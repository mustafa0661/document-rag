# Hızlı Kurulum (Windows / PowerShell)

**Gereksinimler:** Python 3.11, Ollama, yaklaşık 10 GB boş disk ve ilk kurulum için internet. Ayrıntılar ana [README.md](README.md) dosyasında.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
ollama pull qwen3:4b-instruct
python -m app.scripts.download_models
streamlit run streamlit_app.py
```

Ollama uygulaması açık olmalı. Uygulamada PDF/JPG/PNG yükleyin → **Belgeleri işle** → belge seçin → soru sorun. Kaynaklar her yanıtın altında gösterilir. Maksimum dosya boyutu 25 MB'dır.

**Testler:**

```powershell
pytest -m "not integration" -q
pytest -m integration -q
```

**Yaygın sorunlar:** Ollama'ya bağlanılamıyorsa servisi ve model indirmesini kontrol edin. İndeksin model/chunk ayarları değiştiyse `python -m app.scripts.search_documents --reset-index` komutu eski indeksi **siler**. İlk model indirmeleri birkaç dakika sürebilir; SSL doğrulamasını kapatmayın.

> Bu kurulum özeti ana README'deki talimatlarla tekrar ediyor. Repository'de tek kurulum kaynağı istiyorsanız bu ek dosyayı kaldırabilirsiniz.
