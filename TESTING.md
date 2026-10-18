# Test ve Doğrulama

Bu doküman sistemin nasıl test edildiğini, sonuçlarını ve bilinen sınırlarını kayıt altına alır. Şu an **Document Ingestion** ile **Chunking, Embedding ve Retrieval** bileşenlerini kapsıyor; soru-cevap (LLM) aşaması geliştirildikçe yeni bölümler eklenecek.

## Testleri çalıştırma

```bash
pip install -r requirements-dev.txt
python -m app.scripts.download_models   # Modelleri önceden indirir (ilk kurulumda bir kez)

pytest -m "not integration" -v          # Birim testleri: model yüklenmez
pytest -m integration -v -s             # Entegrasyon: gerçek Docling, EasyOCR ve BGE-M3; -s ölçümleri gösterir
pytest -v                               # Tümü
```

Model indirme adımı atlanırsa modeller ilk entegrasyon testinde indirilir; bu durumda internet bağlantısı gerekir ve ilk çalıştırma birkaç dakika sürebilir. Docling veya sentence-transformers kurulu olmayan bir ortamda ilgili entegrasyon modülü otomatik olarak atlanır ve birim testleri yine çalışır.

## Test ortamı

| | |
|---|---|
| İşletim sistemi | Windows |
| Python | 3.11.9 |
| pytest | 9.1.1 |
| Docling | 2.138.0 (`docling[feat-ocr-easyocr]`) |
| OCR | EasyOCR, diller: `tr`, `en` |
| Embedding | BAAI/bge-m3 (`sentence-transformers` 6.1.0), 1024 boyut |
| Vektör veritabanı | ChromaDB 1.5.9, kosinüs mesafesi |
| Donanım hızlandırma | Yok — torch CPU üzerinde çalışıyor (bkz. Sınırlamalar) |

## Test stratejisi

Testler iki katmana ayrıldı:

- **Birim testleri** (`tests/test_ingestion_service.py`): `IngestionService`, sahte bir parser ile test ediliyor. Doğrulama, metadata ve hata yönetimi mantığı Docling'den bağımsız olarak, hızlıca sınanıyor.
- **Entegrasyon testleri** (`tests/test_docling_parser.py`, `@pytest.mark.integration`): Gerçek Docling ve EasyOCR modelleriyle uçtan uca çalışıyor.

Test dosyaları depoya konmuyor; `tests/conftest.py` her oturumda bunları üretiyor (Pillow ile metin içeren görseller, görüntüden oluşan PDF'ler, fpdf2 ile metin katmanlı ve tablolu PDF'ler). Böylece her testin hangi metni, hangi sayfada beklediği kodda açıkça görülebiliyor.

OCR çıktısı birebir deterministik olmadığı için metin testleri tam eşleşme yerine anahtar kelimelerin varlığını kontrol ediyor. Türkçe karakterlerin (ç, ğ, ı, ö, ş, ü) korunması ise ayrıca doğrulanıyor: yanlış bir dil yapılandırmasında ilk bozulacak şey bunlardır. Dijital tabloda ise hücreler birebir kontrol ediliyor, çünkü değerin doğru satır ve sütunda kalması doğru cevabın ön koşulu.

## Sonuçlar

Son çalıştırma (Windows), iki aşama birlikte:

| Katman | Sonuç | Süre |
|---|---|---|
| Birim testleri | 53 / 53 geçti | 12,3 sn |
| Entegrasyon testleri | 20 / 20 geçti | 64,7 sn |
| **Tümü** | **73 / 73 geçti** | |

| Aşama | Birim | Entegrasyon |
|---|---|---|
| Ingestion | 12 | 9 |
| Chunking, embedding, retrieval | 41 (16 chunker + 25 indeks/retrieval) | 11 (BGE-M3) |

Ingestion entegrasyon testleri ayrıca üç kez art arda çalıştırıldı; üçünde de tamamı geçti.

### Ingestion

#### Birim testleri

