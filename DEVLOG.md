# Development Log

## Day 1 — 2026-10-13

### Hedef
Sınırlı geliştirme süresi içerisinde PDF ve görsellerden metin çıkarabilen, Türkçe ve İngilizce desteği olan, yalnızca yüklenen belge içeriğine dayalı yanıt üreterek halüsinasyonu engelleyen, SOLID ilkelerine uygun ve genişletilebilir bir Belge Analiz & Soru-Cevap MVP'si için geliştirme ortamının hazırlanması ve temel mimarinin kurgulanması.

### Teknik kararlar
- **Programlama Dili:** Python 3.11 (AI/ML ekosistemi, kütüphane olgunluğu ve hızlı prototipleme)
- **Kullanıcı Arayüzü:** Streamlit (Ayrı bir ön yüz geliştirmeye gerek kalmadan belge yükleme ve sohbet akışını hızlıca sunabilme)
- **Belge & Görsel İşleme:** Docling + Tesseract OCR (PDF, JPG, PNG formatlarında yapılandırılmış metin ve tablo çıkarımı; Türkçe/İngilizce dil desteği)
- **Vektör Veritabanı:** ChromaDB (Düşük kurulum maliyeti, metadata desteği ve yerel kalıcılık)
- **Embedding Modeli:** BAAI/bge-m3 (Türkçe ve İngilizce belgelerde yüksek başarımlı çok dilli anlamsal arama)
- **LLM Runtime & Model:** Ollama + Qwen3 4B Instruct (Harici API maliyeti/bağımlılığı olmadan yerel GPU üzerinde çalıştırma)
- **Geliştirme & Dağıtım Ortamı:** Windows, PyCharm, Git ve Docker Compose (Tekrarlanabilir ve taşınabilir çalıştırma ortamı)

### Karar gerekçeleri ve Mimari Değerlendirmeler

#### 1. Mimari Karar: Yerel LLM Kullanımı
- **Değerlendirilen alternatifler:** Yerel Ollama, uzak Ollama sunucusu ve bulut tabanlı LLM API servisleri.
- **Seçilen yaklaşım:** Ollama üzerinden yerel Qwen3 4B modeli.
- **Gerekçe:** Ek sunucu maliyeti veya API kotası kısıtına takılmadan, demo videosu ve yerel değerlendirme için sıfır maliyetli ve hızlı bir MVP ortamı sağlamak.
- **Ödünleşim / Bilinen sınırlamalar:** Çalıştırılan donanımın kapasitesi yanıt süresini ve bağlam (context) boyutunu sınırlar.
- **Genişletilebilirlik:** LLM erişimi bağımsız bir servis/arayüz katmanı arkasında tasarlanmıştır (Open-Closed prensibi). İleride konfigürasyon değişikliğiyle uzak bir Ollama adresine veya bulut LLM API sağlayıcılarına geçiş yapılabilir.
- **Doğrulama:** Modelin RTX 3060 üzerinde VRAM tüketimi, yanıt süresi ve belgeden bilgi çıkarma doğruluğu test edilmiştir.

#### 2. Mimari Karar: Vektör Veritabanı Seçimi
- **Problem:** Belgelerden çıkarılan metin parçalarının (chunk) embedding'lerini saklamak ve kullanıcı sorularıyla anlamsal benzerlik araması (similarity search) yapmak.
- **Değerlendirilen alternatifler:** ChromaDB, FAISS, Qdrant, pgvector.
- **Seçilen yaklaşım:** ChromaDB.
- **Gerekçe:** MVP kapsamında minimum konfigürasyon, yerel diskte kalıcılık (persistence), zengin metadata desteği ve Python ile zahmetsiz entegrasyon.
- **Ödünleşim:** Dağıtık mimariler ve yüksek eşzamanlı sorgu yüklerinde daha gelişmiş bir sunucu tabanlı çözüm gerekebilir.
- **Genişletilebilirlik:** Vektör saklama katmanı soyutlanarak, ileride ölçeklenme ihtiyacına göre Qdrant veya pgvector altyapılarına kolayca geçilebilecek şekilde kurgulanmıştır.
- **Doğrulama:** Farklı dillerdeki belgelerden üretilen parçaların ait olduğu belge metadata'sıyla doğru eşleşmesi ve retrieval sonuçlarının tutarlılığı üzerinden test edilecektir.

