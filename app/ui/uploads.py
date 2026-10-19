"""Yüklenen dosyaların doğrulanması ve güvenli biçimde diske yazılması.

İstemciden gelen dosya adı hiçbir zaman doğrudan yol olarak kullanılmaz:
- Dizin bileşenleri atılır (hem `/` hem `\\`), güvensiz karakterler `_` olur.
- Windows'un ayrılmış aygıt adları (CON, NUL, COM1…) etkisizleştirilir.
- Dosya, içeriğinin SHA-256 özetiyle adlandırılan bir klasöre yazılır:
  data/uploads/<özet>/<temizlenmiş_ad>. Aynı içerik bir kez saklanır.
- Son kontrol: çözümlenmiş yol yükleme klasörünün içinde olmalıdır.
"""

import hashlib
import re
import unicodedata
from pathlib import Path

_UNSAFE_CHARS_RE = re.compile(r"[^\w.\- ()]", re.UNICODE)
_MAX_STEM_LENGTH = 120
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
)


class UploadRejectedError(ValueError):
    """Yüklenen dosya kabul edilmedi (uzantı, boyut veya boş içerik)."""


def sanitize_filename(name: str) -> str:
    base = re.split(r"[\\/]", name or "")[-1]
    base = unicodedata.normalize("NFC", base).strip().strip(".")
    base = _UNSAFE_CHARS_RE.sub("_", base)
    stem, dot, extension = base.rpartition(".")
    if not dot:
        stem, extension = base, ""
    stem = stem.strip()[:_MAX_STEM_LENGTH] or "belge"
    if stem.upper() in _WINDOWS_RESERVED:
        stem = f"_{stem}"
    return f"{stem}.{extension.lower()}" if extension else stem


def validate_upload(name: str, data: bytes, allowed_extensions: frozenset[str], max_mb: int) -> None:
    safe_name = sanitize_filename(name)
    extension = Path(safe_name).suffix.lower()
    if extension not in allowed_extensions:
        raise UploadRejectedError(
            f"'{name}' desteklenmiyor. Desteklenen türler: {', '.join(sorted(allowed_extensions))}."
        )
    if not data:
        raise UploadRejectedError(f"'{name}' boş bir dosya.")
    size_mb = len(data) / (1024 * 1024)
    if size_mb > max_mb:
        raise UploadRejectedError(f"'{name}' çok büyük ({size_mb:.1f} MB). En fazla {max_mb} MB yüklenebilir.")


def save_upload(data: bytes, original_name: str, upload_dir: Path) -> Path:
    root = upload_dir.resolve()
    target_dir = root / hashlib.sha256(data).hexdigest()
    path = (target_dir / sanitize_filename(original_name)).resolve()
    if root not in path.parents:
        raise UploadRejectedError("Geçersiz dosya adı.")
    target_dir.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(data)
    return path
