# Retrieval değerlendirmesi

Gerçek belgelerle, tekrarlanabilir biçimde retrieval kalitesini ölçmek için kullanılır.

```bash
python -m app.scripts.evaluate_retrieval                 # eval/retrieval_eval.json
python -m app.scripts.evaluate_retrieval --reset         # değerlendirme indeksini sil
```

Belgeler ana indeksten ayrı bir indekste (`data/eval_chroma`) tutulur ve tekrar çalıştırmada yeniden okunmaz. Bu sayede soru setini düzenleyip betiği birkaç saniyede yeniden çalıştırabilirsiniz. Rapor `eval/results/` altına yazılır.

## Belgeler

Case study'nin saydığı belge tiplerini kapsayan 3–5 belge yeterlidir: Türkçe dijital PDF, İngilizce dijital PDF, taranmış veya fotoğrafı çekilmiş bir sayfa ve tablolu bir belge.

**Gerçek hasta verisi kullanılmaz.** Herkese açık belgeler (ilaç kullanma talimatları, Dünya Sağlık Örgütü bilgi notları, kamu kurumlarının raporları) veya kendi hazırladığınız belgeler kullanılmalıdır. Belgeleri depoya eklemeden önce yeniden dağıtımlarına izin verildiğinden emin olun; emin değilseniz `eval/documents/` klasörünü `.gitignore`'a ekleyip belgelerin kaynaklarını aşağıya yazın.

### Kullanılan belgeler ve kaynakları

| Dosya | Tür | Kaynak |
|---|---|---|
| _doldurulacak_ | | |

## Soru setini yazma kuralları

1. **Beklenen cevapları sistemi çalıştırmadan ÖNCE yazın.** Sonuçlara bakıp beklentiyi sonradan yazmak ölçümü taraflı hâle getirir.
2. **Soruyu kendi kelimelerinizle sorun.** Belgedeki cümleyi kopyalamak kelime eşleşmesini ölçer, anlamsal aramayı ölçmez. Kullanıcı nasıl sorarsa öyle sorun ("günlük maksimum doz" yerine "günde en fazla kaç tane içebilirim").
3. **Soru türlerini dengeleyin.** Yaklaşık hedef:
   - `relevant`: ~20 soru (yaklaşık 8 Türkçe, 6 İngilizce, 6 diller arası). Birkaçı tablo hücresine, birkaçı sayısal değere yönelik olsun.
   - `near_miss`: ~8 soru. Belgenin konusuna yakın ama cevabı belgede **olmayan** sorular. Eşiği asıl belirleyen ve halüsinasyon riskinin en yüksek olduğu tür bu.
   - `out_of_scope`: ~4 soru. Tamamen alakasız sorular.
4. **Cevap birden fazla sayfadaysa** hepsini `pages` listesine yazın; herhangi biri doğru sayılır.
5. **Dil kodu:** `tr` (Türkçe soru, Türkçe belge), `en` (İngilizce soru, İngilizce belge), `cross` (Türkçe soru, İngilizce belge veya tersi).

## Metrikler

- **Hit@1 / Hit@5:** Beklenen sayfa ilk sonuçta / ilk 5 sonuç içinde mi?
- **MRR:** Doğru sonucun sırasının tersinin ortalaması (1/sıra). 1,00 doğru sayfanın her zaman en üstte olduğu anlamına gelir.
- **Mesafe:** Kosinüs mesafesi = 1 − kosinüs benzerliği. Küçük olan daha alakalıdır.
- **Eşik taraması:** Her eşik için alakalı soruların yüzde kaçının korunduğu ve cevabı belgede olmayan soruların yüzde kaçının reddedildiği. Aday eşik, ikisinin ortalamasını en yükseğe çıkaran değerdir; eşitlikte alakalı soruları daha çok koruyan eşik seçilir.
