"""Docling'in sayfa bazlı Markdown çıktısını token sınırlı chunk'lara böler.

Kurallar:
- Chunk'lar sayfa sınırını aşmaz; boş sayfalar atlanır.
- `chunk_size` KESİN üst sınırdır (başlık öneki ve overlap dahil), embedding
  modelinin kendi tokenlarıyla ölçülür. Böylece model hiçbir chunk'ı kırpmaz.
- Sayfa metni bloklara ayrılır: başlık (`#`), tablo (art arda `|` satırları),
  metin. Bloklar sırayla, sınır dolana kadar aynı chunk'a eklenir.
- Aktif başlık, bölümün sonraki chunk'larının başına (ve sonraki sayfaya)
  bağlam olarak eklenir.
- Boyut nedeniyle yeni chunk'a geçilirken, önceki chunk metinle bitiyorsa son
  cümlelerinden en fazla `chunk_overlap` tokenlık bir overlap taşınır. Yeni
  bölümde (başlık) ve tablodan sonra overlap uygulanmaz.
- Sınırı aşan metin cümlelerden, o da yetmezse kelimelerden bölünür. Sınırı
  aşan tablo satır gruplarına bölünür ve her parçaya başlık satırı tekrar
  eklenir; böylece her parça kendi başına anlamlı bir tablodur.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.core.models import Chunk, IngestedDocument
from app.interfaces.text_chunker import TextChunker

_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
_TABLE_SEPARATOR_RE = re.compile(r"^\|?(\s*:?-{3,}:?\s*\|)*\s*:?-{3,}:?\s*\|?$")
# Basit cümle sınırı: . ! ? … ve ardından boşluk, ya da satır sonu.
# Bilinen sınırlama: "Dr." gibi kısaltmalarda da böler; içerik kaybı olmaz.
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?…])\s+|\n+")
_PART_SEPARATOR = "\n\n"
# Başlık öneki chunk'ın en fazla bu oranını kaplayabilir; daha uzun başlıklar önek yapılmaz.
_MAX_PREFIX_RATIO = 4
# Parça bütçesi hesaplanırken ayraç tokenları için bırakılan pay.
_SEPARATOR_MARGIN = 3

TEXT, TABLE, HEADING, PREFIX, OVERLAP = "text", "table", "heading", "prefix", "overlap"


@dataclass(frozen=True, slots=True)
class _Part:
    kind: str
    text: str


class MarkdownChunker(TextChunker):
    VERSION = "1"

    def __init__(
        self,
        count_tokens: Callable[[str], int],
        chunk_size: int = 500,
        chunk_overlap: int = 75,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size pozitif olmalı.")
        if not 0 <= chunk_overlap < chunk_size // 2:
            raise ValueError("chunk_overlap 0 ile chunk_size/2 arasında olmalı.")
        self._count = count_tokens
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    @property
    def version(self) -> str:
        return self.VERSION

    def chunk(self, document: IngestedDocument) -> list[Chunk]:
        chunks: list[Chunk] = []
        heading: str | None = None
        for page in document.pages:
            if page.is_empty:
                continue
            texts, heading = self._chunk_page(page.text, heading)
            for index, text in enumerate(texts):
                chunks.append(
                    Chunk(
                        chunk_id=Chunk.make_id(document.document_id, page.page_number, index),
                        document_id=document.document_id,
                        file_name=document.file_name,
                        page_number=page.page_number,
                        chunk_index=index,
                        text=text,
                        token_count=self._count(text),
                    )
                )
        return chunks

    # --- Sayfa düzeyi -------------------------------------------------------

    def _chunk_page(self, page_text: str, heading: str | None) -> tuple[list[str], str | None]:
        builder = _PageBuilder(self, heading)
        for block in _parse_blocks(page_text):
            if block.kind == HEADING:
                builder.start_section(block.text)
            else:
                for piece in self._split_block(block, builder.piece_budget()):
                    builder.add(piece)
        return builder.finish(), builder.heading

    # --- Sınırı aşan blokları bölme -----------------------------------------

    def _split_block(self, block: _Part, budget: int) -> list[_Part]:
        if self._count(block.text) <= budget:
            return [block]
        if block.kind == TABLE:
            return self._split_table(block.text, budget)
        # Metin parçaları overlap payı bırakılarak bölünür; aksi halde "overlap +
        # parça" sınıra hiç sığmaz ve overlap sessizce düşer.
        text_budget = max(budget - self._chunk_overlap, 1)
        return [_Part(TEXT, text) for text in self._split_text(block.text, text_budget)]

    def _split_table(self, table: str, budget: int) -> list[_Part]:
        lines = table.splitlines()
        has_separator = len(lines) > 1 and _TABLE_SEPARATOR_RE.match(lines[1].strip())
        head = lines[:2] if has_separator else lines[:1]
        rows = lines[len(head):]
        if not rows or self._count("\n".join(head)) > budget // 2:
            # Başlığı bile sığmayan tablo: metin gibi böl.
            return [_Part(TEXT, text) for text in self._split_text(table, budget)]

        pieces: list[_Part] = []
        current: list[str] = []
        for row in rows:
            if self._count("\n".join(head + current + [row])) <= budget:
                current.append(row)
                continue
            if current:
                pieces.append(_Part(TABLE, "\n".join(head + current)))
                current = []
            if self._count("\n".join(head + [row])) <= budget:
                current = [row]
            else:
                # Tek satır bile sınırı aşıyor (nadir): satırı metin olarak böl.
                pieces.extend(_Part(TEXT, text) for text in self._split_text(row, budget))
        if current:
            pieces.append(_Part(TABLE, "\n".join(head + current)))
        return pieces

    def _split_text(self, text: str, budget: int) -> list[str]:
        units = [unit.strip() for unit in _SENTENCE_BOUNDARY_RE.split(text) if unit.strip()]
        pieces: list[str] = []
        current: list[str] = []
        for unit in units:
            if self._count(unit) > budget:
                if current:
                    pieces.append(" ".join(current))
                    current = []
                pieces.extend(self._split_words(unit, budget))
            elif self._count(" ".join(current + [unit])) <= budget:
                current.append(unit)
            else:
                pieces.append(" ".join(current))
                current = [unit]
        if current:
            pieces.append(" ".join(current))
        return pieces

    def _split_words(self, text: str, budget: int) -> list[str]:
        pieces: list[str] = []
        current: list[str] = []
        for word in text.split():
            if self._count(word) > budget:
                if current:
                    pieces.append(" ".join(current))
                    current = []
                pieces.extend(self._split_characters(word, budget))
            elif self._count(" ".join(current + [word])) <= budget:
                current.append(word)
            else:
                pieces.append(" ".join(current))
                current = [word]
        if current:
            pieces.append(" ".join(current))
        return pieces

    def _split_characters(self, word: str, budget: int) -> list[str]:
        """Boşluk içermeyen ve tek başına sınırı aşan dizgiler (ör. uzun kodlar) için son çare."""
        pieces: list[str] = []
        rest = word
        while rest:
            # Sınıra sığan en uzun önek (ikili arama); en az 1 karakter ilerler.
            low, high = 1, len(rest)
            while low < high:
                middle = (low + high + 1) // 2
                if self._count(rest[:middle]) <= budget:
                    low = middle
                else:
                    high = middle - 1
            pieces.append(rest[:low])
            rest = rest[low:]
        return pieces

    # --- Overlap ------------------------------------------------------------

    def overlap_from(self, text: str) -> str | None:
        """Metnin sonundan en fazla `chunk_overlap` tokenlık, cümle sınırında başlayan kuyruk."""
        if self._chunk_overlap == 0:
            return None
        sentences = [unit.strip() for unit in _SENTENCE_BOUNDARY_RE.split(text) if unit.strip()]
        selected: list[str] = []
        for sentence in reversed(sentences):
            if self._count(" ".join([sentence] + selected)) > self._chunk_overlap:
                break
            selected.insert(0, sentence)
        if selected:
            return " ".join(selected)
        # Son cümle tek başına overlap'ten uzun: son kelimelerini al.
        words: list[str] = []
        for word in reversed(sentences[-1].split() if sentences else []):
            if self._count(" ".join([word] + words)) > self._chunk_overlap:
                break
            words.insert(0, word)
        return " ".join(words) or None

    def prefix_for(self, heading: str | None) -> str | None:
        if heading and self._count(heading) * _MAX_PREFIX_RATIO <= self._chunk_size:
            return heading
        return None

    def fits(self, parts: list[_Part]) -> bool:
        return self._count(_PART_SEPARATOR.join(part.text for part in parts)) <= self._chunk_size


class _PageBuilder:
    """Tek bir sayfanın chunk'larını sırayla oluşturur."""

    def __init__(self, chunker: MarkdownChunker, heading: str | None) -> None:
        self._chunker = chunker
        self.heading = heading
        self._texts: list[str] = []
        self._parts: list[_Part] = self._fresh_parts()

    def piece_budget(self) -> int:
        """Taze bir chunk'ta (önekle birlikte) bir parçanın kaplayabileceği token sayısı."""
        prefix = self._chunker.prefix_for(self.heading)
        used = self._chunker._count(prefix) + _SEPARATOR_MARGIN if prefix else 0
        return self._chunker._chunk_size - used

    def start_section(self, heading: str) -> None:
        if self._has_content():
            self._flush()
            self._parts = []
        # Henüz içerik yoksa: taşınan önek yeni başlıkla değiştirilir, art arda
        # gelen başlıklar ise birlikte tutulur.
        self._parts = [part for part in self._parts if part.kind != PREFIX]
        self.heading = heading
        heading_part = _Part(HEADING, heading)
        if self._chunker.fits(self._parts + [heading_part]):
            self._parts.append(heading_part)
        else:
            for piece in self._chunker._split_block(_Part(TEXT, heading), self._chunker._chunk_size):
                self.add(piece)

    def add(self, piece: _Part) -> None:
        if self._chunker.fits(self._parts + [piece]):
            self._parts.append(piece)
            return

        previous_last = self._parts[-1] if self._parts else None
        overlap = (
            self._chunker.overlap_from(previous_last.text)
            if previous_last is not None and previous_last.kind == TEXT and piece.kind == TEXT
            else None
        )
        self._flush()
        self._parts = self._fresh_parts()
        if overlap and self._chunker.fits(self._parts + [_Part(OVERLAP, overlap), piece]):
            self._parts.append(_Part(OVERLAP, overlap))
        if not self._chunker.fits(self._parts + [piece]):
            self._parts = []  # Son çare: öneki bırak.
        if self._chunker.fits(self._parts + [piece]):
            self._parts.append(piece)
        else:
            # Bütçe hesabındaki yaklaşıklık yüzünden sığmayan parça: daha küçük böl.
            for smaller in self._chunker._split_text(piece.text, self._chunker._chunk_size // 2):
                self.add(_Part(TEXT, smaller))

    def finish(self) -> list[str]:
        self._flush()
        return self._texts

    def _fresh_parts(self) -> list[_Part]:
        prefix = self._chunker.prefix_for(self.heading)
        return [_Part(PREFIX, prefix)] if prefix else []

    def _has_content(self) -> bool:
        return any(part.kind in (TEXT, TABLE) for part in self._parts)

    def _flush(self) -> None:
        # Yalnızca önek (taşınan başlık) içeren chunk üretilmez; başlık içeren chunk
        # ise üretilir ki sayfa sonundaki bir başlık kaybolmasın.
        if any(part.kind in (TEXT, TABLE, HEADING) for part in self._parts):
            self._texts.append(_PART_SEPARATOR.join(part.text for part in self._parts))
        self._parts = []


def _parse_blocks(text: str) -> list[_Part]:
    blocks: list[_Part] = []
    for group in re.split(r"\n\s*\n", text.strip()):
        run: list[str] = []
        run_is_table = False
        for line in group.splitlines():
            is_table = line.lstrip().startswith("|")
            if run and is_table != run_is_table:
                blocks.extend(_classify(run, run_is_table))
                run = []
            run.append(line)
            run_is_table = is_table
        if run:
            blocks.extend(_classify(run, run_is_table))
    return blocks


def _classify(lines: list[str], is_table: bool) -> list[_Part]:
    if is_table:
        return [_Part(TABLE, "\n".join(line.strip() for line in lines))]
    blocks: list[_Part] = []
    # Başlık satırı metinle aynı grupta (araya boş satır girmeden) gelebilir.
    while lines and _HEADING_RE.match(lines[0].strip()):
        blocks.append(_Part(HEADING, lines.pop(0).strip()))
    body = "\n".join(lines).strip()
    if body:
        blocks.append(_Part(TEXT, body))
    return blocks
