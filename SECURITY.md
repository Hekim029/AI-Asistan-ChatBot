# Heko Güvenlik Politikası

## Tehdit modeli

Heko tek kullanıcılı bir Windows masaüstü uygulamasıdır. İnternetten gelen bir
sunucu portu açmaz. Bulut modeli, Google servisleri, hava durumu ve isteğe bağlı
Ollama istemcisi için dışarıya bağlantı kurar. Ollama adresi yalnızca loopback
(`127.0.0.1`, `::1` veya `localhost`) olabilir.

Korunan başlıca riskler:

- Modelin veya dış içeriğin kullanıcı onayı olmadan yıkıcı işlem başlatması
- Komut/shell enjeksiyonu ve kontrolsüz program çalıştırma
- Yol geçişi, sembolik bağlantı ve proje kökü dışına yazma
- API anahtarı, parola, özel anahtar ve OAuth tokenının log/hafızaya sızması
- Bozuk veya aşırı büyük yerel veri dosyalarının uygulamayı etkilemesi
- E-posta başlığı, URL ve takvim alanları üzerinden kötü niyetli girdi
- Bilinen güvenlik açığı bulunan doğrudan Python bağımlılıkları

## Uygulanan sınırlar

- Silme, e-posta/takvim değişikliği, proje kodu yazma, geçmiş/hafıza temizleme
  ve zorla uygulama kapatma iki aşamalı, süreli kullanıcı onayı ister.
- Süreç çalıştırma allowlist ile sınırlandırılır; kullanıcı girdisi shell'e
  verilmez. Sohbetten yürütülebilir dosya ve kısayol açılmaz.
- Proje yazma; kök dizin, uzantı, hassas yol, symlink, SHA-256 sürümü, diff,
  yedek ve atomik değiştirme kontrollerini uygular.
- Proje silme yalnızca göreli ve doğrulanmış proje yolunda çalışır; kalıcı silme
  yerine Windows Çöp Kutusu ve süreli kullanıcı onayı kullanır.
- PDF/DOCX okuma; yol, symlink, boyut, şifreli PDF, makro/gömülü nesne ve DOCX
  sıkıştırma-bombası sınırlarını uygular. Belge içeriği güvenilmeyen veri sayılır.
- Hassas veri desenleri sohbet, kalıcı hafıza, ortak çalışma alanı ve loglarda
  reddedilir veya maskelenir.
- Google OAuth tokenı Windows DPAPI ile geçerli kullanıcı hesabına bağlı olarak
  şifrelenir. Şifreleme çalışmazsa token düz metin kaydedilmeden işlem durur.
- Yerel JSON kayıtları boyut sınırıyla okunur ve geçici dosya + atomik değiştirme
  yöntemiyle yazılır.
- HTTP çağrılarında yönlendirme kapatılır; tarayıcı araçları HTTPS doğrular;
  Ollama istemcisi proxy ortam değişkenlerini kullanmaz.
- Model sistem talimatı; e-posta, dosya, web sonucu ve ortak pencere içeriklerini
  güvenilmeyen veri sayar.

## Kalan riskler

Bu önlemler uygulamayı "kırılamaz" yapmaz. Aynı Windows kullanıcısı veya yönetici
yetkisiyle çalışan zararlı yazılım; ekranı, belleği, klavyeyi ve kullanıcı
dosyalarını okuyabilir. Kullanıcının bizzat onayladığı kötü bir işlem yine zarar
verebilir. Model tabanlı prompt injection savunması olasılığı azaltır ancak
matematiksel güvence sağlamaz. Ekran/klavye otomasyonu öndeki yanlış pencereyi
etkileyebilir. Bulut modeline gönderilen normal sohbet içeriği ilgili sağlayıcının
gizlilik koşullarına tabidir.

Bu nedenle gerçek API anahtarlarını sohbete yapıştırmayın, `.env` ve
`credentials.json` dosyalarını Git'e eklemeyin, Windows hesabını ve depoyu özel
tutun, onay kartlarını okumadan kabul etmeyin.

## Güvenlik denetimi

```powershell
venv\Scripts\python.exe -m unittest discover -s tests -q
venv\Scripts\python.exe -m compileall -q main.py ui core services memory tests utils
venv\Scripts\python.exe -m bandit -r core services memory ui utils main.py -x tests
venv\Scripts\python.exe -m pip_audit --local
```

Bandit'teki kontrollü `os.startfile`/`subprocess` çağrıları düşük seviye bulgu
üretebilir. Bu çağrılar yalnızca kodda tanımlı uygulama listesi veya doğrulanmış,
yürütülebilir olmayan kullanıcı dosyalarıyla kullanılır.

## Açık bildirme

Depo private kaldığı sürece bir güvenlik bulgusunu herkese açık issue olarak
paylaşmayın. Depo sahibine etki, yeniden üretim adımları ve mümkünse önerilen
düzeltmeyle özel kanaldan bildirin. Anahtar sızıntısında önce anahtarı iptal edip
yenisini üretin; yalnızca Git geçmişinden silmek yeterli değildir.
