# Development Log

**Proje:** Belge Analiz ve Soru-Cevap (RAG) · **Dönem:** 13–19 Ekim 2026  
Bu günlük her teknik denemeyi değil, **kararları, önemli hataları, çözümleri ve öğrenilenleri** özetler.

## Day 1 · 13 Ekim — Ortam ve mimari

**Yapılanlar:** Python 3.11 sanal ortamı, Git ve Ollama `qwen3:4b-instruct` kuruldu; RTX 3060 üzerinde modelin GPU'da çalıştığı doğrulandı. Python + Streamlit + Docling/OCR + BGE-M3 + ChromaDB + Ollama mimarisi seçildi.

**Karar:** Büyük bir modeli eğitmek yerine yerel LLM ve RAG; bağımlılıklar arayüzler üzerinden ayrılacak. **Sorun:** PowerShell çalıştırma politikası ve Windows GPU bellek göstergeleri; `ollama ps` ile GPU tahsisi kontrol edildi.

## Day 2 · 14 Ekim — Belge işleme

**Yapılanlar:** PDF/JPG/PNG parser, ingestion servisi, sayfa metadata'sı, SHA-256 belge kimliği ve hata yönetimi. Metin Markdown olarak çıkarılıyor. **12 birim + 9 entegrasyon testi** geçti.

**Kararlar ve gerekçeler:**
- Tesseract yerine **EasyOCR (`tr`, `en`)**: iki dil açıkça ayarlanıyor; ayrı sistem OCR kurulumu azaltılıyor.
- Dijital PDF'de metin katmanını korumak için varsayılan OCR modu; tam sayfa OCR bazı kelimelerin sırasını bozdu.
- Parser metni çıkarıyor, servis dosyayı doğrulayıp kimlik/metadata üretiyor. Tablolar Markdown yapısında korunuyor.

**Önemli hata:** Taranmış PDF'in ikinci sayfası boş görünüyordu. Kontrollü deney, Docling'in sayfalar arası paragrafı birleştirip önceki sayfaya atadığını gösterdi. Sentetik fixture cümleleri gerçekçi noktalama ile düzeltildi; **sayfa atıf kayması bilinen sınırlama** olarak bırakıldı. Hugging Face indirme sorunu yeniden üretilemedi; modeller için ön indirme betiği eklendi.

**Öğrenilen:** Test verisinin gerçekçiliği ve hatayı hipotezlerle izole etmek, rastgele ayar değiştirmekten daha etkili.

## Day 3 · 15 Ekim — Chunking, embedding, retrieval

**Yapılanlar:** Sayfa ve tablo duyarlı Markdown chunker (500 token; 75 overlap), BGE-M3, kalıcı ChromaDB, belge filtresi ve indeks yaşam döngüsü. O tarihte **73/73 test** geçti. Sentetik 7/7 alakalı soruda doğru sayfa ilk sıradaydı.

**Kararlar:** Chunk boyutu BGE-M3 tokenizer'ıyla ölçülüyor; uzun tablolar parçalanırken sütun başlığı yineleniyor. Koleksiyonun model/boyut/chunker ayarları açılışta doğrulanıyor; aynı belge tekrar indekslenmiyor, yarım indeks geri alınıyor. Belge filtresi zorunlu; küçük örneklem nedeniyle benzerlik eşiği konmadı.

**Önemli bulgular:**
- `docling[feat-ocr-easyocr]` kurulumu hatalıydı; doğru paket **`docling[easyocr]`** olarak düzeltildi.
- ChromaDB mevcut koleksiyonda değişen metadata'yı sessizce koruyordu; açık yapılandırma kontrolü eklendi.
- İlk chunker sürümü overlap'i düşürüyordu; testle yakalanıp bütçe hesabı düzeltildi.
- CUDA'lı torch indirme denemesi geliştirme diskini doldurdu; CPU çözümü korundu. **Ölçüm: 1,23 chunk/sn.**

