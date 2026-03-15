# 🚀 Heko — AI Desktop Assistant

<p align="center">
  <b>Masaüstünde yaşayan, konuşan, düşünen kişisel asistan.</b><br/>
  Groq API ile güçlendirilmiş, PySide6 ile inşa edilmiştir.
</p>

---

## ✨ Özellikler

### 💬 Sohbet & AI
- **Doğal dil ile sohbet** — Groq API (llama-3.3-70b-versatile) ile güçlü AI yanıtları
- **Mod seçimi** — Normal, Eğlenceli, Ciddi, Teknik kişilik modları
- **Hafıza** — Kullanıcı bilgilerini ve konuşma geçmişini hatırlar
- **Günlük motivasyon** — Her gün bir kez ilham verici mesaj

### 🖥️ Sistem Kontrolü
- **Uygulama aç/kapat** — Spotify, Chrome, Discord, Steam ve daha fazlası
- **Ses kontrolü** — Ses seviyesi ayarla, kıs, artır, sessiz yap
- **Medya kontrolü** — Sonraki/önceki şarkı, duraklat, devam et
- **Sistem bilgisi** — CPU, RAM, batarya durumu

### 📁 Dosya Yönetimi
- **Klasör aç** — Masaüstü, İndirmeler, Belgeler ve alt klasörler
- **Dosya listele** — Klasör içeriğini göster
- **Dosya ara** — Masaüstü, Belgeler, İndirmelerde ara
- **Dosya sil** — Dosyaları sil

### 🌐 Web & Servisler
- **Web arama** — Google'da ara, YouTube'da ara, harita
- **Site açma** — Instagram, GitHub, Netflix, Trendyol ve daha fazlası
- **Google Calendar** — Takvim etkinlikleri, yaklaşan etkinlikler, tatiller
- **Gmail** — Okunmamış mailler, bugün gelenler, mail gönder

### 🎨 Arayüz
- **Tema sistemi** — 7 renk çifti, kullanıcı ve AI balonu ayrı renk
- **Floating button** — Sürüklenebilir, yanıt gelince yeşil parlar
- **Geçmiş ekranı** — Tüm konuşma geçmişini ayrı pencerede gör
- **Mesaj arama** — Konuşmalar içinde anlık arama
- **Global kısayol** — `Ctrl+Shift+Space` ile her yerden aç
- **Uzay nebula arayüzü** — Yarı saydam, oval köşeli

---

## 🛠️ Teknolojiler

| Teknoloji | Kullanım |
|-----------|---------|
| Python 3.11+ | Ana dil |
| PySide6 | Masaüstü GUI |
| Groq API | LLM (llama-3.3-70b-versatile) |
| Google Calendar API | Takvim entegrasyonu |
| Gmail API | Mail entegrasyonu |
| pycaw | Ses kontrolü |
| keyboard | Global kısayol & medya tuşları |
| psutil | Sistem bilgisi |
| pygetwindow / pyautogui | Pencere yönetimi |
| python-dotenv | API key yönetimi |

---

## 📁 Proje Yapısı

```
ai-desktop-assistant/
├── main.py                    # Giriş noktası, FloatingButton
├── HekoAI.exe                 # Derlenmiş uygulama
├── credentials.json           # Google OAuth kimlik bilgileri
├── assets/
│   └── arka_plan_3.jpg        # Arka plan görseli
├── core/
│   ├── router.py              # Intent yönlendirme
│   ├── worker.py              # API thread (QThread)
│   ├── intent_detector.py     # Niyet tespiti
│   └── daily_motivation.py    # Günlük motivasyon
├── ui/
│   ├── chat_window.py         # Ana chat arayüzü
│   ├── settings_window.py     # Ayarlar penceresi
│   └── history_window.py      # Geçmiş penceresi
├── services/
│   ├── llm_client.py          # Groq API istemcisi
│   ├── calendar_reader.py     # Google Calendar
│   ├── gmail_reader.py        # Gmail entegrasyonu
│   ├── web_controller.py      # Web & site kontrolü
│   ├── app_launcher.py        # Uygulama aç/kapat, ses, medya
│   ├── pc_controller.py       # Dosya yönetimi
│   └── system_info.py         # CPU, RAM, batarya
├── memory/
│   ├── context_manager.py     # Konuşma geçmişi
│   ├── user_memory.py         # Kullanıcı hafızası
│   ├── history.json           # Geçmiş verisi
│   └── token.json             # Google OAuth token
└── utils/
    ├── config.py              # Global ayarlar
    └── startup.py             # Windows başlangıç yönetimi
```

---

## ⚙️ Kurulum

### 1. Repoyu klonla
```bash
git clone https://github.com/Hekim029/AI-Asistan-ChatBot.git
cd AI-Asistan-ChatBot
```

### 2. Sanal ortam oluştur
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Bağımlılıkları yükle
```bash
pip install -r requirements.txt
```

### 4. API anahtarını ayarla
`.env` dosyası oluştur:
```
GROQ_API_KEY=your_api_key_here
```
> Ücretsiz API anahtarı için: [console.groq.com](https://console.groq.com)

### 5. Google API kurulumu (opsiyonel)
- [Google Cloud Console](https://console.cloud.google.com) üzerinden proje oluştur
- Calendar API ve Gmail API'yi etkinleştir
- OAuth 2.0 kimlik bilgilerini indir → `credentials.json` olarak kaydet
- İlk çalıştırmada tarayıcıda Google girişi yapılır, `token.json` otomatik oluşur

### 6. Çalıştır
```bash
python main.py
```

### 7. nircmd kurulumu (ses kontrolü için)
- [nirsoft.net/utils/nircmd.html](https://www.nirsoft.net/utils/nircmd.html) adresinden indir
- `nircmd.exe`'yi proje ana klasörüne koy (`main.py`'in yanına)

---

## 🎮 Kullanım Örnekleri

| Komut | Eylem |
|-------|-------|
| `"spotify aç"` | Spotify'ı başlatır |
| `"spotify kapat"` | Spotify'ı kapatır |
| `"ses 50 yap"` | Ses seviyesini %50'ye ayarlar |
| `"sonraki şarkı"` | Sonraki parçaya geçer |
| `"masaüstü 2209A klasörünü aç"` | İlgili klasörü açar |
| `"indirmeleri listele"` | İndirmeler klasörünü listeler |
| `"bayrama kaç gün var"` | Takvimden kontrol eder |
| `"okunmamış maillerim"` | Gmail'den getirir |
| `"youtube'da lo-fi ara"` | YouTube'da arama yapar |
| `"sistem durumu"` | CPU, RAM, pil bilgisi |

---

## 🗺️ Yol Haritası

- [x] Temel sohbet & Groq API
- [x] Intent tespiti
- [x] Mod & tema sistemi
- [x] Mesaj arama & geçmiş ekranı
- [x] Google Calendar entegrasyonu
- [x] Gmail entegrasyonu
- [x] Web arama & site açma
- [x] Uygulama aç/kapat
- [x] Ses & medya kontrolü
- [x] Dosya/klasör yönetimi
- [x] Sistem bilgisi
- [x] HekoAI.exe build
- [ ] Windows otomatik başlangıç
- [ ] Mail içeriği okuma
- [ ] Hava durumu

---

## 📄 Lisans

MIT License — dilediğin gibi kullan, geliştir.

---

<p align="center">Made with ❤️ by <a href="https://github.com/Hekim029">Hekim029</a></p>