### Yapılan işlemler
- [x] Python 3.11 tabanlı sanal geliştirme ortamı (`.venv`) yapılandırıldı.
- [x] Git deposu başlatıldı; `.gitignore` kuralları (venv, cache, veri dizinleri) tanımlandı ve ilk commit oluşturuldu.
- [x] Ollama yerel servisi kuruldu ve `qwen3:4b-instruct` modeli indirildi.
- [x] Modelin GPU (CUDA) üzerinden çalıştığı (`nvidia-smi` ve `ollama ps` ile %100 GPU tahsisi) doğrulandı.
- [x] Projenin klasör hiyerarşisi (`app/`, `tests/`, `docs/`) ve temel bağımlılık listesi planlandı.
- [ ] Belge işleme (Docling & OCR) pipeline'ının kodlanması
- [ ] Embedding ve ChromaDB vektör dizinleme katmanının kurulması
- [ ] Streamlit arayüzünün tamamlanması
- [ ] Pytest test senaryolarının yazılması ve Dockerfile/docker-compose hazırlanması

### Karşılaşılan sorunlar
- **PowerShell Script Çalıştırma Engeli:** Windows varsayılan kısıtlaması nedeniyle sanal ortam aktivasyon betiği çalışmadı. Mevcut kullanıcı kapsamı için `ExecutionPolicy RemoteSigned` tanımlanarak sorun aşıldı.
- **Windows Task Manager / nvidia-smi Bellek Okuma:** WDDM mimarisinden dolayı process bazlı bellek detayında N/A görünmesi incelendi; `ollama ps` üzerinden modelin %100 GPU'da yüklü olduğu teyit edilerek devam edildi.

### Öğrenilenler
- RAG (Retrieval-Augmented Generation) mimarisinde halüsinasyonu engellemenin en kritik ayağının kaliteli metin çıkarımı ve doğru retrieval stratejisi (chunking + multilingual embedding) olduğu netleştirildi.
- Genişletilebilir bir RAG mimarisi için LLM ve vektör katmanlarının doğrudan uygulama mantığına bağlanmak yerine soyut servisler üzerinden yönetilmesinin ilerleyen aşamalarda bakım kolaylığı sağladığı pekiştirildi.

---

## Day 2 — 2026-10-14

### Hedef
RAG zincirinin ilk halkası olan **Document Ingestion** bileşeninin geliştirilmesi: PDF, JPG ve PNG dosyalarından metin çıkarımı, taranmış belgelerde Türkçe/İngilizce OCR, sayfa bazlı saklama, metadata (dosya adı, `document_id`, sayfa numarası) koruması ve anlaşılır hata yönetimi.

Kapsam bilinçli olarak dar tutuldu: LLM, embedding, ChromaDB ve Streamlit entegrasyonu bu aşamaya dahil edilmedi. Amaç, sonraki katmanların güvenebileceği, tek başına test edilmiş bir ingestion çıktısı üretmekti.

### Problemi nasıl parçaladım
Önce kod yazmadan mimari ve uygulama planı çıkarıldı, ardından onaylanan plan uygulandı. Sorumluluklar dört parçaya ayrıldı:

- **`core/models.py`** — `PageContent` ve `IngestedDocument` (frozen dataclass). Her sayfa kendi `document_id`, `file_name` ve `page_number` bilgisini taşır; böylece sonraki chunking aşamasında metadata yeniden birleştirilmek zorunda kalmaz.
- **`core/exceptions.py`** — `IngestionError` tabanlı hata hiyerarşisi (plana sonradan eklenen tek dosya). Arayüz katmanı ileride tek bir `except IngestionError` ile kullanıcıya anlaşılır mesaj gösterebilecek.
- **`interfaces/document_parser.py`** — İki üyeli bir sözleşme: `supported_extensions` ve `parse(path) -> [(sayfa_no, metin)]`.
- **`infrastructure/docling_parser.py`** — Docling implementasyonu.
- **`services/ingestion_service.py`** — Doğrulama → kimlik üretimi → parse → metadata.

