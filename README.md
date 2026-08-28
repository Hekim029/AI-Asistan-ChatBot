# Heko — AI Desktop Assistant

Güncel geliştirme sürümü: **0.1.0**

Heko; Windows üzerinde çalışan, Türkçe doğal dil desteğine sahip, kişisel hafıza
ve masaüstü araçları sunan PySide6 tabanlı bir yapay zekâ asistanıdır.

Proje hâlen aktif geliştirme aşamasındadır. Dosya silme, e-posta gönderme ve
takvim değişiklikleri gibi riskli işlemler kullanıcı onayı olmadan uygulanmaz.

## Öne çıkan özellikler

### Sohbet ve model desteği

- Groq modelleriyle doğal dil sohbeti ve araç çağırma
- Model kullanmadan çalışan yerel görev, not, hava ve dosya komutları
- Groq kullanılamadığında isteğe bağlı Ollama yerel model desteği
- Normal, eğlenceli, ciddi ve teknik kişilik modları
- Uzun konuşmalarda otomatik bağlam küçültme
- Mesaja göre dinamik araç seçimiyle daha düşük token kullanımı

### Çoklu sohbet ve ortak çalışma

- Aynı anda birden fazla bağımsız sohbet penceresi
- Her pencere için ayrı konuşma geçmişi ve çalışan işlem
- Pencereler arasında ortak görev, not, hatırlatıcı ve kişisel hafıza
- Diğer pencerelerin sonuçlarını paylaşan kalıcı ortak çalışma alanı
- Sohbet oturumlarını açma, gizleme ve yeniden adlandırma paneli
- Kapatılan bir sohbeti aynı geçmiş ve isimle yeniden açma
- Kontrol Merkezi'nden görev, not, hatırlatıcı ve ortak çalışmaları elle
  ekleme, düzenleme ve silme

### Kişisel asistan

- Düzenlenebilir ve aranabilir kalıcı kullanıcı hafızası
- Görev oluşturma, listeleme ve tamamlama
- Etiketlenebilir, aranabilir ve tekrarları engellenen notlar
- Kalıcı hatırlatıcı oluşturma, listeleme ve iptal
- Son tarihi geçen görevler için `GECİKMİŞ` uyarısı
- Sabah ve akşam otomatik günlük özetleri
- Günlük özet saati, şehir ve etkinlik tercihleri
- Open-Meteo üzerinden anahtarsız hava durumu

### Masaüstü araçları

- Dosya ve klasör arama/açma
- Dosyaları kalıcı silmek yerine Windows Çöp Kutusu'na taşıma
- Küçük metin ve kod dosyalarını salt okunur inceleme
- Proje dosyalarını göreli yollarla güvenli listeleme ve okuma
- Kod değişikliklerinde diff önizlemesi, açık onay ve otomatik yedek
- Kod değişiklikleri için renkli, kopyalanabilir ve süreli görsel diff penceresi
- Proje dosyalarını proje kökü doğrulaması ve açık onayla Çöp Kutusu'na taşıma
- PDF ve DOCX belgelerinden güvenli, salt okunur metin çıkarma
- Uygulama açma ve kapatma
- Ses ve medya kontrolü
- Web, YouTube ve Spotify işlemleri
- Sistem durumu ve tanılama ekranı

### Google entegrasyonları

- Gmail listeleme, arama ve içerik okuma
- Açık kullanıcı onayıyla e-posta gönderme
- Google Takvim etkinliklerini okuma
- Açık kullanıcı onayıyla etkinlik oluşturma, güncelleme ve silme

### Arayüz

- Yeniden boyutlandırılabilir ve tam ekran olabilen çerçevesiz pencere
- Türkiye saatine bağlı hareketli kaos temalı arka plan
- Bekleme, çalışma, dinleme, başarı, uyarı ve çevrimdışı durumlarına tepki veren
  masaüstü karakteri; çoklu sohbetlerde ortak çalışma durumunu izler