| Test | Doğrulanan davranış |
|---|---|
| `test_metadata_is_attached_to_every_page` | `document_id`, dosya adı ve sayfa numarası her sayfaya aktarılıyor |
| `test_page_numbers_come_from_parser_not_renumbered` | Servis sayfaları yeniden numaralandırmıyor (ör. 1, 3 → 1, 3) |
| `test_document_id_depends_on_content_not_name` | Aynı içerik → aynı kimlik; farklı içerik → farklı kimlik |
| `test_extension_check_is_case_insensitive` | `.PNG` gibi büyük harfli uzantılar kabul ediliyor |
| `test_unsupported_extension_is_rejected_before_parsing` | `.docx` reddediliyor; mesaj dosya adını ve desteklenen uzantıları içeriyor; parser hiç çağrılmıyor |
| `test_file_without_extension_is_rejected` | Uzantısız dosya reddediliyor |
| `test_empty_file_is_rejected_before_parsing` | 0 baytlık dosya, parse'a gitmeden `EmptyFileError` veriyor |
| `test_missing_file_raises_file_not_found` | Var olmayan dosya için `FileNotFoundError` |
| `test_directory_path_raises_file_not_found` | Dosya yerine klasör verilirse reddediliyor |
| `test_parse_error_propagates` | Parser hatası servis üzerinden iletiliyor |
| `test_document_without_text_is_returned_with_warning` | Metinsiz belge hata değil; boş sayfalar korunuyor ve uyarı loglanıyor |
| `test_accepts_str_path` | `str` yol da kabul ediliyor |

#### Entegrasyon testleri

| Test | Girdi | Doğrulanan davranış |
|---|---|---|
| `test_text_pdf_keeps_page_boundaries` | Metin katmanlı 2 sayfalık PDF (TR + EN) | Sayfa numaraları 1, 2; her sayfanın metni yalnızca kendi sayfasında |
| `test_turkish_png_is_read_with_turkish_characters` | Türkçe metin içeren PNG | `şikayeti`, `göğüs`, `ağrısı`, `üç`, `açıklanacak` doğru okunuyor |
| `test_english_jpg_is_read` | İngilizce metin içeren JPG | `invoice`, `total`, `amount`, `payment` doğru okunuyor |
| `test_scanned_pdf_is_ocred_page_by_page` | Metin katmanı olmayan 2 sayfalık PDF (TR + EN) | Her sayfa OCR'lanıyor ve metin doğru sayfaya atanıyor |
| `test_pdf_table_is_exported_with_rows_and_columns` | Laboratuvar sonuç tablosu içeren metin katmanlı PDF | Başlık satırı ve `Glukoz \| 98 \| mg/dL \| 70 - 100` satırı hücre hücre doğru; tablo dışındaki paragraf korunuyor |
| `test_scanned_table_is_ocred_into_table_structure` | Aynı tablonun görüntüye çevrilmiş hâli (PNG) | OCR sonrası 4 satırlık tablo yapısı kuruluyor; "Glukoz" satırında "98" doğru sütunda |
| `test_warm_up_initializes_pipelines` | — | Kurulum betiğinin kullandığı `warm_up()` hatasız çalışıyor |
| `test_corrupted_pdf_raises_parse_error` | `%PDF` başlıklı rastgele baytlar | Anlaşılır `DocumentParseError` |
| `test_service_end_to_end_with_docling` | Metin katmanlı PDF | Servis + Docling birlikte: metadata ve sayfa numaraları doğru |

## Chunking, Embedding ve Retrieval

