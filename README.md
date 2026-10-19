# Belge Analiz ve Soru-Cevap Sistemi (Document RAG)

PDF, JPG ve PNG dosyalarını yükleyip Türkçe/İngilizce soru sorabileceğiniz **yerel bir RAG MVP'si**. Yanıtlar seçili belgelerden getirilen metinlere dayanır; ilgili dosya, sayfa ve kaynak metni gösterilir. Kaynak doğrulaması hatalı aktarımı tamamen önlemez (bkz. [TESTING.md](TESTING.md)).

## Özellikler ve mimari

- **Belge işleme:** Docling + EasyOCR (`tr`, `en`); dijital/taranmış PDF ve görseller, Markdown tablo çıkarımı.
- **Arama:** Sayfa sınırını koruyan Markdown chunker (en fazla 500 token, 75 overlap), BAAI/bge-m3 ve kalıcı ChromaDB.
- **Cevap:** Seçili belgelerde `top-5` retrieval → Ollama / Qwen3 4B Instruct → kaynak kimliği doğrulaması.
- **Arayüz:** Streamlit ile dosya yükleme, belge seçimi, sohbet ve kaynak gösterimi. Boş retrieval'da LLM çağrılmaz.

```text
PDF/JPG/PNG → Docling/EasyOCR → Markdown → Chunker → BGE-M3 → ChromaDB
Soru → BGE-M3 → seçili belge filtresi → Qwen3 (Ollama) → kaynak kontrolü → yanıt
```

Kod: `app/core` (modeller/ayarlar), `app/interfaces` (sözleşmeler), `app/infrastructure` (adaptörler), `app/services` (iş akışı), `app/ui` (yükleme), `streamlit_app.py` (arayüz).

## Kurulum ve çalıştırma (Windows / PowerShell)

**Gereksinimler:** Python 3.11, [Ollama](https://ollama.com/download), önerilen 16 GB RAM ve yaklaşık 10 GB boş disk. İlk kurulumda internet gerekir. GPU zorunlu değildir; OCR ve embedding CPU'da çalışacak şekilde yapılandırılmıştır.

```powershell
git clone <repository-url> document-rag
cd document-rag
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pip check
ollama pull qwen3:4b-instruct
python -m app.scripts.download_models
streamlit run streamlit_app.py
```

Ollama uygulaması çalışıyor olmalıdır. PowerShell aktivasyon izni sorununda yalnızca mevcut oturum için `Set-ExecutionPolicy -Scope Process Bypass` kullanılabilir. Tarayıcıda PDF/JPG/PNG yükleyin, **Belgeleri işle**'yi seçin, ardından belgeyi işaretleyip sorunuzu yazın. Dosya sınırı **25 MB**; veri ve indeks `data/` altındadır. Her soru bağımsız yanıtlanır; sohbet geçmişi modele iletilmez.

## Test ve teslimat kontrolü

```powershell
pytest -m "not integration" -q
pytest -m integration -q
python -m app.scripts.release_check --run-tests
```

**Son kodun Windows testleri henüz doğrulanmış olarak raporlanmadı.** Test sayıları, gerçek belge denemesi ve bilinen hatalar: [TESTING.md](TESTING.md). Tasarım ve geliştirme kararları: [DEVLOG.md](DEVLOG.md).

## Yapılandırma

| Değişken | Varsayılan |
|---|---|
| `RAG_OLLAMA_HOST` | `http://localhost:11434` |
| `RAG_LLM_MODEL` | `qwen3:4b-instruct` |
| `RAG_EMBEDDING_DEVICE` | `cpu` |
| `RAG_CHROMA_PATH` | `data/chroma` |
| `RAG_UPLOAD_DIR` | `data/uploads` |

Uygulama `.env` dosyasını otomatik okumaz; değişkenleri işletim sisteminde ayarlayın. Model veya chunk ayarları değiştiğinde eski indeksi bilinçli şekilde sıfırlayın:

```powershell
python -m app.scripts.search_documents --reset-index
```

## Bilinen sınırlamalar

- Küçük LLM kaynak metnindeki **uyarı/yasak/şart** ayrımını yanlış aktarabiliyor. Özellikle tıbbi içerikte kaynak metni kontrol edin; bu uygulama tıbbi karar destek sistemi değildir.
- Türkçe soru → İngilizce belgede göreli tarihlerin aktarımı hatalı olabiliyor; takip soruları önceki sohbeti kullanmıyor.
- Gerçek, düşük kaliteli taramalarda OCR ölçülmedi. CPU embedding yaklaşık **1,23 chunk/sn**.
- Docker dosyaları mevcut fakat **derlenip çalıştırılarak doğrulanmadı**. Resmî başlangıç yolu Windows yerel kurulumudur.

Docker denemesi: `docker compose build` → `docker compose run --rm app python -m app.scripts.download_models` → `docker compose up`. Ollama ana makinede çalışır; konteyner bağlantısı için ek ağ ayarı gerekebilir. Ayrıntılı hata/gerekçeler için [TESTING.md](TESTING.md).