- Mesaj arama, geçmiş, hafıza, ayarlar ve kontrol merkezi pencereleri
- Her Heko mesajında çevrimdışı seslendirme düğmesi; ayarlanabilir otomatik
  okuma, Windows sesi, hız ve ses seviyesi
- Uzun yanıtlarda işlem aşaması, geçen süre ve güvenli durdurma düğmesi
- İç araç adlarını ve SHA karmalarını kullanıcıdan gizleyen sade sonuç metinleri
- Windows açılışında otomatik başlatma seçeneği
- Varsayılan kapalı, Ayarlar'dan açılabilen deneysel ekran farkındalığı

## Sistem gereksinimleri

- Windows 10 veya Windows 11
- Python 3.11 veya üzeri
- İnternet bağlantısı (Groq, hava durumu ve Google özellikleri için)
- İsteğe bağlı mikrofon
- İsteğe bağlı Ollama ve yerel model

## Kurulum

Depoyu klonladıktan sonra proje klasöründe:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Proje kökünde `.env` dosyası oluştur:

```env
GROQ_API_KEY=groq_api_anahtarin
YOUTUBE_API_KEY=istege_bagli_youtube_anahtarin
```

Uygulamayı çalıştır:

```powershell
python .\main.py
```

> `.env`, Google kimlik dosyaları ve `memory/` altındaki kişisel veriler Git'e
> gönderilmez. Bu dosyaları hiçbir commit'e elle eklemeyin.

## İsteğe bağlı Ollama kurulumu

Yerel model, Groq kota veya bağlantı sorunu yaşadığında normal sohbet için geri
dönüş sağlayabilir. Ollama kurulumu zorunlu değildir.

Donanımı daha sınırlı sistemler için:

```powershell
ollama pull qwen3:8b
```

`.env` dosyasına ekle:

```env
OLLAMA_MODEL=qwen3:8b
OLLAMA_URL=http://127.0.0.1:11434
```

Alternatif olarak Heko içindeki **Ayarlar > Yerel Model (Ollama)** ekranından
kurulu modelleri kontrol edebilir, bir model seçebilir ve bağlantıyı
sınayabilirsin. Buradan yapılan değişiklik uygulamayı yeniden başlatmadan
devreye girer ve yalnızca bu bilgisayarda saklanır.

Bağlantıyı kontrol et:

```powershell
ollama list
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

Tamamen yerel kullanım isteniyorsa Windows kullanıcı ortam değişkenlerine
`OLLAMA_NO_CLOUD=1` eklenebilir.

## Çevrimdışı sesli yanıt

Heko'nun metinden sese özelliği PySide6 `QtTextToSpeech` üzerinden Windows'un
yerel SAPI/WinRT konuşma motorunu kullanır. Yanıt metni bir ses API'sine
gönderilmez ve yeni bir Python paketi gerekmez.

- Heko mesajının altındaki `🔊` düğmesi yalnızca o yanıtı okur.
- Aynı düğmeye veya `■` simgesine basmak okumayı durdurur.
- **Ayarlar > Ses** bölümünden otomatik okuma, ses, hız ve seviye seçilir.
- Mikrofon açıldığında devam eden ses otomatik kesilir.
- Birden fazla sohbet tek motoru paylaşır; sesler üst üste binmez.
- Kod blokları, bağlantılar ve iç teknik protokoller okunmaz; çok uzun yanıtlar
  kısa bir sesli bölümden sonra ekrandan devam eder.

**Ayarlar > Ses** ekranında konuşma sesi bulunamadığı yazıyorsa Windows
**Ayarlar > Saat ve dil > Konuşma** bölümünden Türkçe bir konuşma sesi ekleyip
Heko'yu yeniden başlat.

## Google kurulumu

1. Google Cloud Console'da bir OAuth masaüstü istemcisi oluştur.
2. İndirilen dosyayı proje köküne `credentials.json` adıyla yerleştir.
3. İlk Gmail veya Takvim kullanımında tarayıcıdan izin ver.
4. Oluşan erişim bilgileri kaynak çalışmada `memory/token.dat` altında, paketli
   sürümde kullanıcı veri dizininde şifreli olarak saklanır.

`credentials.json`, `memory/token.json` ve `memory/token.dat` Git tarafından yok sayılır.

## Örnek komutlar

```text
20 dakika sonra fırına bakmamı hatırlat
yarın Ankara'da hava nasıl?
görev ekle: proje raporunu tamamla
alışveriş görevini tamamla
not al: arayüzün ana rengi mor olacak
proje hakkındaki notlarımı göster
günlük özetimi ver
benim hakkımda ne biliyorsun?
diğer pencerede ne oldu
dosya oku: C:\Projeler\ornek\main.py
proje dosyalarını listele
services/llm_client.py dosyasını incele
services/example.py dosyasını oluştur ve önce değişikliği göster
okunmamış maillerimi göster
yarın saat 14.00'e proje toplantısı ekle
masaüstündeki rapor.txt dosyasını sil
Spotify'ı aç
sesi yüzde 35 yap
```

## Çoklu sohbet kullanımı

- Üst çubuktaki `+` düğmesi yeni bir sohbet oluşturur.
- `▦` düğmesi Sohbet Oturumları panelini açar.
- Kapatılan sohbetler silinmez; panelde gizli olarak kalır.
- `Aç` düğmesi oturumu aynı geçmişle geri getirir.
- `Adlandır` düğmesiyle oturumlara `Kodlama`, `Araştırma` veya `Rapor` gibi
  kalıcı isimler verilebilir.
- `diğer pencerede ne oldu` komutu diğer oturumların son sonuçlarını getirir.

## Güvenlik modeli

Aşağıdaki işlemler iki aşamalı onay gerektirir:

- Dosya silme
- E-posta gönderme
- Takvim etkinliği oluşturma, güncelleme veya silme
- Konuşma geçmişini temizleme
- Kalıcı kullanıcı hafızasından bilgi silme
- Proje dosyasına kod yazma
- Uygulamayı zorla kapatma
- Tek kare ekran görüntüsü alma ve görsel analiz servisine gönderme

İşlem özeti gösterildikten sonra kullanıcı beş dakika içinde ayrıca onay vermelidir.
Dosya silme işlemleri Windows Çöp Kutusu üzerinden geri alınabilir biçimde yapılır.

Ek güvenlik sınırları:

- `.env`, `credentials.json`, `token.dat`, özel anahtar ve kimlik dosyaları okunmaz
- İkili dosyalar
- Desteklenmeyen uzantılar
- 2 MB üzerindeki dosyalar
- 20 MB üzerindeki PDF/DOCX belgeleri, şifreli PDF'ler ve makrolu/gömülü DOCX'ler
- Aşırı sıkıştırılmış veya açıldığında 100 MB sınırını aşan DOCX arşivleri
- Uygulama ve dosya açmada yürütülebilir dosya/kısayol çalıştırma engellenir
- Ollama bağlantısı yalnızca bu bilgisayardaki `localhost` adresine izin verir
- API anahtarı/parola görünen mesajlar modele gönderilmez veya hafızaya yazılmaz
- Google OAuth yenileme tokenı Windows DPAPI ile kullanıcı hesabına bağlı şifrelenir
- Kalıcı JSON verileri atomik ve kısıtlı izinli dosya yazımıyla kaydedilir
- Dış e-posta, dosya ve araç içerikleri model komutu değil, güvenilmeyen veri sayılır
- Ekran görüntüsü onaydan önce alınmaz; yalnızca bellekte küçültülür, Groq'un
  `qwen/qwen3.6-27b` görsel modeline gönderilir ve yerel dosya olarak saklanmaz.
  Bu deneysel özellik varsayılan olarak kapalıdır ve yalnızca **Ayarlar > Sistem**
  bölümünden açılabilir
- Metinden sese çıktısı Windows'un yerel konuşma motorunda üretilir; yanıt metni
  bu amaçla harici bir ses hizmetine gönderilmez

Ayrıntılı tehdit modeli, kalan riskler ve denetim komutları için
[SECURITY.md](SECURITY.md) belgesine bakın.

## Test

Tüm regresyon testleri:

```powershell
venv\Scripts\python.exe -m unittest discover -s tests -v
```

Hızlı sözdizimi kontrolü:

```powershell
venv\Scripts\python.exe -m compileall -q main.py ui core services memory tests evals utils
```

API kullanmadan gerçek kullanıcı cümleleriyle yönlendirme, güvenlik, sunum ve
kişilik sözleşmesi puanını ölç:

```powershell
venv\Scripts\python.exe -m evals.run_evals
```

Seçili Ollama modeliyle dört güvenli kişilik yanıtını da değerlendirmek için:

```powershell
venv\Scripts\python.exe -m evals.run_evals --live-local
```

Çevrimdışı toplam puan **Ayarlar > Sistem > Sistem Kontrolü** ekranında da
gösterilir. Ayrıntılar ve rapor komutları [evals/README.md](evals/README.md)
dosyasındadır.

Geliştirici güvenlik araçları ve taramalar:

```powershell
venv\Scripts\python.exe -m pip install -r requirements-dev.txt
venv\Scripts\python.exe -X utf8 -m bandit -ll -r core services memory ui utils main.py -x tests
venv\Scripts\python.exe -m pip_audit --local
```

## Windows EXE oluşturma

```powershell
.\scripts\build_release.ps1
```

Betik; test, çevrimdışı kalite değerlendirmesi, orta/yüksek güvenlik taraması ve
temiz PyInstaller derlemesini sırasıyla çalıştırır. Ayrıntılı manuel yayın
kontrolleri [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) dosyasındadır.

Çıktı `dist/HekoAI.exe` altında oluşur. API anahtarları, Google kimlik bilgileri
ve kişisel hafıza EXE içine paketlenmez. Paketli sürüm; ayar, sohbet, görev,
hatırlatıcı ve OAuth verilerini `%LOCALAPPDATA%\HekoAI\data` altında tutar.
Eski bir sürümde EXE yanında `memory/` kayıtları varsa, boş hedef dizine ilk
açılışta yalnızca tanınan veri dosyaları güvenli sınırlarla kopyalanır.
Mikrofon kaydı PCM16 WAV dosyasını standart Python altyapısıyla üretir; dağıtım
paketinde yalnızca bu iş için ağır SciPy kitaplığının taşınması gerekmez.

## Proje yapısı

```text
assets/       arka planlar ve masaüstü karakter görselleri
core/         yönlendirme, araç şemaları, güvenlik ve ortak durum
evals/        API gerektirmeyen kalite senaryoları ve isteğe bağlı Ollama ölçümü
memory/       kaynak çalışmada oluşan yerel kişisel veriler
services/     Groq, Ollama, Google, görev, hava ve sistem servisleri
tests/        güvenlik ve servis regresyon testleri
ui/           sohbet, ayarlar, oturum, hafıza ve kontrol pencereleri
utils/        yapılandırma ve Windows başlangıç yardımcıları
main.py       uygulama giriş noktası ve pencere yöneticisi
```

## Yol haritası

Planlanan sağlamlaştırma çalışmaları [ROADMAP.md](ROADMAP.md) dosyasında tutulur.
Öne çıkan sonraki adımlar:

- Ölçülen sonuçlara göre model ve prompt kişiselleştirme planı
- Sürümleme, kurulum paketi ve temiz makinede dağıtım testi

## Tanılama ve günlükler

Ayarlar içindeki Sistem Kontrolü ekranı gerekli servisleri denetler. Kaynak
çalışmada hatalar `memory/heko.log` dosyasına, paketli sürümde ise kullanıcı
veri dizinine yazılır ve Git'e eklenmez.

## Lisans

Bu depo için henüz bir lisans seçilmedi. Herkese açık dağıtımdan önce uygun bir
`LICENSE` dosyası eklenmesi önerilir.