### Test stratejisi
- **Birim testleri** gerçek model yerine sahte bir embedding provider kullanıyor. Bu provider kelimeleri hash'leyerek normalize edilmiş vektörler üretiyor; deterministik ve kelime örtüşmesine duyarlı. Bu sayede "doğru chunk bulundu mu" mantığı modelden bağımsız olarak sınanabiliyor. Vektör veritabanı ise her test için geçici bir klasörde açılan **gerçek** bir ChromaDB.
- **Entegrasyon testleri** gerçek BGE-M3 ile çalışıyor. Sorgular chunk'lardaki kelimeleri bilinçli olarak tekrar etmiyor ("şeker" ↔ "glukoz"); bu sayede kelime eşleşmesi değil, anlamsal arama ölçülüyor.
- **Testlerin gerçekten bir şey ölçtüğü doğrulandı (mutasyon testi).** Beş kritik koruma tek tek bozuldu: yapılandırma kontrolü, belge filtresi, yarım indekslemenin geri alınması, tekrar indekslemenin atlanması ve embedding boyut kontrolü. Her birinde en az bir test başarısız oldu.

### İstenen senaryoların karşılığı

| # | Senaryo | Test(ler) | Katman |
|---|---|---|---|
| 1 | Türkçe metinde doğru chunk | `test_turkish_query_finds_correct_chunk_with_source_and_page`, `test_semantic_query_finds_correct_page` (TR) | Birim + Entegrasyon |
| 2 | İngilizce metinde doğru chunk | `test_english_query_finds_correct_chunk`, `test_semantic_query_finds_correct_page` (EN) | Birim + Entegrasyon |
| 3 | Türkçe soru → İngilizce içerik | `test_turkish_query_finds_english_content` | Entegrasyon |
| 4 | Sayfa numarası korunuyor | `test_chunks_never_cross_pages_and_keep_page_numbers`, retrieval testlerindeki sayfa kontrolleri | Birim + Entegrasyon |
| 5 | Belgeler arası veri karışmıyor | `test_search_never_returns_chunks_from_other_documents`, `test_document_ids_are_required`, `test_delete_document_removes_only_its_chunks` | Birim |
| 6 | Aynı dosyanın tekrar indekslenmesi | `test_reindexing_same_document_is_skipped_without_duplicates`, `test_forced_reindex_replaces_chunks` | Birim |
| 7 | Boş içerik ve boş sorgu | `test_empty_document_indexes_nothing`, `test_empty_query_is_rejected` (3 varyant), `test_empty_pages_are_skipped` | Birim |
| 8 | Overlap doğruluğu | `test_overlap_repeats_tail_of_previous_chunk_from_a_sentence_start`, `test_overlap_falls_back_to_words_when_last_sentence_is_too_long`, `test_no_overlap_when_disabled` | Birim |
| 9 | Markdown tablo yapısı | `test_short_table_stays_intact_in_one_chunk`, `test_long_table_is_split_and_every_part_repeats_the_header`, `test_no_overlap_is_injected_into_tables`, `test_markdown_table_survives_storage_roundtrip` | Birim |
| 10 | Kalıcı veritabanının yeniden açılması | `test_persistent_index_is_usable_after_reopening` | Birim |
| 11 | Yanlış boyut veya model yapılandırması | `test_opening_index_with_different_config_is_rejected` (5 varyant), `test_wrong_embedding_dimension_is_rejected_and_nothing_is_stored`, `test_embedding_dimension_and_normalization` | Birim + Entegrasyon |
| 12 | Alakasız sorgular | `test_irrelevant_queries_are_farther_than_relevant_ones` | Entegrasyon |