Ana tasarım kararı, parser'ın **yalnızca metin çıkarması**, doğrulama ve metadata üretiminin ise servise ait olmasıdır. Böylece yeni bir parser yazan kişi uzantı kontrolü veya kimlik üretimiyle uğraşmaz ve servis, Docling yüklenmeden sahte bir parser ile saniyeler içinde test edilebilir. Tek implementasyon olduğu için factory/registry gibi ek soyutlamalar eklenmedi.

Docling API'si dokümantasyon özetlerine veya ezbere değil, kurulu sürümün (docling 2.138.0, docling-core 2.101.1) kaynak koduna bakılarak kullanıldı. Bu, aşağıdaki birkaç kararı doğrudan etkiledi.

### Kritik karar noktaları

#### 3. OCR Motoru: Tesseract → EasyOCR (Day 1 kararının revizyonu)
- **Değerlendirilen alternatifler:** Docling varsayılanı (`OcrAutoOptions`), RapidOCR, Tesseract (`tesserocr`/CLI), EasyOCR.
- **Bulgu:** Docling'in varsayılanı OCR motorunu ortamda ne kuruluysa ona göre seçiyor. Seçilebilecek motorlardan RapidOCR, çalıştırma başına **yalnızca tek dil** kullanıyor; birden fazla dil verilirse ilkini alıp gerisini uyarıyla yok sayıyor. Yani "Türkçe + İngilizce" gereksinimi varsayılan ayarlarla sessizce bozulabilirdi.
- **Tesseract neden bırakıldı:** Sistem seviyesinde kurulum ve `tur.traineddata` gerektiriyor. Bu, Windows'ta ve ileride Docker imajında ayrı bir kurulum adımı ve "bende çalışıyordu" riski demek.
- **Seçilen yaklaşım:** `EasyOcrOptions(lang=["tr", "en"])`, motor ve diller açıkça belirtildi. İki dil de Latin alfabesi kullandığı için aynı tanıma modelinde birlikte çalışıyor. Docling desteklenmeyen bir dili yapılandırma anında hata olarak bildiriyor; yanlış yapılandırma ilk belgede değil, uygulama açılırken fark ediliyor.
- **Ödünleşim:** EasyOCR, Docling'e ayrı bir ekstra (`docling[feat-ocr-easyocr]`) olarak ekleniyor ve torch bağımlılığı nedeniyle kurulum büyük.

#### 4. OCR Modu: Varsayılan mı, Tam Sayfa mı?
- **Alternatifler:** `OcrMode.DEFAULT` (PDF'in metin katmanı olan bölgeleri OCR'lanmaz) ve `OcrMode.FULL_PAGE` (her sayfa baştan sona OCR'lanır).
- **Seçilen yaklaşım:** `DEFAULT`. Metin katmanı olan dijital PDF'ler kayıpsız ve hızlı okunuyor, taranmış sayfalar OCR'lanıyor.
- **Gerekçe (ölçülerek doğrulandı):** `FULL_PAGE`, PDF'in metin katmanını tamamen atıp yalnızca OCR çıktısına güveniyor. Ayrıca teşhis sırasında bu modda kelime sırasının bozulduğu görüldü ("üç **gün** içinde açıklanacak" → "üç içinde açıklanacak **gün**"). Varsayılan modda sıra doğruydu.
- **Genişletilebilirlik:** Metin katmanı bozuk PDF'ler için `DoclingParser(force_full_page_ocr=True)` parametresi bırakıldı.

#### 5. `document_id`: İçerik Özeti mi, UUID mi?
- **Seçilen yaklaşım:** Dosya içeriğinin SHA-256 özeti.
- **Gerekçe:** Aynı dosya her yüklendiğinde aynı kimliği alır. İleride vektör veritabanında tekrar yüklemeleri tespit etmek kolaylaşır; dosya adı değişse bile kimlik değişmez. Dosya adı ayrıca metadata olarak saklanır.

#### 6. Sayfa Numaralarının Korunması
- Sayfa numaraları sayaçla üretilmiyor; Docling'in `document.pages` sözlüğünün anahtarlarından (1'den başlayan gerçek sayfa numaraları) alınıyor ve her sayfa `export_to_markdown(page_no=n)` ile ayrı dışa aktarılıyor.
- Metin içermeyen sayfalar listeden silinmiyor, boş metinle saklanıyor; böylece numaralar kaymıyor. Görseller tek sayfalık belge olarak `page_number=1` alıyor.

