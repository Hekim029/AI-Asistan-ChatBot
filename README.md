# AI Assistant

Windows'ta çalışan, ekranda sürüklenebilen, LLM destekli masaüstü AI asistanı.

## Özellikler
- Floating button — ekranın istediğin yerine taşıyabilirsin
- Groq API ile hızlı LLM entegrasyonu
- Konuşma geçmişi (uygulama kapatılsa bile silinmez)
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

## Teknolojiler
- Python 3.x
- PySide6 (Qt for Python)
- Groq API (Llama 3.3 70B)
- keyboard