Bunlara ek olarak şu testler var:
- **Chunker:** 500 token sınırının hiçbir içerik türünde aşılmaması (gerçek tokenizer'la da doğrulandı), uzun cümlenin kelimelerden bölünmesi, başlığın sonraki chunk'lara ve sayfaya taşınması, sayfa sonundaki başlığın kaybolmaması, aynı girdiden her seferinde aynı çıktının üretilmesi.
- **İndeksleme:** Yarıda kalan indekslemenin geri alınması, açık bir sıfırlama komutundan sonra indeksin yeniden oluşturulabilmesi.

### Ölçümler (CPU, Windows)

| Ölçüm | Değer |
|---|---|
| BGE-M3 ilk indirme | 178 sn (~2,3 GB) |
| BGE-M3 yükleme (önbellekten) | 6,1 sn |
| Embedding hızı | **1,23 chunk/sn** (16 chunk, chunk başına ~360 token, 13,0 sn) |
| Türkçe token yoğunluğu | 2,33 token/kelime (12 kelime = 28 token) |

**Yorum:** Türkçede kelime başına 2,33 token düşmesi, chunk boyutunun modelin kendi tokenizer'ıyla ölçülmesi kararını doğruluyor. Kelime sayısıyla ölçülseydi "500 kelimelik" bir chunk yaklaşık 1165 token olurdu ve modelin 512 tokenlık sınırında sessizce kırpılırdı. CPU'daki embedding hızı ise asıl darboğaz: 100 sayfalık bir belge (~300 chunk) yalnızca embedding için 4 dakikanın üzerinde sürer. GPU (RTX 3060) değerlendirmesi için ölçülmüş bir gerekçe bu.

### Mesafe ölçümleri

ChromaDB'nin döndürdüğü değer kosinüs **mesafesi**: `1 − kosinüs benzerliği`. Aralığı [0, 2] ve **küçük olan daha alakalı**. Embedding'ler normalize edildiği için `benzerlik = 1 − mesafe` birebir kosinüs benzerliği. Tabloda en yakın sonucun mesafesi veriliyor.

| Tür | Soru | Belge | Bulunan sayfa | Mesafe |
|---|---|---|---|---|
| Alakalı (TR) | Şeker değeri kaç çıktı? | Türkçe | 1 ✅ | 0,4795 |
| Alakalı (TR) | Doktora tekrar ne zaman gideceğim? | Türkçe | 2 ✅ | 0,3898 |
| Alakalı (TR) | İlacı nasıl kullanmalıyım? | Türkçe | 3 ✅ | 0,3885 |
| Alakalı (EN) | How much do I have to pay in total? | İngilizce | 1 ✅ | 0,3258 |
| Alakalı (EN) | How long does shipping take? | İngilizce | 3 ✅ | 0,3130 |
| Diller arası | Ödemenin son günü ne zaman? | İngilizce | 2 ✅ | 0,2942 |
| Diller arası | Ürünün garanti süresi ne kadar? | İngilizce | 4 ✅ | 0,3281 |
| Alakasız | Dünya Kupası finalini hangi takım kazandı? | Türkçe | — | 0,7647 |
| Alakasız | What is the capital of Australia? | İngilizce | — | 0,6725 |

**Özet:** Alakalı soruların en iyi sonuçları 0,2942 ile 0,4795 arasında (ortalama 0,3598); alakasız sorularınkiler 0,6725 ile 0,7647 arasında. Arada yaklaşık 0,19'luk bir boşluk var.

**Gözlemler:**
- Yedi alakalı sorunun yedisinde de doğru sayfa ilk sırada geldi.
- Diller arası arama, aynı dildeki aramadan daha kötü değil; en düşük mesafe Türkçe soru ile İngilizce içerik arasında ölçüldü.
- En zor durum eş anlamlı kelime içeren soru oldu ("şeker" ↔ "glukoz", 0,4795).

**Neden henüz eşik yok:** Örnek küçük (7 alakalı, 2 alakasız soru) ve metinler kısa, tek cümlelik sayfalar. Bu sonuçlar eşiğin 0,55–0,60 aralığında aranabileceğine işaret ediyor. Ancak eşik, gerçek ve uzun belgelerle yapılacak ölçümden sonra belirlenecek (`python -m app.scripts.search_documents`). Uzun chunk'larda mesafelerin genel olarak artması beklenir.

### Bilinen sınırlamalar
- **Cümle ayırıcı basit bir kurala dayanıyor.** "Dr." gibi kısaltmalarda yanlış bölebiliyor. Sonucu en fazla birkaç kelimelik bir chunk sınırı kayması; içerik kaybı yok.
- **Sayfa sınırını aşan paragraflar iki chunk'a bölünüyor**, çünkü chunk'lar sayfa sınırını aşmıyor. Ingestion'daki bilinen sınırlama nedeniyle (Docling'in sayfa sonu birleştirmesi) devam eden kısım çoğu zaman zaten önceki sayfada yer alıyor.
- **Embedding CPU'da yavaş** (1,23 chunk/sn). Bkz. Ölçümler.