**Öğrenilen:** Mutasyon testleri korumaların gerçekten sınandığını gösterdi; ölçüm olmadan optimizasyon yapılmadı.

## Day 4 · 18 Ekim — LLM ve Streamlit MVP

**Yapılanlar:** Ollama adaptörü, soru-cevap servisi, JSON şemalı yanıt ve kaynak ID doğrulaması; Streamlit belge yükleme/seçme/sohbet ekranı ve oturum izolasyonu. Ağır modeller yeniden yüklenmesin diye cache kullanıldı.

**Koruma yaklaşımı:** Boş retrieval'da LLM çağrılmıyor; belge içindeki talimatlar veri kabul ediliyor; kaynak ID'leri kodla kontrol ediliyor; kaynak olmadan yanıt gösterilmiyor. **Bunlar halüsinasyonu tamamen ortadan kaldırmaz.**

**Önemli denemeler ve sonuçlar:**
- Windows'ta uzun pytest parametresi ortam değişkeni sınırını aştı; test verisi test içinde oluşturularak düzeltildi.
- Türkçe soruya İngilizce cevap veriliyordu; cevap dili prompt'ta açıklandı.
- Türkçe soru → İngilizce belgede göreli tarih eşleştirmesi başarısız veya hatalı çeviri üretti; test **`xfail`** olarak korundu.
- Gerçek **Parol 500 mg KÜB** dosyasıyla Streamlit'te 19 soru: **15 doğru (10 cevap + 5 ret), 4 sorunlu**. Model bazen “dikkatli kullanılmalı”yı “kullanılmamalı”ya çevirdi, “tıbbi tavsiye olmadıkça” şartını düşürdü ve bazı etkileşimleri atladı. Prompt ile yasak/uyarı ayrımı kısmen iyileşti; başka hatalar sürdü ve ikinci test `xfail` kaldı. Kullanıcıya kaynak metnini doğrulama uyarısı eklendi.

**Öğrenilen:** Kaynak ID'sinin doğru olması, **kaynağın doğru aktarıldığı** anlamına gelmiyor. Gerçek belgeler sentetik testlerin yakalamadığı hataları gösterdi.

## Day 5 · 19 Ekim — Teslimat hazırlığı

**Yapılanlar:** Statik analiz temizlendi; Git'te hassas dosya, model, indeks ve büyük dosya tarayan `release_check` eklendi ve kendi testleriyle sınandı. README ve Docker/Compose taslakları hazırlandı.

**Doğrulama sınırı:** Son geliştirme ortamında Linux/Python 3.12 üzerinde **166 test geçti, 12 test atlandı** (ağır modeller/Ollama yok). **Son kod Windows'ta yeniden test edilmedi.** Docker yapılandırması yazıldı ancak imaj derlenmedi/çalıştırılmadı. Bunlar tamamlanmış olarak gösterilmiyor.

## Genel değerlendirme

**İşe yarayanlar:** Önce planlama; kütüphane davranışlarını ölçerek doğrulama; mutasyon testleri; gerçek belgeyle soru-cevap denemesi; hata ve sınırlamaları saklamama.

**Baştan başlasaydım:** Gerçek belge testlerini ve temiz ortam kurulumu doğrulamasını daha erken yapardım; Windows/Linux farklarını başta kontrol ederdim; kaynakların yalnızca kimliğini değil iddia düzeyinde doğruluğunu da sınayan bir yöntem planlardım.

**Açık sınırlamalar:** Kaynak anlamının yanlış aktarılması, iki dil arasında göreli tarih, takip sorusu bağlamının olmaması, CPU embedding yavaşlığı, gerçek düşük kaliteli OCR testlerinin eksikliği, bazı sayfa atfı hataları, doğrulanmamış Docker.

**Zaman kayıtları:** Gerçek saatler ölçülmediği için sayı eklenmedi. Günlük çalışmaların kapsamı yukarıda yer alıyor.
