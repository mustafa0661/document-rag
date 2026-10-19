# Belge Analiz ve Soru-Cevap Sistemi (Document RAG)

PDF, JPG ve PNG belgelerini yükleyip bu belgeler hakkında Türkçe veya İngilizce doğal dilde soru sorabileceğiniz, tamamen yerel çalışan bir RAG (Retrieval-Augmented Generation) uygulaması. Cevaplar **yalnızca seçili belgelerden** üretilir ve her cevabın altında dayandığı dosya, sayfa ve metin gösterilir. Belgede olmayan bir bilgi sorulduğunda sistem bunu açıkça söyler.

> Geliştirme süreci, alınan kararlar ve denenip vazgeçilen yaklaşımlar için [DEVLOG.md](DEVLOG.md); test senaryoları, gerçek sonuçlar ve bilinen sınırlamalar için [TESTING.md](TESTING.md).

## Özellikler

- **Belge işleme:** Docling ile PDF, JPG ve PNG okuma. Taranmış sayfalar ve görseller için EasyOCR (Türkçe + İngilizce). Tablolar Markdown tablosu olarak korunur.
- **Arama:** Sayfa sınırını aşmayan, başlık ve tablo yapısını koruyan chunk'lar; BAAI/bge-m3 ile çok dilli embedding; ChromaDB'de kalıcı indeks.
- **Cevaplama:** Ollama üzerinde Qwen3 4B Instruct. Cevaplar yapılandırılmış JSON olarak üretilir; modelin gösterdiği kaynaklar kodla doğrulanır.
- **Halüsinasyona karşı katmanlı koruma:** İlgili bölüm bulunamazsa model hiç çağrılmaz. Kaynak kimlikleri şema ve kod düzeyinde doğrulanır; geçerli kaynağa dayanmayan cevap gösterilmez; belge içindeki talimatlar talimat olarak işlenmez.
- **Arayüz:** Streamlit. Belge yükleme, işleme durumu, belge seçimi, sohbet ve kaynak gösterimi.

## Mimari

```
Yükleme ─▶ Docling + EasyOCR ─▶ sayfa bazlı Markdown ─▶ Markdown chunker (≤500 token, 75 overlap)
                                                                 │
                                                       BGE-M3 embedding ─▶ ChromaDB (kalıcı)
                                                                 │
Soru ─▶ BGE-M3 ─▶ seçili belgelerde arama (top-5) ─▶ bağlam ─▶ Qwen3 4B (Ollama, JSON) ─▶ kaynak doğrulama ─▶ cevap + kaynaklar
```

Kod katmanları: `app/core` (modeller, ayarlar, hatalar) · `app/interfaces` (soyut sözleşmeler) · `app/infrastructure` (Docling, BGE-M3, ChromaDB, Ollama) · `app/services` (iş akışları) · `app/ui` (yükleme güvenliği) · `streamlit_app.py` (arayüz). Servisler yalnızca arayüzleri tanır; dış kütüphaneler `infrastructure` katmanında izole edilmiştir.

## Gereksinimler