### Test çıktısındaki zararsız mesajlar
- `Token indices sequence length is longer than the specified maximum sequence length (… > 512)`: Chunker, uzun bir paragrafı bölmeden önce token sayısını ölçmek için tokenizer'a veriyor; tokenizer da metnin modelin sınırından uzun olduğunu hatırlatıyor. Bu metin modele hiçbir zaman gönderilmiyor; model en fazla 500 tokenlık chunk'lar görüyor (`test_real_tokenizer_keeps_chunks_within_limit`).
- Hugging Face'in `HF_TOKEN` ve Windows symlink uyarıları: Kimlik doğrulaması olmadan indirme yapıldığını ve Windows'ta önbelleğin kopya dosyalarla çalıştığını bildiriyor. İşlevsel bir etkileri yok (bkz. README → Sorun giderme).

## Ingestion: Belge tiplerine göre davranış

| Belge tipi | Durum | Not |
|---|---|---|
| Dijital (metin katmanlı) PDF | ✅ Test edildi | Metin katmanından okunuyor, OCR'a gerek kalmıyor |
| Taranmış PDF | ✅ Test edildi | Sayfa sayfa OCR'lanıyor |
| Türkçe görsel (PNG) | ✅ Test edildi | Türkçe karakterler korunuyor |
| İngilizce görsel (JPG) | ✅ Test edildi | |
| Tablolu dijital PDF | ✅ Test edildi | Markdown tablosu olarak çıkıyor; hücreler doğru satır ve sütunda |
| Tablolu taranmış belge | ✅ Test edildi | OCR + tablo yapısı birlikte çalışıyor |
| Düşük kaliteli / eğik tarama, el yazısı | ⚠️ Henüz test edilmedi | |

Önemli not: Şu ana kadarki testler **sentetik, temiz** belgelerle yapıldı (beyaz zemin, net font, kenarlıklı tablo). Gerçek dünya taramalarındaki performans henüz ölçülmedi.

## Ingestion: Bilinen sınırlamalar ve başarısız olunan durumlar

### 1. Sayfa sınırını aşan paragrafların sayfa ataması
Docling, bir sayfanın sonunda bitmemiş görünen paragrafı bir sonraki sayfanın başıyla tek öğede birleştiriyor. Sayfa bazlı dışa aktarma yalnızca öğenin ilk sayfasına baktığı için, devam eden kısım **bir önceki sayfaya** yazılıyor. Metin kaybolmuyor, ancak RAG'de kaynak gösterilirken bu kısım için sayfa numarası bir eksik görünebilir.

Bu davranış geliştirme sırasında bir test başarısızlığıyla ortaya çıktı: noktalamasız sentetik test metinleri her sayfa geçişinde birleştirmeyi tetikliyordu ve taranmış PDF'in 2. sayfası boş dönüyordu. Teşhis süreci `DEVLOG.md` içinde (Day 2) adım adım anlatılıyor.

### 2. Tam sayfa OCR modunda kelime sırası
`force_full_page_ocr=True` (yani `OcrMode.FULL_PAGE`) kullanıldığında kelime sırasının bozulduğu gözlendi: "üç **gün** içinde açıklanacak" metni "üç içinde açıklanacak **gün**" olarak çıktı. EasyOCR aynı görüntüyü doğrudan okuduğunda sıra doğru çıkıyor; yani sorun Docling'in OCR sonuçlarını birleştirme adımında. Varsayılan modda bu sorun görülmedi; parser bu yüzden varsayılan modu kullanıyor.

### 3. Tablo testinde aralıklı "Windows fatal exception: access violation" mesajı
Windows'ta üç çalıştırmanın ikisinde, her seferinde aynı testte (`test_pdf_table_is_exported_with_rows_and_columns`) bu mesaj görüldü. Test her seferinde geçti ve süreç hiç çökmedi.