#### 7. Çıktı Formatı: Markdown mı, Düz Metin mi?
- **Seçilen yaklaşım:** Markdown. Başlık ve tablo yapısı RAG'de anlam taşıyor. Görsel yer tutucuları (`<!-- image -->`) gürültü olacağı için boş string ile değiştirildi.

#### 8. Hata Yönetimi
- Ucuz kontroller (dosya var mı, uzantı destekleniyor mu, dosya 0 bayt mı) parse'tan **önce**, serviste yapılıyor. Bu durumlarda pahalı Docling çağrısı hiç yapılmıyor.
- Docling `raises_on_error=False` ile çağrılıyor ve `ConversionStatus` kontrol ediliyor. `FAILURE`/`SKIPPED` durumları `DocumentParseError`'a çevriliyor, `PARTIAL_SUCCESS` ise uyarıyla kabul ediliyor. Docling'e özgü istisnalar servis katmanına sızmıyor; asıl hata `__cause__` olarak korunuyor.
- Hiç metin çıkmayan geçerli bir belge hata sayılmıyor; uyarı loglanıp karar üst katmana bırakılıyor.

#### 9. Test Stratejisi
- **Birim testleri:** Sahte parser ile, Docling yüklenmeden çalışıyor. Hızlı geri bildirim sağlıyor.
- **Entegrasyon testleri:** Gerçek Docling + EasyOCR ile çalışıyor ve `@pytest.mark.integration` ile ayrılmış durumda.
- Test dosyaları depoya konmuyor, fixture'lar tarafından çalışma anında üretiliyor. Böylece her testin neyi doğruladığı (hangi metin, hangi sayfada) kodda okunabiliyor.
- OCR çıktısı birebir sabit olmadığı için tam eşleşme yerine anahtar kelimeler kontrol ediliyor. Türkçe karakterlerin (ç, ğ, ı, ö, ş, ü) korunması ise ayrıca doğrulanıyor; dil yapılandırmasının işe yaradığının kanıtı bu.

#### 10. Model İndirme: Ayrı Kurulum Adımı
- **Problem:** Modeller ilk belge işlenirken indiriliyordu; ağ sorunu yaşanırsa bu, test veya ilk kullanım sırasında, nedeni belirsiz bir hata olarak ortaya çıkıyordu.
- **Değerlendirilen alternatifler:** Docling'in `docling-tools models download` aracı ve parser üzerinden pipeline'ları önceden başlatmak.
- **Neden `docling-tools` değil:** Modelleri ayrı bir klasöre indiriyor; Docling o klasörü ancak `artifacts_path` ile açıkça gösterilirse kullanıyor. Hem ek yapılandırma gerektiriyor hem de EasyOCR modellerini kapsamıyor.
- **Seçilen yaklaşım:** `DoclingParser.warm_up()`. Docling'in `initialize_pipeline()` metodunu PDF ve görsel formatları için çağırıyor. Kaynak koda bakılarak doğrulandı: pipeline kurulurken layout/tablo modelleri Hugging Face önbelleğine iniyor ve EasyOCR okuyucusu oluşturulurken tr/en modelleri indiriliyor. Modeller, çalışma anında kullanılan önbelleklerin aynısına iniyor. Bunu çağıran `scripts/download_models.py` betiği README'de kurulum adımı olarak yer alıyor.
- **Yan fayda:** İleride Streamlit açılışında `warm_up()` çağrılarak ilk kullanıcının model yüklemesini beklemesi önlenebilir.
- **Kapsam kararı:** `warm_up()` interface'e eklenmedi; yalnızca Docling'e özgü bir ihtiyaç.

#### 11. Tablo Testleri: Dijital ve Taranmış
- Case study tablolu belgeleri ayrıca sorduğu için iki test eklendi: aynı laboratuvar sonuç tablosunun metin katmanlı PDF hâli ve görüntüye çevrilmiş (metin katmanı olmayan) hâli.
- Dijital tabloda hücreler **birebir** kontrol ediliyor (`["Glukoz", "98", "mg/dL", "70 - 100"]`). Gerekçe: RAG'de "Glukoz kaç?" sorusunun doğru cevabı, değerin doğru satır ve sütunda kalmasına bağlı. Yalnızca kelimelerin varlığını kontrol etmek bunu yakalamazdı.
- Taranmış tabloda OCR küçük farklar üretebileceği için ("mg/dL" → "mg/dl") yalnızca tablo yapısı (4 satır) ve "Glukoz → 98" eşleşmesi kontrol ediliyor.
- Parser'da `do_table_structure=True` açıkça yazıldı. Varsayılanı zaten `True`, ama tablolar bu proje için önemli olduğundan davranış koddan okunabilir olmalı.

