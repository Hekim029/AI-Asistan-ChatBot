# 🚀 Heko — AI Desktop Assistant

<p align="center">
  <b>Masaüstünde yaşayan, konuşan, düşünen kişisel asistan.</b><br/>
  Groq API ile güçlendirilmiş, PySide6 ile inşa edilmiştir.
</p>

---

## ✨ Özellikler

- 💬 **Doğal dil ile sohbet** — Groq API (llama-3.3-70b-versatile) ile güçlü AI yanıtları
- 🎭 **Mod seçimi** — Normal, Eğlenceli, Ciddi, Teknik kişilik modları
- 🎨 **Tema sistemi** — Uyumlu renk çiftleriyle kullanıcı ve AI balonu renkleri ayrı ayrı değişir
- 🧠 **Hafıza** — Kullanıcı bilgilerini ve konuşma geçmişini hatırlar
- 📜 **Geçmiş ekranı** — Tüm konuşma geçmişini ayrı bir pencerede göster
- 🔍 **Mesaj arama** — Konuşmalar içinde anlık arama
- 💡 **Günlük motivasyon** — Her gün bir kez ilham verici mesaj
- ⌨️ **Global kısayol** — `Ctrl+Shift+Space` ile her yerden aç
- 🖱️ **Floating button** — Masaüstünde sürüklenebilir, yanıt gelince yeşil parlar
- 📋 **Mesaj kopyala** — Sağ tık ile kopyalama
- 💬 **Seçim popup** — Metni seç, "Bunu sor" ile direkt sorguya çevir
- 🌌 **Uzay nebula arayüzü** — Yarı saydam, oval köşeli, arka plan görselliği

---

## 🛠️ Teknolojiler

| Teknoloji | Kullanım |
|-----------|---------|
| Python 3.11+ | Ana dil |
| PySide6 | Masaüstü GUI |
| Groq API | LLM (llama-3.3-70b-versatile) |
| python-dotenv | API key yönetimi |
| keyboard | Global kısayol |

---

## 📁 Proje Yapısı

```
ai-desktop-assistant/
├── main.py                  # Giriş noktası, FloatingButton
├── assets/
│   └── arka_plan_3.jpg      # Arka plan görseli
├── core/
│   ├── router.py            # Intent yönlendirme
│   ├── worker.py            # API thread (QThread)
│   ├── intent_detector.py   # Niyet tespiti
│   └── daily_motivation.py  # Günlük motivasyon
├── ui/
│   ├── chat_window.py       # Ana chat arayüzü
│   ├── settings_window.py   # Ayarlar penceresi
│   └── history_window.py    # Geçmiş penceresi
├── services/
│   └── llm_client.py        # Groq API istemcisi
├── memory/
│   ├── context_manager.py   # Konuşma geçmişi
│   └── user_memory.py       # Kullanıcı hafızası
└── utils/
    └── config.py            # Global ayarlar
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
venv\Scripts\activate   # Windows
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

### 5. Çalıştır
```bash
python main.py
```

---

## 🎮 Kullanım

| Eylem | Nasıl |
|-------|-------|
| Asistanı aç/kapat | `Ctrl+Shift+Space` veya floating butona tıkla |
| Mesaj gönder | Yaz + Enter veya ↑ butonuna bas |
| Mod değiştir | ⚙ → Mod Seç |
| Tema değiştir | ⚙ → Tema Seç (ikiye bölünmüş daireler) |
| Mesaj ara | 🔍 butonuna bas |
| Geçmişi gör | 📜 butonuna bas |
| Konuşmayı temizle | ⟳ butonuna bas |
| Mesaj kopyala | Mesaja sağ tıkla |

---

## 🗺️ Yol Haritası

- [x] Temel sohbet
- [x] Intent tespiti (saat, selamlama, hafıza)
- [x] Mod sistemi
- [x] Tema rengi seçimi
- [x] Mesaj arama
- [x] Konuşma geçmişi ekranı
- [x] Günlük motivasyon
- [ ] Dosya aç / ara / yönet
- [ ] Web'de arama yap
- [ ] Uygulama açma
- [ ] Sistem bilgisi (RAM, CPU, batarya)
- [ ] Windows başlangıç ile otomatik açılma

---

## 📄 Lisans

MIT License — dilediğin gibi kullan, geliştir.

---

<p align="center">Made with ❤️ by <a href="https://github.com/Hekim029">Hekim029</a></p>
