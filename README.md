## Kurulum

### Gereksinimler
- Python 3.11
- İnternet bağlantısı (yalnızca ilk kurulumda: Python paketleri ve modeller indirilir)
- Yaklaşık birkaç GB boş disk alanı (torch ve modeller nedeniyle)

### Adımlar

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m scripts.download_models
pytest -v
```

**Linux / macOS:**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m scripts.download_models
pytest -v
```

`requirements.txt` yalnızca uygulamanın çalışması için gerekenleri, `requirements-dev.txt` ise ek olarak test araçlarını içerir.

### Model indirme adımı
`python -m scripts.download_models` belge işleme için gereken modelleri önceden indirir ve yüklenebildiklerini doğrular:

| Model | Kaynak | İndiği yer |
|---|---|---|
| Docling layout ve tablo yapısı modelleri | Hugging Face | Hugging Face önbelleği (`~/.cache/huggingface/hub`) |
| EasyOCR Türkçe/İngilizce modelleri | GitHub (EasyOCR sürüm dosyaları) | `~/.EasyOCR/model` |

Bu adım atlanırsa modeller ilk belge işlenirken indirilir; sonuç aynıdır, ancak bir ağ sorunu o zaman ve daha zor anlaşılır biçimde ortaya çıkar. Modeller zaten indirilmişse betik yeniden indirmez, yalnızca yükleyip doğrular. Windows'ta `~`, `C:\Users\<kullanıcı>` anlamına gelir.

## Testler

```bash
pytest -m "not integration" -v   # Birim testleri: Docling yüklenmez, saniyeler içinde biter
pytest -m integration -v         # Gerçek Docling + EasyOCR ile entegrasyon testleri
pytest -v                        # Tümü
```

Test senaryoları, sonuçları ve bilinen sınırlamalar için bkz. [TESTING.md](TESTING.md).

## Sorun giderme

**Model indirme başarısız oluyor**
1. Hata çıktısının tamamını kaydedin; neden genellikle son satırlarda yazar.
2. İnternet bağlantısını ve `huggingface.co` ile `github.com` adreslerine erişimi kontrol edin.
3. Betiği yeniden çalıştırın. Geçici ağ veya servis hataları tekrar denendiğinde çoğunlukla düzelir; yarım kalan indirmeler kaldığı yerden tamamlanır.
4. Çok sayıda istekte Hugging Face hız sınırına takılıyorsanız ücretsiz bir Hugging Face hesabıyla bir erişim anahtarı oluşturup `HF_TOKEN` ortam değişkenine tanımlayabilirsiniz. Bu adım zorunlu değildir.
5. Kurum ağlarında HTTPS trafiğini denetleyen bir proxy varsa sertifika doğrulama hatası (`CERTIFICATE_VERIFY_FAILED`) alınabilir. Bu durumda SSL doğrulamasını kapatmayın; kurumun kök sertifikasının Python tarafından güvenilir olarak tanınması gerekir (BT ekibinize danışın) veya kurulum denetimsiz bir ağda yapılabilir.

**Windows'ta "symlinks" uyarısı**
Hugging Face önbelleği Windows'ta sembolik bağlantı oluşturamadığında bu uyarıyı verir. Zararsızdır; yalnızca disk kullanımı biraz artar.

**`no accelerator is found` uyarısı**
Windows'ta PyPI'dan kurulan torch CPU sürümüdür; belge işleme CPU üzerinde çalışır. İşlevsel bir sorun değildir, yalnızca büyük belgelerde süre uzar.