#### 12. Test Çıktısındaki Uyarılar: Hedefli Filtre
- Entegrasyon testleri 22 uyarı üretiyordu; hepsi üçüncü parti kütüphanelerden geliyordu (Docling, EasyOCR, torch). Bu gürültü, önemli bir mesajın (aşağıdaki access violation) gözden kaçmasına yol açabiliyordu.
- **Seçilen yaklaşım:** `pytest.ini` içinde her uyarı mesaj metniyle tek tek filtrelendi. Uyarıların tamamı kapatılmadı; projeye ait ya da yeni bir uyarı görünmeye devam ediyor. Filtreler, aynı uyarıları üreten bir deneme testiyle doğrulandı (bilinen beşi gizlendi, yeni bir uyarı göründü).

### Karşılaşılan sorunlar

#### Hugging Face'ten model indirilemedi
Docling'in layout modelleri ilk çalıştırmada Hugging Face'ten indiriliyor ve indirme başarısız oldu. Terminal oturumu için `HF_HUB_ENABLE_HF_TRANSFER=0`, `REQUESTS_CA_BUNDLE=""` ve `CURL_CA_BUNDLE=""` tanımlanarak geçici olarak aşıldı. `CURL_CA_BUNDLE=""` bazı ortamlarda SSL doğrulamasını devre dışı bıraktığı için bu kalıcı bir çözüm olarak kabul edilmedi. Kök neden ayrıca incelendi (bkz. aşağıdaki not).

> **Kök neden ve kalıcı çözüm:** Sorun yeniden üretilemedi. Yeni bir terminalde ağ ve SSL ile ilgili ortam değişkenleri kontrol edildi (tanımlı değişken yok) ve model, Docling'in kendi aracıyla (`docling-tools models download layout`) hiçbir geçici ayar olmadan başarıyla indirildi. İlk hata büyük olasılıkla geçici bir ağ veya servis sorunuydu; ancak ilk hata mesajı kaydedilmediği için kesin neden belirlenemedi. Geçici değişkenlerin sorunu çözdüğü kanıtlanamadığı için kurulum talimatlarına eklenmedi. Bunun yerine model indirme, testlerden önce çalıştırılan ayrı ve açık bir kurulum adımı yapıldı (`python -m scripts.download_models`, bkz. Karar 10); böylece bir ağ sorunu test sırasında değil, kurulumda ve anlaşılır bir mesajla görünür. **Ders:** Hata çıktısını, çözümü denemeden önce kaydetmek.

#### Taranmış PDF'in 2. sayfası boş geliyordu
Bu, günün en öğretici sorunu oldu. Çözüme giden yol düz bir çizgi değildi, bu yüzden adım adım kaydediyorum.

1. **Belirti:** İki sayfalık taranmış PDF testinde sayfa 1'den Türkçe metin doğru okunuyor, ancak sayfa 2 boş string dönüyordu. Sayfa 1'in doğru okunması OCR'ın ve Türkçe dil yapılandırmasının çalıştığını zaten gösteriyordu.
2. **Deneme-yanılma (işe yaramadı):** `force_full_page_ocr=True`, görüntüleri RGB'ye çevirme ve PDF'i fpdf ile yeniden üretme denendi. Hiçbiri sonucu değiştirmedi. Ders: hipotez ölçülmeden yapılan değişiklikler hangi değişkenin etkili olduğunu bulanıklaştırıyor. Bu değişiklikler geri alındı.
3. **Teşhis 1:** Belgedeki tüm öğeler, içerik katmanı filtresi ve görsel içi traversal kapalı olarak listelendi. Sonuç: `status=SUCCESS`, hata yok, ama sayfa 2'ye ait **hiçbir** öğe yok.
4. **Yanlış hipotez:** "Varsayılan modda OCR yalnızca layout modelinin bulduğu bölgeleri okuyor; layout sayfa 2'de bölge bulamadı." Kaynak kod bu mekanizmanın var olduğunu gösteriyordu. Ancak `FULL_PAGE` ile denendiğinde sonuç değişmedi ve hipotez çürüdü.
5. **Teşhis 2 (belirleyici):** Tek bir betikle birkaç olasılık aynı anda ayrıştırıldı. Dört kontrollü PDF (TR-EN, EN-TR, TR-TR, yalnızca EN) üretildi, Docling'in OCR'a verdiği sayfa görüntüleri kaydedildi ve EasyOCR bu görüntülerde doğrudan çalıştırıldı. Sonuçlar:
   - Docling sayfa 2'yi doğru render ediyordu ve EasyOCR bu görüntüyü kusursuz okuyordu.
   - EN-TR PDF'inde sayfa 1'in metni `"...payment due date is next friday hastan..."` diye bitiyordu: **sayfa 2'nin ilk satırı sayfa 1'e eklenmişti.**
