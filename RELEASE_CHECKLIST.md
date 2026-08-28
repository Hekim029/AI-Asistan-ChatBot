# Heko 0.1.0 yayın kontrol listesi

## Otomatik kontroller

Proje kökünde, VS Code PowerShell terminalinden:

```powershell
.\scripts\build_release.ps1
```

Bu komut sözdizimini, birim testlerini, çevrimdışı kalite senaryolarını ve
orta/yüksek güvenlik bulgularını kontrol eder; hepsi geçerse `dist/HekoAI.exe`
dosyasını oluşturup SHA-256 değerini gösterir.

## Son kullanıcı kontrolleri

- EXE açılıyor; arka plan, karakter ve giriş alanı doğru görünüyor.
- `+` ile iki sohbet açılıyor; biri çalışırken diğeri kullanılabiliyor.
- Oturum adı değiştiriliyor, kapatılıp Kontrol Merkezi'nden geri açılıyor.
- Mod, özel kişilik, mesaj renkleri ve ses ayarı yeniden başlatınca korunuyor.
- Görev, not ve hatırlatıcı hem sohbetten hem Kontrol Merkezi'nden düzenleniyor.
- PDF ve DOCX okuma çalışıyor; büyük/şifreli/şüpheli belgeler reddediliyor.
- Proje dosyası yazma ve silme yalnızca diff/onay kartından sonra uygulanıyor.
- Heko mesajındaki ses düğmesi okuyor ve durdurma düğmesi sesi kesiyor.
- Mikrofon, uygun ortamda Türkçe sesi yazıya çeviriyor.
- Ekran farkındalığı kapalıyken çalışmıyor; açıldığında her analiz için onay istiyor.
- `%LOCALAPPDATA%\HekoAI\data` altında çalışma verileri oluşuyor.
- EXE yanında `.env`, token veya kişisel JSON dosyası bulunmuyor.

Temiz makine testi için `.env` ve gerekiyorsa `credentials.json` ayrıca,
`HekoAI.exe` ile aynı klasöre konur. Bu gizli dosyalar EXE'ye gömülmez ve Git'e
eklenmez.
