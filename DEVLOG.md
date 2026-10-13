• Problemi nasıl parçaladınız?
• Hangi yaklaşımları denediniz? Hangisi işe yaramadı ve neden?
• Kritik karar noktalarında hangi alternatifleri değerlendirdiniz?
• Nerede takıldınız? Nasıl çözdünüz?
• Zamanınızı nasıl harcadınız?
• Şu an bildiğinizle baştan başlasanız neyi farklı yapardınız?


--------

13.10.2026 - 1. Gün

- Proje planı hazırlandı

Problem: Kullanıcıların çeşitli formatlardaki belgeleri yükleyerek bu belgeler üzerinden doğal dil ile soru sorabileceği,
yapay zeka destekli bir Belge Analiz ve Soru-Cevap Sistemi geliştirmenizi bekliyoruz.
Sistem, yüklenen belgeleri işleyecek, içeriğini analiz edecek 
ve kullanıcı sorularına belgelerden elde ettiği bilgiye dayalı yanıtlar verecektir.

-Belge Yükleme	Kullanıcı PDF ve resim formatlarında (JPG, PNG) belge yükleyebilmeli.
-Metin Çıkarımı	Resim belgelerindeki metinler okunabilmeli. Türkçe ve İngilizce desteklenmeli.
-Soru - Cevap	Kullanıcı, yüklenen belgeler hakkında doğal dilde soru sorabilmeli ve tutarlı yanıtlar alabilmeli.
-Doğruluk	Sistem, belgede olmayan bilgileri üretmemeli (hallucination).
-Kullanılabilirlik	Kullanıcı sistemi bir arayüz üzerinden kullanabilmeli.


(RAG) 

Görsel işleme olacak.
Metin işleme olacak.
Türkçe ve İngilizce desteği olacak.
Cevaplar yüklenen belgeyle tutarlı olmalı.
Halüsinasyon görmemeli.
Arayüz gerekli.
Belge yüklenebilir olmalı. Belge yüklememe durumu olmamalı. Kaynak olarak yüklenen belgeyi kullanmalı.
MVP olmalı
Gelişmeye açık değişime kapalı olmalı SOLID prensibi gereğince üzerinde geliştirilebilir olmalı.


Python'ı hızlı geliştirme için düşünüyorum.
Hem LLM hem arayüz için yine python kullanılabilir.
Model olaral Ollama ve vb. modeller araştırılacak. İhtiyaca yönelik bu değişebilir.
Proje en sonda Dockerize edilmeli çünkü başkaları tarafından kolayca kullanılabilmeli.



RAG mimarisini öğrendim.

Örnek: Vektör veritabanı seçimi
Problem: Belgelerden çıkarılan metin parçalarının embedding'lerini saklamak ve kullanıcı sorularıyla benzerlik araması yapmak.
Alternatifler: ChromaDB, FAISS, Qdrant, pgvector.
Karar: ChromaDB.
Gerekçe: MVP kapsamında düşük kurulum maliyeti, yerel kalıcılık, metadata desteği ve Python ile kolay entegrasyon.
Ödünleşim: Büyük ölçekli dağıtık sistemler için daha gelişmiş bir çözüm gerekebilir.
Doğrulama: Farklı belgelerden gelen chunk'ların doğru belgeyle ilişkilendirilmesi ve retrieval sonuçlarının test edilmesi.
Gelecek yaklaşım: Ölçek, eşzamanlı kullanıcı veya gelişmiş filtreleme ihtiyacı oluşursa Qdrant ya da pgvector değerlendirilmesi.


Projede temel önceliğim, sınırlı geliştirme süresi içerisinde PDF ve görsellerden bilgi çıkarabilen, Türkçe ve İngilizce belgeleri destekleyen ve yanıtlarını belge içeriğine dayandıran işlevsel bir MVP geliştirmekti.
Teknoloji seçimlerini yaparken yalnızca geliştirme hızını değil; entegrasyon kolaylığını, yerel çalışabilmeyi, doğruluğu, operasyonel karmaşıklığı ve ileride genişletilebilirliği dikkate aldım.
Python ve Streamlit ile uygulama geliştirme süresini azaltmayı, Docling ve OCR ile farklı belge türlerini işlemeyi, BGE-M3 ile çok dilli retrieval gerçekleştirmeyi, ChromaDB ile basit bir vektör depolama katmanı oluşturmayı, Ollama ve Qwen3 ile de harici API bağımlılığını azaltmayı hedefledim.
Bu tercihlerin her senaryo için en iyi çözümler olduğunu iddia etmiyorum. Projenin kapsamına ve zaman kısıtına göre uygun bir başlangıç mimarisi olduğunu düşünüyorum. Kararların doğruluğunu ise farklı belge türleri, retrieval testleri ve cevap kalitesi üzerinden değerlendirmeyi hedefliyorum.


İlk aşamada Ollama'yı yerel ve tekrarlanabilir bir geliştirme ortamı sağlamak amacıyla seçtim. Ancak uygulamanın belirli bir bilgisayara bağımlı olmasını istemediğim için model erişimini ayrı bir katmanda tasarladım. Bu sayede aynı uygulama, konfigürasyon değişikliğiyle farklı bir Ollama sunucusuna bağlanabilecek şekilde geliştirilebilir. İleride bulut API entegrasyonu da bu katman üzerinden yapılabilir.

### Mimari Karar: Yerel LLM Kullanımı

**Değerlendirilen alternatifler:** Yerel Ollama, uzak Ollama sunucusu ve bulut tabanlı LLM API servisleri.

**Seçilen yaklaşım:** Ollama üzerinden yerel Qwen3 modeli.

**Kararın gerekçesi:** Projenin sınırlı geliştirme süresi, işlevsel MVP beklentisi ve demo videosu ile sunulacak olması dikkate alınarak, ek sunucu altyapısı ve harici API bağımlılığı gerektirmeyen yerel model kullanımı tercih edilmiştir.

**Bilinen sınırlamalar:** Modelin çalıştırıldığı bilgisayarın donanım kapasitesi cevap süresini ve kullanılabilecek model boyutunu etkiler. Başka bilgisayarlarda çalıştırılması için uygun model ortamının kurulması gerekir.

**Genişletilebilirlik:** LLM erişimi ayrı bir servis katmanında tasarlanarak model adı ve bağlantı adresi konfigürasyona taşınacaktır. Böylece gelecekte uzak Ollama veya bulut LLM sağlayıcılarına geçiş kolaylaştırılacaktır.

**Doğrulama:** Yerel modelin cevap kalitesi, kaynak tüketimi ve yanıt süresi örnek belgeler üzerinde test edilecektir.