6. **Kök neden:** Docling'in reading order aşaması, sayfa sonunda bitmemiş görünen bir paragrafı bir sonraki sayfanın başıyla tek öğede birleştiriyor (`predict_merges` → `_merge_elements`). Birleşen öğe iki sayfa kaydı taşıyor, ancak sayfa bazlı dışa aktarma docling-core serializer'ında yalnızca **ilk** kayda (`item.prov[0].page_no`) bakıyor. Sentetik test metinlerinde büyük harf ve nokta olmadığı için Docling her sayfa geçişini "cümle devam ediyor" olarak yorumluyordu. Metin hiçbir zaman kaybolmuyordu, yanlış sayfaya yazılıyordu.
7. **Çözüm:** Fixture metinleri gerçekçi cümlelere (büyük harfle başlayan, noktayla biten) çevrildi ve test geçti. Davranış, parser'da "bilinen sınırlama" olarak belgelendi.
8. **Değerlendirilen alternatif:** Birleşmiş öğeleri `prov` kayıtlarındaki `charspan` aralıklarına göre bölüp her parçayı kendi sayfasına yazmak. Bu tam doğru sayfa ataması sağlar, ancak `export_to_markdown` yerine kendi serializer'ımızı yazmayı ve tablo/başlık biçimlendirmesini yeniden kurmayı gerektirir. MVP için ertelendi; sayfa atıfları kritik hâle gelirse yeniden değerlendirilecek.

#### Test fixture'larında fpdf2 hataları
Tablolu PDF fixture'ı, kullanıcı ortamına verilmeden önce geliştirme ortamında çalıştırıldı ve iki hata yakalandı. Birincisi: fpdf2'de art arda `multi_cell` çağrıldığında imleç satırın sağında kalıyordu ve ikinci satır yer bulamıyordu (`new_x="LMARGIN", new_y="NEXT"` ile çözüldü). İkincisi: tablo başlıkları varsayılan olarak kalın yazılıyor ve ayrı bir kalın font dosyası gerektiriyordu. Kalın font dosyasının adı işletim sistemine göre değiştiği için başlıkların kalın yazılması kapatıldı. Ders: test verisi üreten kodu da test etmek; aksi halde hata, asıl testi çalıştıran kişinin ortamında ortaya çıkıyor.

#### Docling kurulu değilken birim testleri toplanamıyordu
`pytest -m "not integration"` bile `test_docling_parser.py` dosyasını import ettiği için, Docling kurulu olmayan bir ortamda toplama aşamasında hata veriyordu. `pytest.importorskip("docling")` ile entegrasyon modülü bu durumda atlanıyor; birim testleri Docling'den bağımsız olarak çalışıyor.