Mesaj, pytest'in `faulthandler` eklentisinden geliyor. Windows'ta `faulthandler`, yerel (C/C++) bir kütüphanede oluşan istisnayı kütüphanenin kendi hata yakalayıcısından önce görüyor; bu yüzden kütüphanenin kendi içinde yakalayıp toparladığı istisnalar da bu mesajı üretebiliyor. Thread dökümüne göre mesaj anında hiçbir Python kodu çalışmıyordu (Docling'in tüm pipeline thread'leri iş bekliyordu) ve hatayı veren thread, Python karşılığı olmayan yerel bir thread'di. Mesajın çıktığı çalıştırmalarda da tablo hücreleri birebir doğru çıktı.

Hata üçüncü parti yerel kodda olduğu ve çıktıyı etkilemediği için proje tarafında bir değişiklik yapılmadı. Mesaj bilinçli olarak gizlenmedi (`-p no:faulthandler` kullanılmadı); böylece ileride gerçek bir çökme olursa teşhis bilgisi kaybolmaz. Bir çalıştırmada süreç çökerse veya tablo çıktısı yanlış çıkarsa yeniden ele alınacak.

### 4. CPU üzerinde çalışma
Torch CPU sürümüyle kurulu. Ingestion'ın 9 entegrasyon testi yaklaşık 37,6 saniye sürüyor; embedding hızı 1,23 chunk/sn (bkz. Ölçümler). Çok sayfalı belgelerde işleme süresi belirgin şekilde artacak.

### 5. İlk kurulumda model indirme
Docling ve EasyOCR modelleri ilk kullanımda internetten indiriliyor. Bu nedenle kurulumda `python -m app.scripts.download_models` adımı ayrıca çalıştırılıyor; ağ sorunu varsa testte değil burada, anlaşılır bir mesajla ortaya çıkıyor. Geliştirme ortamında bir kez indirme hatası yaşandı, ancak yeniden üretilemedi (bkz. `DEVLOG.md`).

## Test çıktısındaki uyarılar

Entegrasyon testleri çalışırken üçüncü parti kütüphanelerden 22 uyarı geliyordu. Bunların hiçbiri proje kodundan kaynaklanmıyor. Önemli mesajları gölgelememeleri için `pytest.ini` içinde **mesaj metniyle tek tek** filtreleniyorlar:

| Uyarı | Kaynağı |
|---|---|
| `force_full_page_ocr is deprecated` | Docling, pipeline seçeneklerini önbellek anahtarı için serileştirirken eski alanı da okuyor. Proje kodu bu alanı kullanmıyor. |
| `generate_table_images ... deprecated` | Docling'in iç pipeline kodu |
| `torch.ao.quantization is deprecated`, `torch.quantize_per_tensor` | EasyOCR'ın kullandığı, torch'ta eskiyen API |
| `pin_memory ... no accelerator is found` | torch'un CPU üzerinde çalıştığını belirtiyor (bkz. Sınırlama 4) |

Uyarıların tamamı kapatılmadı: projeye ait ya da yeni bir uyarı görünmeye devam ediyor. Filtreler, aynı uyarıları üreten bir deneme testiyle doğrulandı. Access violation mesajı bir uyarı olmadığı için bu filtrelerden etkilenmiyor.

## Henüz kapsanmayanlar

- Gerçek taranmış belgelerle (düşük çözünürlük, eğik sayfa, gürültü, el yazısı) doğrulama
- Gerçek ve uzun belgelerde retrieval mesafe ölçümü ve buna dayalı benzerlik eşiği
- GPU (RTX 3060) ile embedding hızı ölçümü
- README'deki kurulum adımlarının boş bir ortamda baştan sona denenmesi
- Soru-cevap (LLM) ve "belgede olmayan bilgi" senaryoları (ilgili bileşen geliştirilince eklenecek)
