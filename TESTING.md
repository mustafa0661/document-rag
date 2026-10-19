# Test ve Doğrulama

**Kapsam:** PDF/görsel işleme, OCR, chunking, embedding, retrieval, Ollama ile cevaplama ve Streamlit. Sonuçlar ilgili ortamlarda **raporlanan çalıştırmalara** aittir; bütün testler son sürümde aynı makinede yeniden çalıştırılmadı.

## 1. Son test durumu (19 Ekim 2026)

| Ortam / kapsam | Raporlanan sonuç |
|---|---|
| Linux, Python 3.12 — son kodun birim/arayüz/denetim testleri | **166 geçti, 12 atlandı** (model/Ollama testleri) |
| Windows, Python 3.11 — önceki sürüm birim/arayüz | **139 geçti** |
| Windows — Docling + EasyOCR entegrasyonu | **9/9 geçti** |
| Windows — BGE-M3 entegrasyonu | **11/11 geçti** |
| Windows — Ollama | Son çalıştırmalarda bilinen başarısızlıklar görüldü; iki test `xfail` yapıldı. **Son kod Windows'ta yeniden çalıştırılmadı.** |

**Teslim öncesi doğrulama (henüz raporlanmadı):**

```powershell
python -m app.scripts.release_check --run-tests
pytest -m integration -q
```

`xfail`, beklenen/bilinen başarısızlık demektir; geçerli bir testle aynı şey değildir. Testlerin geçmesi gerçek dünya doğruluğunu tek başına kanıtlamaz.

## 2. Test edilen davranışlar

| Bileşen | Kontrol |
|---|---|
| Belge işleme | TR/EN PDF, JPG, PNG; taranmış PDF; tablo satır/sütunları; sayfa metadata'sı; bozuk ve boş dosyalar |
| Chunking / indeks | 500-token sınırı, overlap, tablo başlığı, sayfa izolasyonu, tekrar indeksleme, yarım işlemi geri alma |
| Retrieval | Seçili belge filtresi, kalıcı ChromaDB, embedding boyutu/model ayarı kontrolü, çapraz dil arama |
| Soru-cevap | Boş retrieval'da LLM'i çağırmama; kaynak ID doğrulama; belge dışı soruyu reddetme; prompt injection testi |
| Streamlit | Güvenli dosya adı, 25 MB sınırı, belge seçimi, oturum ayrımı, model cache, servis kesintisinde hata gösterimi |

Sentetik retrieval setinde **7/7 alakalı soruda doğru sayfa ilk sırada** bulundu; alakasız soruların mesafeleri daha yüksekti. Örneklem küçük olduğundan genel başarı oranı veya güvenilir benzerlik eşiği çıkarılmadı.

## 3. Gerçek belge testi — Parol 500 mg KÜB

**Belge:** Türkçe dijital PDF; 10 sayfa, 54 chunk. Streamlit üzerinden **19 soru** soruldu ve cevaplar kaynak metinle karşılaştırıldı.

| Sonuç | Sayı | Örnek |
|---|---:|---|
| Kaynakla uyumlu cevap | 10 | “Bir tablette kaç mg?” → 500 mg |
| Doğru ret | 5 | Belgede bulunmayan fiyat, başka ilaç ve konu dışı sorular |
| Sorunlu cevap | 4 | Uyarının yasağa çevrilmesi; şartların/listelerin eksilmesi; kaynaksız “evet” hükmü; son kullanım tarihinin yanlış anlaşılması |

**Önemli bulgu:** Kaynak doğru seçilse bile Qwen3 4B bazen “dikkatli kullanılmalıdır” ifadesini “kullanılmamalıdır” diye aktardı veya “tıbbi tavsiye olmadıkça” koşulunu düşürdü. Prompt düzenlemesi bir durumu iyileştirdi fakat bütün hataları gidermedi. Bu nedenle yanıtlar, özellikle tıbbi uyarı ve yasaklarda, **gösterilen kaynak metinle doğrulanmalıdır**. Uygulama tıbbi karar destek aracı değildir.

## 4. Bilinen sınırlamalar

- **LLM:** Türkçe soru → İngilizce belgede göreli tarih yanlış çevrilebilir veya cevap reddedilebilir; bazı şartlar ve önemli liste üyeleri atlanabilir. İki Ollama senaryosu `xfail` olarak korunuyor.
- **Retrieval:** Gerçek uzun belgelerde Hit@k ölçülmedi; kontrendikasyonlar (4.3) bölümü bir soruda getirilemedi. Benzerlik eşiği tanımlı değil.
- **OCR:** Gerçek eğik/gölgeli telefon taramaları ve el yazısı ölçülmedi. Docling sayfalar arası paragrafı önceki sayfaya atayabilir, liste maddesini başlık sanabilir.
- **Performans:** CPU embedding yaklaşık **1,23 chunk/sn**; büyük belgeler yavaş işlenir.
- **Platform:** Windows'ta aralıklı `access violation` mesajı görüldü; raporlanan çalıştırmalarda testin sonucu doğruydu. Docker build/çalıştırma doğrulanmadı.

## 5. Testleri çalıştırma

```powershell
pip install -r requirements-dev.txt
python -m app.scripts.download_models
pytest -m "not integration" -q
pytest -m integration -q
```

Gerçek modellerle entegrasyon için Ollama açık, `qwen3:4b-instruct` indirilmiş olmalıdır. Yalnızca temiz sentetik belge testleriyle elde edilen sonuçları gerçek dünya başarısı olarak yorumlamayın.
