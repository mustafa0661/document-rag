# Test ve Doğrulama

Bu doküman sistemin nasıl test edildiğini, sonuçlarını ve bilinen sınırlarını kayıt altına alır. Şu an **Document Ingestion** bileşenini kapsıyor; retrieval ve soru-cevap aşamaları geliştirildikçe yeni bölümler eklenecek.

## Testleri çalıştırma

```bash
pip install -r requirements-dev.txt
python -m scripts.download_models   # Modelleri önceden indirir (ilk kurulumda bir kez)

pytest -m "not integration" -v      # Birim testleri: Docling yüklenmez, saniyeler içinde biter
pytest -m integration -v            # Entegrasyon: gerçek Docling + EasyOCR
pytest -v                           # Tümü
```

Model indirme adımı atlanırsa modeller ilk entegrasyon testinde indirilir; bu durumda internet bağlantısı gerekir ve ilk çalıştırma birkaç dakika sürebilir. Docling kurulu olmayan bir ortamda entegrasyon modülü otomatik olarak atlanır ve birim testleri yine çalışır.

## Test ortamı

| | |
|---|---|
| İşletim sistemi | Windows |
| Python | 3.11.9 |
| pytest | 9.1.1 |
| Docling | 2.138.0 (`docling[feat-ocr-easyocr]`) |
| OCR | EasyOCR, diller: `tr`, `en` |
| Donanım hızlandırma | Yok — torch CPU üzerinde çalışıyor (bkz. Sınırlamalar) |

## Test stratejisi

Testler iki katmana ayrıldı:

- **Birim testleri** (`tests/test_ingestion_service.py`): `IngestionService`, sahte bir parser ile test ediliyor. Doğrulama, metadata ve hata yönetimi mantığı Docling'den bağımsız olarak, hızlıca sınanıyor.
- **Entegrasyon testleri** (`tests/test_docling_parser.py`, `@pytest.mark.integration`): Gerçek Docling ve EasyOCR modelleriyle uçtan uca çalışıyor.

Test dosyaları depoya konmuyor; `tests/conftest.py` her oturumda bunları üretiyor (Pillow ile metin içeren görseller, görüntüden oluşan PDF'ler, fpdf2 ile metin katmanlı ve tablolu PDF'ler). Böylece her testin hangi metni, hangi sayfada beklediği kodda açıkça görülebiliyor.

OCR çıktısı birebir deterministik olmadığı için metin testleri tam eşleşme yerine anahtar kelimelerin varlığını kontrol ediyor. Türkçe karakterlerin (ç, ğ, ı, ö, ş, ü) korunması ise ayrıca doğrulanıyor: yanlış bir dil yapılandırmasında ilk bozulacak şey bunlardır. Dijital tabloda ise hücreler birebir kontrol ediliyor, çünkü değerin doğru satır ve sütunda kalması doğru cevabın ön koşulu.

## Sonuçlar

| Katman | Sonuç | Süre |
|---|---|---|
| Birim testleri | 12 / 12 geçti | < 1 sn |
| Entegrasyon testleri | 9 / 9 geçti | 37,6 sn |
| **Tümü** | **21 / 21 geçti** | **41,2 sn** |

Entegrasyon testleri üç kez çalıştırıldı; üçünde de tamamı geçti.

### Birim testleri

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

### Entegrasyon testleri

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

## Belge tiplerine göre davranış

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

## Bilinen sınırlamalar ve başarısız olunan durumlar

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
Torch CPU sürümüyle kurulu. 9 entegrasyon testi yaklaşık 37,6 saniye sürüyor. Çok sayfalı belgelerde işleme süresi belirgin şekilde artacak.

### 5. İlk kurulumda model indirme
Docling ve EasyOCR modelleri ilk kullanımda internetten indiriliyor. Bu nedenle kurulumda `python -m scripts.download_models` adımı ayrıca çalıştırılıyor; ağ sorunu varsa testte değil burada, anlaşılır bir mesajla ortaya çıkıyor. Geliştirme ortamında bir kez indirme hatası yaşandı, ancak yeniden üretilemedi (bkz. `DEVLOG.md`).

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
- README'deki kurulum adımlarının boş bir ortamda baştan sona denenmesi
- Retrieval, soru-cevap ve "belgede olmayan bilgi" senaryoları (ilgili bileşenler geliştirilince eklenecek)