| | |
|---|---|
| İşletim sistemi | Windows 10/11 (doğrulanmış). Linux/macOS komutları aşağıda; bu sistemlerde uçtan uca denenmedi. |
| Python | 3.11 |
| Ollama | [ollama.com/download](https://ollama.com/download) |
| Bellek | 16 GB RAM önerilir |
| Disk | ~10 GB (Python paketleri, torch ve modeller) |
| İnternet | Yalnızca ilk kurulumda (paketler ve modeller) |

GPU gerekmez. Embedding ve OCR CPU'da çalışır (bkz. [Bilinen sınırlamalar](#bilinen-sınırlamalar)).

## Kurulum (resmî ve doğrulanmış yöntem: yerel Windows)

```powershell
git clone <repository-url> document-rag
cd document-rag

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip check
```

PowerShell sanal ortamı etkinleştirmeye izin vermezse bir kez şu komutu çalıştırın: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

**LLM modeli** (Ollama uygulaması açık olmalı):

```powershell
ollama pull qwen3:4b-instruct
```

**Belge işleme ve embedding modelleri** (ilk seferde birkaç dakika sürer, ~3 GB):

```powershell
python -m app.scripts.download_models
```

**Kurulumun doğrulanması:**

```powershell
pytest -m "not integration" -q
```

Linux/macOS'ta etkinleştirme komutu `source .venv/bin/activate`; diğer komutlar aynı.

## Çalıştırma

```powershell
streamlit run streamlit_app.py
```

Tarayıcıda açılan sayfada:
1. Soldan PDF, JPG veya PNG dosyalarını seçip **Belgeleri işle**'ye basın. İşleme durumu adım adım gösterilir.
2. İşlenen belgeler listelenir. Soru sormak istediğiniz belgeleri işaretleyin; hiç belge seçili değilse soru sorulamaz.
3. Sorunuzu yazın. Cevabın altındaki **Kaynaklar** bölümünde dosya adı, sayfa ve ilgili metin görünür.

Notlar:
- İlk açılışta modeller yüklenir (1–2 dakika); sonraki etkileşimlerde yeniden yüklenmez.
- Aynı içerikli bir dosya tekrar yüklenirse yeniden işlenmez ve ilk yüklendiği adla gösterilir.
- En fazla 25 MB'lık dosyalar kabul edilir. Yüklenen dosyalar ve indeks `data/` altında saklanır.
- Her soru bağımsız cevaplanır; sohbet geçmişi modele gönderilmez.

## Komut satırı araçları

| Komut | Ne yapar |
|---|---|
| `python -m app.scripts.inspect_document belge.pdf` | Yalnızca metin çıkarımını gösterir; tam çıktı `inspect_out/` altına yazılır |
| `python -m app.scripts.search_documents belge.pdf -q "soru"` | Belgeyi indeksler ve soruya en yakın bölümleri mesafeleriyle listeler (LLM kullanmaz) |
| `python -m app.scripts.search_documents --reset-index` | Ana indeksi siler (model veya chunk ayarı değiştiyse gerekir) |
| `python -m app.scripts.evaluate_retrieval` | `eval/retrieval_eval.json` soru setiyle Hit@1, Hit@5, MRR ve eşik taraması raporu üretir (bkz. [eval/README.md](eval/README.md)) |
| `python -m app.scripts.release_check --run-tests` | Teslimat öncesi repository denetimi (commit edilmiş hassas dosyalar, `.gitignore`, bağımlılık uyumu, testler) |

## Yapılandırma

Ayarlar `app/core/config.py` içindedir. Makineye göre değişenler ortam değişkeniyle verilebilir (örnek: [.env.example](.env.example)). Uygulama `.env` dosyasını otomatik okumaz; değişkenleri ortamda tanımlayın, örneğin `$env:RAG_OLLAMA_HOST = "http://localhost:11434"`.

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `RAG_OLLAMA_HOST` | `http://localhost:11434` | Ollama adresi |
| `RAG_LLM_MODEL` | `qwen3:4b-instruct` | Ollama model adı; kod değişmeden başka bir model denenebilir |
| `RAG_EMBEDDING_DEVICE` | `cpu` | `cuda` (CUDA destekli torch kuruluysa) |
| `RAG_CHROMA_PATH` | `data/chroma` | Vektör indeksi klasörü |
| `RAG_UPLOAD_DIR` | `data/uploads` | Yüklenen dosyaların klasörü |

Model ve chunk ayarları indeksin kimliğinin parçasıdır. Bu ayarlar değişirse mevcut indeks kullanılmaz ve açık bir hata verilir (`--reset-index` ile yeniden oluşturulur). Böylece farklı bir modelle üretilmiş vektörler yanlışlıkla aranmaz.

## Testler

```powershell
pytest -m "not integration" -v      # Birim ve arayüz testleri: model gerektirmez
pytest -m integration -v -s         # Gerçek Docling, EasyOCR, BGE-M3 ve Ollama
```

Entegrasyon testleri modellerin indirilmiş ve Ollama'nın çalışıyor olmasını gerektirir; Ollama kapalıysa ilgili testler atlanır. Sonuçlar, örnek cevaplar ve bilinen sınırlamalar: [TESTING.md](TESTING.md).

## Proje yapısı

```
app/
  core/            veri modelleri, ayarlar, hata sınıfları
  interfaces/      DocumentParser, TextChunker, EmbeddingProvider, VectorStore, LlmProvider
  infrastructure/  Docling, Markdown chunker, BGE-M3, ChromaDB, Ollama
  services/        ingestion, indexing, retrieval, soru-cevap (+ prompt)
  ui/              yükleme doğrulama ve işleme (Streamlit'ten bağımsız)
  scripts/         komut satırı araçları
  bootstrap.py     bileşenlerin bağlandığı tek yer
streamlit_app.py   arayüz
tests/             birim, arayüz ve entegrasyon testleri
eval/              gerçek belgelerle retrieval değerlendirmesi
```

## Docker (deneysel, doğrulanmadı)

Depoda bir `Dockerfile` ve `docker-compose.yml` bulunur, ancak **geliştirme sırasında derlenip çalıştırılarak doğrulanmamıştır**. Resmî yöntem yukarıdaki yerel kurulumdur. Denemek isterseniz:

```powershell
docker compose build
docker compose run --rm app python -m app.scripts.download_models
docker compose up      # http://localhost:8501
```

- Ollama konteynerde değil, ana makinede çalışır; konteyner ona `host.docker.internal:11434` üzerinden bağlanır. Ollama yalnızca `127.0.0.1` üzerinden dinliyorsa konteyner bağlanamayabilir. Bu durumda Windows'ta `OLLAMA_HOST=0.0.0.0` ortam değişkenini tanımlayıp Ollama'yı yeniden başlatmak gerekebilir; bunun Ollama'yı ağdaki diğer cihazlara da açacağını unutmayın.
- İndeks ve yüklenen dosyalar `./data`, modeller `models` volume'ünde kalıcıdır.
- İmaj CPU sürümü torch kullanır. `env_file` sözdizimi Docker Compose 2.24 veya üstünü gerektirir.

## Bilinen sınırlamalar

Ayrıntılar ve ölçümler için bkz. [TESTING.md](TESTING.md).

- **Kaynağın yanlış aktarılması:** Model uydurma bilgi eklemez, ancak kaynaktaki bir ifadenin kesinlik derecesini değiştirebilir. Örneğin "dikkatli kullanılmalıdır" ifadesini "kullanılmamalıdır" diye aktarabilir veya "tıbbi tavsiye olmadıkça" gibi bir şartı düşürebilir. Arayüz bu nedenle her cevabın altında kaynakla doğrulama uyarısı gösterir. **Sistem tıbbi karar destek aracı değildir.**
- **Türkçe soru ile İngilizce belge:** 4B model, cevabı reddedebilir veya göreli ifadeleri yanlış çevirebilir. İngilizce soru ile Türkçe belge çalışır.
- **Bağlam takibi yok:** "Peki çocuklarda?" gibi takip soruları önceki soruyu bilmeden cevaplanır.
- **Benzerlik eşiği yok:** Gerçek belgelerle ölçüm yapılmadığı için retrieval'da eşik uygulanmaz; cevaplanabilirlik kararını model ve kaynak doğrulaması verir.
- **Performans:** Embedding CPU'da yaklaşık 1,2 chunk/sn hızında; büyük belgelerin işlenmesi dakikalar sürebilir.
- **OCR:** Yalnızca temiz, sentetik görsellerle test edildi; düşük kaliteli taramalar ve el yazısı ölçülmedi.

## Sorun giderme

**"Ollama'ya bağlanılamadı" / "model Ollama'da yüklü değil"**
Ollama uygulamasının açık olduğundan emin olun (veya `ollama serve`). Model yüklü değilse: `ollama pull qwen3:4b-instruct`. Uygulama bu durumda çökmez; Ollama açıldıktan sonra soruyu tekrar sorabilirsiniz.

**Model indirme başarısız oluyor**
1. Hata çıktısının tamamını kaydedin.
2. `huggingface.co` ve `github.com` adreslerine erişimi kontrol edin.
3. `python -m app.scripts.download_models` komutunu tekrar çalıştırın; yarım kalan indirmeler kaldığı yerden devam eder.
4. Hız sınırına takılıyorsanız `HF_TOKEN` ortam değişkenine ücretsiz bir Hugging Face erişim anahtarı tanımlayın.
5. Kurum ağında `CERTIFICATE_VERIFY_FAILED` hatası alırsanız SSL doğrulamasını kapatmayın; kurumun kök sertifikasının tanıtılması gerekir (BT ekibinize danışın).

**`IndexConfigMismatchError`**
İndeks farklı bir model veya chunk ayarıyla oluşturulmuş. `python -m app.scripts.search_documents --reset-index` ile silip belgeleri yeniden yükleyin.

**Windows uyarıları:** Hugging Face'in "symlinks" uyarısı ve torch'un `no accelerator is found` uyarısı zararsızdır.
