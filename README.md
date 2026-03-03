# AI Assistant

Windows'ta çalışan, ekranda sürüklenebilen, LLM destekli masaüstü AI asistanı.

## Özellikler
- Floating button — ekranın istediğin yerine taşıyabilirsin
- Groq API ile hızlı LLM entegrasyonu (Llama 3.3 70B)
- Konuşma geçmişi (uygulama kapatılsa bile silinmez)
- Konuşmayı temizle (buton veya "temizle" yaz)
- Intent detection — saat, selamlama, vedalaşma yerel olarak işlenir
- Global hotkey: `Ctrl+Shift+Space`
- Mesaj kopyalama (sağ tık)
- Uzay temalı arayüz

## Kurulum

1. Repoyu klonla
```
   git clone https://github.com/Hekim029/AI-Asistan-ChatBot.git
```

2. Virtual environment oluştur
```
   python -m venv venv
   venv\Scripts\activate
```

3. Bağımlılıkları kur
```
   pip install -r requirements.txt
```

4. `.env` dosyası oluştur
```
   GROQ_API_KEY=your_key_here
```

5. Çalıştır
```
   python main.py
```

## Proje Yapısı
```
ai-desktop-assistant/
├── main.py              # Uygulama başlangıcı + FloatingButton
├── ui/
│   └── chat_window.py   # Arayüz
├── core/
│   ├── router.py        # Mesaj yönlendirme
│   ├── intent_detector.py # Yerel intent tespiti
│   └── worker.py        # Threading
├── memory/
│   └── context_manager.py # Konuşma geçmişi
├── services/
│   └── llm_client.py    # Groq API istemcisi
└── utils/
    └── config.py        # Ayarlar ve sistem promptu
```

## Teknolojiler
- Python 3.x
- PySide6 (Qt for Python)
- Groq API (Llama 3.3 70B)
- keyboard
- python-dotenv