#### Tablo testinde aralıklı "Windows fatal exception: access violation"
- **Gözlem:** Üç çalıştırmanın ikisinde, her seferinde aynı testte (`test_pdf_table_is_exported_with_rows_and_columns`) görüldü. Test her seferinde geçti; süreç hiç çökmedi.
- **Analiz:** Mesaj pytest'in `faulthandler` eklentisinden geliyor. Windows'ta `faulthandler`, yerel (C/C++) bir kütüphanede oluşan istisnayı kütüphanenin kendi hata yakalayıcısından önce görüyor; bu yüzden kütüphanenin kendi içinde yakalayıp toparladığı bir istisna da bu mesajı üretebiliyor. Thread dökümüne göre mesaj anında hiçbir Python kodu çalışmıyordu: Docling'in tüm pipeline thread'leri iş bekliyordu ve hatayı veren thread Python karşılığı olmayan yerel bir thread'di. Mesajın çıktığı çalıştırmalarda da tablo hücreleri birebir doğru çıktı.
- **Karar:** Daha fazla daraltılmadı. Hangi kütüphanenin tetiklediği bulunsa bile hata üçüncü parti yerel kodda ve çıktı doğru; yani hiçbir sonuç proje kodunda yapılacak bir değişikliğe yol açmıyordu. Araştırmanın sınırı, sonucun aksiyonu değiştirip değiştirmeyeceğine göre kondu.
- **Bilinçli olarak yapılmayan:** Mesaj `-p no:faulthandler` ile gizlenmedi. Bu ayar, gerçek bir çökme olursa elimizdeki tek teşhis bilgisini de yok ederdi.
- **Ne zaman yeniden ele alınacak:** Bir çalıştırmada süreç çökerse veya tablo çıktısı yanlış çıkarsa.

#### Torch CPU üzerinde çalışıyor
Test çıktısındaki `'pin_memory' ... no accelerator is found` uyarısı, Docling ve EasyOCR'ın GPU yerine CPU'da çalıştığını gösteriyor. Windows'ta PyPI'dan kurulan torch varsayılan olarak CPU sürümü. İşlevsel bir sorun değil, ancak büyük belgelerde süreyi etkiler. Açık madde olarak not edildi.

### Yapılan işlemler
- [x] Mimari ve uygulama planı hazırlandı, onaylandı.
- [x] Veri modelleri, hata hiyerarşisi, parser sözleşmesi, Docling parser'ı ve ingestion servisi yazıldı.
- [x] Türkçe/İngilizce OCR yapılandırması (EasyOCR) açıkça tanımlandı.
- [x] Birim testleri (12) ve entegrasyon testleri (9) yazıldı. 21 testin tamamı Windows'ta geçiyor.
- [x] Taranmış PDF sayfa atama sorununun kök nedeni bulundu ve belgelendi.
- [x] Hugging Face indirme sorunu incelendi; model indirme ayrı bir kurulum adımı yapıldı (`warm_up()` + `scripts/download_models.py`).
- [x] Dijital ve taranmış tablo testleri eklendi; ikisi de geçiyor.
- [x] Test çıktısındaki üçüncü parti uyarıları hedefli olarak filtrelendi.
- [x] README kurulum, test ve sorun giderme bölümü yazıldı.
- [x] `TESTING.md` yazıldı ve güncellendi.
- [ ] Gerçek (sentetik olmayan) taranmış belgelerle doğrulama
- [ ] README'deki kurulum adımlarının boş bir ortamda baştan sona denenmesi
- [ ] GPU'lu torch kurulumunun değerlendirilmesi

### Öğrenilenler
- Bir kütüphanenin "varsayılan" davranışı gereksinimle örtüşmeyebilir (OCR motorunun tek dile düşmesi). Kritik gereksinimler yapılandırmada açıkça ifade edilmeli.
- Hata ayıklarken tahmine dayalı değişiklik yapmak yerine, birden fazla hipotezi aynı anda ayıran kontrollü bir deney kurmak çok daha hızlı sonuç verdi.
- Test fixture'ları gerçek veriye benzemeli. Noktalamasız sentetik metinler, gerçek belgelerde nadir görülen bir davranışı tetikledi ve yanlış yöne bakmamıza yol açtı.
- Bir testin başarısız olması her zaman kodun yanlış olduğu anlamına gelmez; ama testi değiştirmeden önce bunun kanıtlanması gerekir.
- Rahatsız edici bir mesajı gizlemek yerine anlamak gerekir; ama araştırmanın ne zaman duracağını, sonucun yapılacak işi değiştirip değiştirmeyeceği belirler.

### Zaman dağılımı
_Doldurulacak._ (Planlama, kodlama, Docling kaynak kodu incelemesi, teşhis süreci, dokümantasyon)

### Baştan başlasaydım
- Test fixture'larını en baştan gerçekçi cümlelerle yazardım.
- İlk başarısız testte, değişiklik denemeden önce doğrudan teşhis betiğiyle başlardım.
