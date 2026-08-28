"""
Heko'nun araç (tool) tanımları ve çalıştırıcısı.

MANTIK:
  Eski sistemde "intent tahmin et -> o fonksiyona git -> parametreleri
  fonksiyon kendi çıkarsın" vardı. Bu iki ayrı tahmin demekti.

  Yeni sistemde LLM'e araçların TARİFİNİ veriyoruz. LLM tek seferde hem
  "hangi araç" hem "hangi parametreler" kararını veriyor.

  Bu dosyada iki şey var:
    1) TOOLS      -> LLM'e gönderilen araç tarifleri (JSON şema)
    2) execute()  -> LLM'in seçtiği aracı gerçekten çalıştıran fonksiyon
"""

from datetime import datetime, timedelta
import time
import math
import re


# ═════════════════════════════════════════════
#  1. ARAÇ TARİFLERİ
#
#  Format OpenAI/Groq standardı:
#    type: "function"
#    function:
#      name        -> fonksiyon adı (execute() içinde eşleşir)
#      description -> LLM bunu okuyup karar verir. NET yazılmalı!
#      parameters  -> JSON Schema formatında parametre tanımı
# ═════════════════════════════════════════════

TOOLS = [
    # ── Zaman ────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Şu anki saati ve tarihi döndürür. Kullanıcı saati sorduğunda kullan.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },

    # ── Dosya / Klasör ───────────────────────
    {
        "type": "function",
        "function": {
            "name": "open_folder",
            "description": (
                "Bilgisayarda bir klasör veya dosya açar. "
                "Kullanıcı bir klasörü/dosyayı açmak, ona gitmek veya görmek istediğinde kullan. "
                "Yazım hatası varsa sistem otomatik en yakın eşleşmeyi bulur."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": (
                            "Açılacak klasör veya dosyanın SADECE adı. "
                            "Fiil, ek veya soru edatı ekleme. "
                            "Örnek: 'ChatBot klasörüme git' -> 'ChatBot'. "
                            "Sadece sistem klasörü açılacaksa boş bırak."
                        ),
                    },
                    "location": {
                        "type": "string",
                        "enum": ["masaüstü", "indirmeler", "belgeler",
                                 "resimler", "müzik", "videolar"],
                        "description": "Hangi ana klasörde aranacak. Belirtilmemişse masaüstü.",
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_folder",
            "description": "Bir klasörün içindekileri listeler. 'X klasöründe ne var' gibi sorularda kullan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "enum": ["masaüstü", "indirmeler", "belgeler",
                                 "resimler", "müzik", "videolar"],
                        "description": "Listelenecek klasör.",
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_file",
            "description": "Bilgisayarda dosya arar. Kullanıcı bir dosyayı bulmak istediğinde kullan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Aranacak dosya adı veya parçası."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": (
                "Bir dosyayı KALICI OLARAK SİLMEZ; Windows çöp kutusuna taşır. "
                "Kullanıcı açıkça silmek istediğinde bu aracı çağır. Araç ilk "
                "çağrıda yalnızca gerçek onay kaydı oluşturur."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Silinecek dosyanın adı."},
                },
                "required": ["query"],
            },
        },
    },

    # ── Uygulama ─────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "launch_app",
            "description": (
                "Bilgisayarda bir uygulama açar (Chrome, Spotify, VS Code, Discord, "
                "Word, Excel, hesap makinesi vb.). Web sitesi açmak için bunu DEĞİL "
                "open_website aracını kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Açılacak uygulamanın adı. Örn: 'spotify', 'chrome', 'vs code'.",
                    },
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_app",
            "description": "Çalışan bir uygulamayı veya tarayıcı sekmesini kapatır.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Kapatılacak uygulamanın adı."},
                },
                "required": ["app_name"],
            },
        },
    },

    # ── Ses / Medya ──────────────────────────
    {
        "type": "function",
        "function": {
            "name": "control_volume",
            "description": "Bilgisayarın ses seviyesini ayarlar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["up", "down", "mute", "set"],
                        "description": "up=artır, down=kıs, mute=sessize al, set=belirli seviyeye ayarla",
                    },
                    "level": {
                        "type": "integer",
                        "description": "action='set' ise hedef seviye (0-100).",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_media",
            "description": (
                "Müzik/video oynatmayı kontrol eder. SADECE komut verildiğinde kullan. "
                "'Ne çalıyor' gibi SORULAR için bu aracı kullanma, normal cevap ver."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["next", "previous", "pause", "play"],
                        "description": "next=sonraki, previous=önceki, pause=durdur, play=devam et",
                    },
                },
                "required": ["action"],
            },
        },
    },

    # ── Web ──────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": (
                "Bir web sitesini SADECE ana sayfasıyla açar (YouTube, Instagram, "
                "GitHub, Netflix, Trendyol vb.). Kullanıcı sitede bir şey aramak, "
                "izlemek veya dinlemek istiyorsa bu aracı KULLANMA, onun yerine "
                "SADECE search_web kullan. İkisini aynı istek için birlikte çağırma — "
                "bir istek ya site açmadır ya aramadır, ikisi birden değil."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "site": {
                        "type": "string",
                        "description": "Açılacak sitenin adı. Örn: 'youtube', 'github', 'instagram'.",
                    },
                },
                "required": ["site"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Bir şeyi arar VE MÜMKÜNSE DİREKT AÇAR/ÇALAR (arama sayfasında "
                "bırakmaz). Kullanıcı bir şarkı/video açmak, çalmak, izlemek, "
                "dinlemek veya aramak istediğinde kullan (örn: 'youtube de X aç', "
                "'X şarkısını çal', 'X'i ara'). Bu araç zaten siteyi de açar — "
                "aynı istek için AYRICA open_website çağırma."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Aranacak ifade. Platform adını ve fiilleri ÇIKAR. "
                            "Örn: 'youtube de lofi müzik aç' -> 'lofi müzik'"
                        ),
                    },
                    "platform": {
                        "type": "string",
                        "enum": ["google", "youtube", "spotify", "maps"],
                        "description": "Nerede aranacak. Belirtilmemişse google.",
                    },
                },
                "required": ["query", "platform"],
            },
        },
    },

    # ── Takvim ───────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_calendar",
            "description": (
                "Google Takvim'deki etkinlikleri getirir. Tatiller ve bayramlar da dahildir. "
                "Kullanıcı takvimini, planlarını, bir güne kaç gün kaldığını sorduğunda kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "enum": ["today", "tomorrow", "week", "all"],
                        "description": "Hangi dönem. Belirsizse 'all' kullan.",
                    },
                },
                "required": ["filter"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": (
                "Google Takvim'e yeni etkinlik ekler. Kullanıcı onayı gerekir. "
                "Başlangıç ve bitişi yerel saatli ISO 8601 olarak hesapla."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "start_at": {"type": "string"},
                    "end_at": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title", "start_at", "end_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_calendar_event",
            "description": (
                "Yaklaşan bir Google Takvim etkinliğini başlık sorgusuyla bulup "
                "değiştirir. Yalnızca değişecek alanları doldur. Kullanıcı onayı gerekir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "title": {"type": "string"},
                    "start_at": {"type": "string"},
                    "end_at": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_calendar_event",
            "description": (
                "Başlık sorgusuyla eşleşen yaklaşan Google Takvim etkinliğini siler. "
                "Kullanıcı onayı gerekir."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },

    # ── Gmail ────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_emails",
            "description": "Gmail'den mailleri okur.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "enum": ["unread", "today", "search"],
                        "description": "unread=okunmamış, today=bugünkü, search=arama",
                    },
                    "query": {
                        "type": "string",
                        "description": "filter='search' ise aranacak kişi/konu.",
                    },
                },
                "required": ["filter"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_email",
            "description": (
                "Gönderen, konu veya anahtar kelimeyle eşleşen en yeni Gmail "
                "mesajının içeriğini okur."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Gmail arama ifadesi; gönderen, konu veya kelime.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Gmail üzerinden mail gönderir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to":      {"type": "string", "description": "Alıcının e-posta adresi."},
                    "subject": {"type": "string", "description": "Mailin konusu."},
                    "body":    {"type": "string", "description": "Mailin içeriği."},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },

    # ── Sistem ───────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "Bilgisayarın CPU, RAM ve batarya durumunu döndürür.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },

    # ── Hafıza ───────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "remember_about_user",
            "description": (
                "Kullanıcı hakkında kalıcı bilgi kaydeder. Kullanıcı kendisi hakkında "
                "bir şey paylaştığında kullan (isim, meslek, tercih, hedef, günlük düzen). "
                "Birden fazla bilgi varsa bu aracı BİRDEN FAZLA KEZ çağır."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["name", "profession", "preference", "schedule", "goal", "misc"],
                        "description": "Bilginin türü.",
                    },
                    "value": {
                        "type": "string",
                        "description": (
                            "Kaydedilecek bilgi, SADE haliyle. "
                            "Örn: 'adım Ali' -> 'Ali', 'yazılımcıyım' -> 'yazılımcı'"
                        ),
                    },
                },
                "required": ["category", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_history",
            "description": "Konuşma geçmişini siler. Kullanıcı açıkça istediğinde kullan.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": (
                "Gelecekte kullanıcıya gösterilecek kalıcı bir hatırlatıcı oluşturur. "
                "'20 dakika sonra...', 'yarın saat 9' veya belirli tarih/saat "
                "isteklerinde kullan. due_at değerini ŞU AN bilgisini temel alarak "
                "yerel saat diliminde ISO 8601 biçiminde hesapla."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Zaman ifadesi çıkarılmış, hatırlatılacak kısa metin.",
                    },
                    "due_at": {
                        "type": "string",
                        "description": "Yerel saatle ISO 8601 tarih-saat. Örn: 2026-07-30T18:00:00+03:00",
                    },
                },
                "required": ["text", "due_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "Bekleyen hatırlatıcıları tarih, saat ve kimlikleriyle listeler.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_reminder",
            "description": (
                "Bekleyen tek bir hatırlatıcıyı iptal eder. Listeden alınan kimlik "
                "veya hatırlatıcı metninin ayırt edici bir bölümünü kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_id": {"type": "string", "description": "Hatırlatıcı kimliği."},
                    "query": {"type": "string", "description": "Hatırlatıcı metninden ayırt edici bölüm."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Bir şehir için güncel hava durumunu veya tahmini getirir. "
                "Kullanıcı şehir belirtmezse varsayılan şehir olarak İstanbul kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Şehir veya ilçe adı. Belirtilmezse İstanbul.",
                    },
                    "period": {
                        "type": "string",
                        "enum": ["now", "today", "tomorrow", "week"],
                        "description": "Şu an, bugün, yarın veya yedi günlük tahmin.",
                    },
                },
                "required": ["period"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": (
                "Yerel yapılacaklar listesine kalıcı görev ekler. Kullanıcı yalnızca "
                "hatırlatılmak istiyorsa create_reminder, yapılacak iş kaydetmek "
                "istiyorsa bu aracı kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "due_at": {
                        "type": "string",
                        "description": "Varsa yerel saatli ISO 8601 son tarih.",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "Bekleyen yerel görevleri listeler.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Bir görevi kimliği veya başlık parçasıyla tamamlandı işaretler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_note",
            "description": "Kullanıcının söylediği kısa notu yerel olarak kalıcı kaydeder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Notun aranmasını kolaylaştıran 1-3 kısa konu etiketi. "
                            "Örn. arayüz rengi notu için ['proje', 'arayüz', 'tasarım']."
                        ),
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_notes",
            "description": "Yerel notları listeler veya anahtar kelimeyle arar.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_briefing",
            "description": (
                "Kullanıcının bekleyen görevlerini, yaklaşan hatırlatıcılarını ve "
                "bugünkü hava durumunu tek günlük özette birleştirir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Hava durumu şehri; belirtilmezse İstanbul.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_user_memory",
            "description": (
                "Heko'nun kullanıcı hakkında kalıcı olarak hatırladığı bilgileri "
                "listeler. Kullanıcı 'benim hakkımda ne biliyorsun' dediğinde kullan."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget_user_memory",
            "description": (
                "Kullanıcının belirttiği tek bir kalıcı hafıza kaydını unutur. "
                "İşlem açık onay gerektirir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "name", "profession", "preferences",
                            "schedule", "goals", "misc",
                        ],
                    },
                    "value": {
                        "type": "string",
                        "description": "Unutulacak bilginin tam değeri.",
                    },
                },
                "required": ["category", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_pending_action",
            "description": (
                "Bekleyen yüksek riskli işlemi çalıştırır. SADECE kullanıcı, "
                "Heko'nun gösterdiği işlem özetini gördükten sonra açıkça "
                "'onaylıyorum', 'evet yap' veya eşdeğeri bir onay verdiyse kullan."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_pending_action",
            "description": (
                "Bekleyen yüksek riskli işlemi iptal eder. Kullanıcı vazgeçtiğinde, "
                "'hayır', 'iptal' veya eşdeğeri bir cevap verdiğinde kullan."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

TOOLS.append({
    "type": "function",
    "function": {
        "name": "get_shared_activity",
        "description": (
            "Diğer sohbet pencerelerinde yapılan son çalışmaların özetini getirir. "
            "Kullanıcı başka pencere, diğer sohbet, kod penceresi veya araştırma "
            "penceresinin sonucunu sorduğunda kullan."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 20}
            },
            "required": [],
        },
    },
})

TOOLS.append({
    "type": "function",
    "function": {
        "name": "analyze_screen",
        "description": (
            "Kullanıcının açık isteği ve ayrı onayı sonrasında ekrandan tek kare "
            "alıp görsel olarak yorumlar. İlk çağrı yalnızca onay kaydı oluşturur; "
            "görüntü almaz. 'Ekranıma bak' ve 'ekranımda ne var' isteklerinde kullan."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Kullanıcının ekran hakkında sorduğu kısa soru."
                }
            },
            "required": [],
        },
    },
})

TOOLS.append({
    "type": "function",
    "function": {
        "name": "read_document",
        "description": (
            "Kullanıcının açıkça verdiği PDF veya DOCX belgesinden yalnızca "
            "metin çıkarır. Belgeyi okuma, inceleme veya özetleme isteklerinde kullan."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Okunacak .pdf veya .docx dosyasının tam yolu."
                }
            },
            "required": ["path"],
        },
    },
})

TOOLS.extend([
    {
        "type": "function",
        "function": {
            "name": "list_project_files",
            "description": "Etkin kod projesindeki dosyaları salt okunur listeler.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "İsteğe bağlı dosya adı filtresi."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_project_file",
            "description": "Etkin projedeki bir kod/metin dosyasını göreli yoluyla okur ve sürüm karmasını döndürür.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Örnek: services/llm_client.py"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_project_file",
            "description": (
                "Etkin projede bir metin/kod dosyası oluşturur veya tüm içeriğini günceller. "
                "Önce diff önizlemesi ve kullanıcı onayı ister. Mevcut dosya için önce "
                "read_project_file kullan ve dönen sha256 değerini expected_sha256 olarak ver."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Proje içindeki göreli dosya yolu."},
                    "content": {"type": "string", "description": "Dosyanın yeni tam içeriği."},
                    "expected_sha256": {"type": "string", "description": "Okunan mevcut sürümün sha256 değeri."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_project_file",
            "description": (
                "Etkin proje içindeki göreli yolu verilen bir dosyayı kalıcı "
                "silmek yerine Windows Çöp Kutusu'na taşır. Açık onay gerektirir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Proje içindeki göreli dosya yolu."
                    },
                },
                "required": ["path"],
            },
        },
    },
])

TOOLS.append({
    "type": "function",
    "function": {
        "name": "read_text_file",
        "description": (
            "Kullanıcının açıkça belirttiği küçük bir metin veya kod dosyasını "
            "salt okunur biçimde okur. Dosyayı açıklama, inceleme veya özetleme "
            "isteklerinde kullan. Hassas dosyalar ve ikili dosyalar engellenir."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Okunacak dosyanın tam yolu."}
            },
            "required": ["path"],
        },
    },
})


# ═════════════════════════════════════════════
#  2. ARAÇ ÇALIŞTIRICI
#
#  LLM bir araç seçtiğinde burası devreye girer.
#  Her araç, mevcut servis dosyalarındaki fonksiyonları çağırır.
#  Servis dosyalarına DOKUNMUYORUZ — sadece etraflarını sarmalıyoruz.
# ═════════════════════════════════════════════

class ToolExecutor:
    """
    Araçları çalıştırır.

    Router bunu bir kez oluşturur ve LLM her araç çağırdığında
    execute() metodunu kullanır.
    """

    CONFIRMATION_TTL = timedelta(minutes=5)
    HIGH_RISK_TOOLS = {
        "delete_file",
        "delete_project_file",
        "send_email",
        "create_calendar_event",
        "update_calendar_event",
        "delete_calendar_event",
        "clear_history",
        "forget_user_memory",
        "update_project_file",
        "close_app",
        "analyze_screen",
    }

    def __init__(
        self,
        user_memory,
        context_manager,
        reminder_manager=None,
        task_manager=None,
        shared_workspace=None,
        session_id="main",
    ):
        # Hafıza nesnelerini router'dan alıyoruz (yeniden oluşturmuyoruz)
        self.user_memory = user_memory
        self.context = context_manager
        self.reminders = reminder_manager
        self.tasks = task_manager
        self.shared_workspace = shared_workspace
        self.session_id = session_id
        self.tasks = task_manager
        self._pending_action: dict | None = None

    def execute(self, tool_name: str, args: dict) -> str:
        """
        Araç adına göre ilgili metodu çağırır.

        getattr(self, f"_{tool_name}", None) -> "_get_time" gibi bir metod
        var mı diye bakar. Varsa döndürür, yoksa None.
        Böylece uzun if/elif zinciri yazmaya gerek kalmıyor.
        """
        args = args if isinstance(args, dict) else {}

        if tool_name == "confirm_pending_action":
            return self._confirm_pending_action(args)
        if tool_name == "cancel_pending_action":
            return self._cancel_pending_action(args)

        if tool_name == "analyze_screen":
            import utils.config as config
            if not getattr(config, "SCREEN_VISION_ENABLED", False):
                return (
                    "Ekran farkındalığı şu anda kapalı. Kullanmak istersen "
                    "Ayarlar > Sistem bölümündeki deneysel özelliği açıp "
                    "ayarları kaydetmelisin."
                )

        if tool_name in self.HIGH_RISK_TOOLS:
            return self._request_confirmation(tool_name, args)

        handler = getattr(self, f"_{tool_name}", None)
        if handler is None:
            return f"⚠️ Bilinmeyen araç: {tool_name}"

        try:
            return handler(args)
        except Exception as e:
            from services.error_logger import log_exception
            from services.security import safe_error
            log_exception(f"tool.{tool_name}", e)
            return f"⚠️ '{tool_name}' çalıştırılırken hata: {safe_error(e)}"

    def _request_confirmation(self, tool_name: str, args: dict) -> str:
        if self._pending_action:
            current = self._action_summary(
                self._pending_action["tool_name"],
                self._pending_action["args"],
            )
            return (
                "ONAY_GEREKLİ: Önce mevcut bekleyen işlem çözülmeli.\n"
                f"Bekleyen işlem: {current}"
            )

        # Proje yazma isteği, bekleyen bir onay oluşturmadan önce diff ve yol
        # doğrulamasından geçsin. Aksi halde geçersiz bir yol bile beş dakika
        # boyunca onay kuyruğunu gereksiz yere kilitleyebiliyordu.
        summary = self._action_summary(tool_name, args)
        if summary.startswith((
            "Geçersiz proje değişikliği:",
            "Geçersiz proje silme isteği:",
        )):
            return f"⚠️ {summary}"

        self._pending_action = {
            "tool_name": tool_name,
            "args": dict(args),
            "created_at": datetime.now(),
            # Duvar saati kullanıcı/Windows tarafından değiştirilebilir.
            # Süre aşımı için yalnızca ileri giden monotonic sayaç kullanılır.
            "expires_at": time.monotonic()
            + self.CONFIRMATION_TTL.total_seconds(),
        }
        return (
            "ONAY_GEREKLİ: İşlem henüz yapılmadı.\n"
            f"İşlem: {summary}\n"
            "Kullanıcıdan bu özeti göstererek açık onay iste. "
            "Onay verirse confirm_pending_action, vazgeçerse "
            "cancel_pending_action aracını çağır."
        )

    def _confirm_pending_action(self, args: dict) -> str:
        pending = self._pending_action
        if not pending:
            return "Bekleyen bir işlem yok."

        if self._pending_is_expired(pending):
            self._pending_action = None
            return "Bekleyen işlemin onay süresi doldu; işlem yapılmadı."

        self._pending_action = None
        tool_name = pending["tool_name"]
        handler = getattr(self, f"_{tool_name}", None)
        if handler is None:
            return f"⚠️ Bilinmeyen araç: {tool_name}"

        try:
            return handler(pending["args"])
        except Exception as e:
            from services.error_logger import log_exception
            from services.security import safe_error
            log_exception(f"tool.{tool_name}", e)
            return f"⚠️ '{tool_name}' çalıştırılırken hata: {safe_error(e)}"

    def _cancel_pending_action(self, args: dict) -> str:
        pending = self._pending_action
        if not pending:
            return "Bekleyen bir işlem yok."

        if self._pending_is_expired(pending):
            self._pending_action = None
            return "Bekleyen işlemin onay süresi doldu; işlem zaten yapılmadı."

        summary = self._action_summary(
            pending["tool_name"],
            pending["args"],
        )
        self._pending_action = None
        return f"İptal edildi; işlem yapılmadı: {summary}"

    @staticmethod
    def _pending_is_expired(pending: dict) -> bool:
        return time.monotonic() >= pending.get("expires_at", 0)

    def _action_summary(self, tool_name: str, args: dict) -> str:
        if tool_name == "delete_file":
            return (
                f"'{args.get('query', '')}' adlı dosyayı "
                "çöp kutusuna taşımak"
            )
        if tool_name == "delete_project_file":
            try:
                preview = self._project_workspace().preview_delete(
                    args.get("path", "")
                )
                return (
                    f"Proje içindeki '{preview['path']}' dosyasını "
                    f"Windows Çöp Kutusu'na taşımak ({preview['size']} bayt)"
                )
            except Exception as exc:
                from services.security import safe_error
                return f"Geçersiz proje silme isteği: {safe_error(exc)}"
        if tool_name == "send_email":
            body = str(args.get("body", "")).strip().replace("\n", " ")
            if len(body) > 240:
                body = body[:237] + "..."
            return (
                f"{args.get('to', '')} adresine "
                f"'{args.get('subject', '')}' konulu mail göndermek. "
                f"İçerik: {body}"
            )
        if tool_name == "create_calendar_event":
            return (
                f"Google Takvim'e '{args.get('title', '')}' etkinliğini "
                f"{args.get('start_at', '')}–{args.get('end_at', '')} arasında eklemek"
            )
        if tool_name == "update_calendar_event":
            changes = ", ".join(
                f"{key}={value}"
                for key, value in args.items()
                if key != "query" and value
            ) or "belirtilen alanları değiştirmek"
            return (
                f"Google Takvim'de '{args.get('query', '')}' etkinliğini "
                f"güncellemek: {changes}"
            )
        if tool_name == "delete_calendar_event":
            return (
                f"Google Takvim'de '{args.get('query', '')}' ile eşleşen "
                "yaklaşan etkinliği silmek"
            )
        if tool_name == "clear_history":
            return "tüm konuşma geçmişini temizlemek"
        if tool_name == "forget_user_memory":
            return (
                f"'{args.get('category', '')}' kategorisindeki "
                f"'{args.get('value', '')}' bilgisini unutmak"
            )
        if tool_name == "update_project_file":
            try:
                preview = self._project_workspace().preview_change(
                    args.get("path", ""), args.get("content", ""),
                    args.get("expected_sha256", ""),
                )
                additions = sum(
                    1 for line in preview["diff"].splitlines()
                    if line.startswith("+") and not line.startswith("+++")
                )
                deletions = sum(
                    1 for line in preview["diff"].splitlines()
                    if line.startswith("-") and not line.startswith("---")
                )
                state = "yeni dosya" if preview["is_new"] else "mevcut dosya"
                return (
                    f"Proje dosyasını güncellemek: {preview['path']} "
                    f"({state}, +{additions} / -{deletions} satır)"
                )
            except Exception as exc:
                from services.security import safe_error
                return f"Geçersiz proje değişikliği: {safe_error(exc)}"
        if tool_name == "close_app":
            return (
                f"'{args.get('app_name', '')}' uygulamasını zorla kapatmak. "
                "Kaydedilmemiş çalışmalar kaybolabilir"
            )
        if tool_name == "analyze_screen":
            return (
                "Ekrandan tek bir görüntü almak ve görsel analiz için Groq'a "
                "göndermek. Görüntü diske kaydedilmeyecek ve işlemden sonra "
                "bellekten bırakılacak"
            )
        return tool_name

    def attach_pending_screen_capture(
        self, image_data: str, width: int, height: int
    ) -> None:
        """UI ana iş parçacığında alınan kareyi yalnızca bekleyen onaya bağlar."""
        pending = self._pending_action
        if not pending or pending.get("tool_name") != "analyze_screen":
            raise ValueError("Bekleyen bir ekran analizi onayı yok.")
        if self._pending_is_expired(pending):
            self._pending_action = None
            raise ValueError("Ekran analizi onay süresi doldu.")
        from services.screen_vision import validate_screen_image_data
        pending["args"]["_image_data"] = validate_screen_image_data(image_data)
        pending["args"]["_image_width"] = max(1, min(int(width), 10_000))
        pending["args"]["_image_height"] = max(1, min(int(height), 10_000))

    def has_pending_action(self) -> bool:
        return self._pending_action is not None

    def pending_action_info(self) -> dict | None:
        pending = self._pending_action
        if not pending:
            return None
        remaining = max(
            0,
            math.ceil(pending.get("expires_at", 0) - time.monotonic()),
        )
        info = {
            "tool_name": pending["tool_name"],
            "summary": self._action_summary(
                pending["tool_name"], pending["args"]
            ),
            "seconds_remaining": remaining,
        }
        if pending["tool_name"] == "update_project_file":
            try:
                preview = self._project_workspace().preview_change(
                    pending["args"].get("path", ""),
                    pending["args"].get("content", ""),
                    pending["args"].get("expected_sha256", ""),
                )
                info["project_change"] = {
                    key: preview[key]
                    for key in (
                        "path", "old_sha256", "new_sha256", "diff",
                        "changed", "is_new",
                    )
                }
            except Exception as exc:
                from services.security import safe_error
                info["project_change_error"] = safe_error(exc)
        return info

    # ─────────────────────────────────────────
    #  Zaman
    # ─────────────────────────────────────────

    def _get_time(self, args: dict) -> str:
        now = datetime.now()
        gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe",
                  "Cuma", "Cumartesi", "Pazar"]
        return (
            f"Saat: {now.strftime('%H:%M')}, "
            f"Tarih: {now.strftime('%d.%m.%Y')}, "
            f"Gün: {gunler[now.weekday()]}"
        )

    # ─────────────────────────────────────────
    #  Dosya / Klasör
    # ─────────────────────────────────────────

    def _reminder_store(self):
        if self.reminders is None:
            from services.reminder_manager import ReminderManager
            self.reminders = ReminderManager()
        return self.reminders

    def _create_reminder(self, args: dict) -> str:
        item = self._reminder_store().add(
            args.get("text", ""),
            args.get("due_at", ""),
        )
        due = datetime.fromisoformat(item["due_at"]).astimezone()
        return (
            f"Hatırlatıcı kuruldu: {due.strftime('%d.%m.%Y %H:%M')} — "
            f"{item['text']} (kimlik: {item['id']})"
        )

    def _list_reminders(self, args: dict) -> str:
        items = self._reminder_store().pending()
        if not items:
            return "Bekleyen hatırlatıcı yok."
        lines = []
        for item in items:
            due = datetime.fromisoformat(item["due_at"]).astimezone()
            lines.append(
                f"- [{item['id']}] {due.strftime('%d.%m.%Y %H:%M')} — {item['text']}"
            )
        return "Bekleyen hatırlatıcılar:\n" + "\n".join(lines)

    def _cancel_reminder(self, args: dict) -> str:
        item = self._reminder_store().cancel(
            reminder_id=args.get("reminder_id", ""),
            query=args.get("query", ""),
        )
        if not item:
            return "Eşleşen bekleyen hatırlatıcı bulunamadı."
        return f"Hatırlatıcı iptal edildi: {item['text']} (kimlik: {item['id']})"

    def _get_weather(self, args: dict) -> str:
        from services.weather_service import get_weather
        city = (args.get("city") or "İstanbul").strip()
        period = args.get("period") or "today"
        return get_weather(city, period)

    def _task_store(self):
        if self.tasks is None:
            from services.task_manager import TaskManager
            self.tasks = TaskManager()
        return self.tasks

    def _add_task(self, args: dict) -> str:
        item = self._task_store().add_task(
            args.get("title", ""),
            args.get("due_at", ""),
        )
        due = ""
        if item["due_at"]:
            due_dt = datetime.fromisoformat(item["due_at"]).astimezone()
            due = f", son tarih {due_dt.strftime('%d.%m.%Y %H:%M')}"
        return f"Görev eklendi: {item['title']} [{item['id']}]{due}"

    def _list_tasks(self, args: dict) -> str:
        items = self._task_store().pending_tasks()
        if not items:
            return "Bekleyen görev yok."
        lines = []
        for item in items:
            due = ""
            if item.get("due_at"):
                due_dt = datetime.fromisoformat(item["due_at"]).astimezone()
                state = (
                    "GECİKMİŞ"
                    if due_dt < datetime.now().astimezone()
                    else "son tarih"
                )
                due = f" — {state}: {due_dt.strftime('%d.%m.%Y %H:%M')}"
            lines.append(f"- {item['title']}{due}")
        return "Bekleyen görevler:\n" + "\n".join(lines)

    def _complete_task(self, args: dict) -> str:
        item = self._task_store().complete_task(
            task_id=args.get("task_id", ""),
            query=args.get("query", ""),
        )
        if not item:
            return "Eşleşen bekleyen görev bulunamadı."
        return f"Görev tamamlandı: {item['title']}"

    def _add_note(self, args: dict) -> str:
        item = self._task_store().add_note(
            args.get("text", ""),
            args.get("tags", []),
        )
        if item.get("_duplicate"):
            return (
                f"Bu not zaten kayıtlı; ikinci kez eklenmedi: "
                f"{item['text']} [{item['id']}]"
            )
        return f"Not kaydedildi: {item['text']} [{item['id']}]"

    def _list_notes(self, args: dict) -> str:
        items = self._task_store().notes(args.get("query", ""))
        if not items:
            return "Eşleşen not bulunamadı."
        heading = (
            "KESİN EŞLEŞME YOK. Yalnızca olası son not önerileri:"
            if items[0].get("_suggestion")
            else "Notlar:"
        )
        return heading + "\n" + "\n".join(
            f"- {item['text']}" for item in items[:20]
        )

    def _get_daily_briefing(self, args: dict) -> str:
        tasks = self._task_store().pending_tasks()
        reminders = self._reminder_store().pending()
        task_lines = (
            "\n".join(f"- {item['title']}" for item in tasks[:8])
            if tasks else "- Bekleyen görev yok."
        )
        reminder_lines = []
        for item in reminders[:8]:
            due = datetime.fromisoformat(item["due_at"]).astimezone()
            reminder_lines.append(
                f"- {due.strftime('%d.%m %H:%M')} — {item['text']}"
            )
        if not reminder_lines:
            reminder_lines = ["- Yaklaşan hatırlatıcı yok."]
        try:
            from services.weather_service import get_weather
            weather = get_weather((args.get("city") or "İstanbul").strip(), "today")
        except Exception:
            weather = "Hava durumu şu anda alınamadı."
        return (
            "GÜNLÜK ÖZET\n\n"
            f"Görevler:\n{task_lines}\n\n"
            f"Hatırlatıcılar:\n{chr(10).join(reminder_lines)}\n\n"
            f"Hava:\n{weather}"
        )

    def _open_folder(self, args: dict) -> str:
        from services.pc_controller import FOLDERS, _smart_open, _get_desktop

        name     = (args.get("name") or "").strip()
        location = (args.get("location") or "masaüstü").lower()
        base     = FOLDERS.get(location, _get_desktop())

        return _smart_open(name, base)

    def _list_folder(self, args: dict) -> str:
        from services.pc_controller import FOLDERS, _list_folder, _get_desktop

        location = (args.get("location") or "masaüstü").lower()
        base     = FOLDERS.get(location, _get_desktop())
        return _list_folder(base, location)

    def _search_file(self, args: dict) -> str:
        from services.pc_controller import _search_file
        return _search_file(args.get("query", ""))

    def _delete_file(self, args: dict) -> str:
        from services.pc_controller import _delete_file
        return _delete_file(args.get("query", ""))

    def _delete_project_file(self, args: dict) -> str:
        item = self._project_workspace().trash_file(args.get("path", ""))
        return f"Proje dosyası Çöp Kutusu'na taşındı: {item['path']}"

    # ─────────────────────────────────────────
    #  Uygulama
    # ─────────────────────────────────────────

    def _launch_app(self, args: dict) -> str:
        from services.app_launcher import launch_app
        name   = args.get("app_name", "")
        result = launch_app(name)
        return result or f"'{name}' uygulaması bulunamadı."

    def _close_app(self, args: dict) -> str:
        from services.app_launcher import close_app
        name   = args.get("app_name", "")
        result = close_app(f"{name} kapat")
        return result or f"'{name}' kapatılamadı."

    # ─────────────────────────────────────────
    #  Ses / Medya
    # ─────────────────────────────────────────

    def _control_volume(self, args: dict) -> str:
        from services.app_launcher import volume_control

        action = args.get("action", "")
        level  = args.get("level")

        # volume_control() metin bekliyor, action'ı metne çeviriyoruz
        text_map = {
            "up":   "sesi artır",
            "down": "sesi kıs",
            "mute": "sessiz",
            "set":  f"ses {level}" if level is not None else "ses 50",
        }
        result = volume_control(text_map.get(action, "sesi kıs"))
        return result or "Ses komutu uygulanamadı."

    def _control_media(self, args: dict) -> str:
        from services.app_launcher import media_control

        text_map = {
            "next":     "sonraki",
            "previous": "önceki",
            "pause":    "durdur",
            "play":     "devam",
        }
        result = media_control(text_map.get(args.get("action", ""), "durdur"))
        return result or "Medya komutu uygulanamadı."

    # ─────────────────────────────────────────
    #  Web
    # ─────────────────────────────────────────

    def _open_website(self, args: dict) -> str:
        import webbrowser
        from services.security import clean_single_line, validate_https_url

        sites = {
            "youtube":     "https://www.youtube.com",
            "instagram":   "https://instagram.com",
            "twitter":     "https://twitter.com",
            "x":           "https://x.com",
            "github":      "https://github.com",
            "gmail":       "https://mail.google.com",
            "netflix":     "https://netflix.com",
            "trendyol":    "https://www.trendyol.com",
            "hepsiburada": "https://www.hepsiburada.com",
            "google":      "https://www.google.com",
            "fırat":       "https://firat.edu.tr",
            "firat":       "https://firat.edu.tr",
        }

        site = clean_single_line(
            args.get("site", ""), name="Site", max_length=253
        ).lower()
        url  = sites.get(site)

        if not url:
            # Tanımlı değilse doğrudan domain olarak dene
            if "." in site and not any(char in site for char in "/\\@?#"):
                url = f"https://{site}"
            else:
                return f"'{site}' sitesini tanımıyorum."

        url = validate_https_url(url)
        webbrowser.open(url)
        return f"{site.capitalize()} açıldı."

    def _search_web(self, args: dict) -> str:
        """
        İnternette/platformda arama yapar.

        YouTube: mümkünse gerçek videoyu DİREKT açar (arama sayfası değil).
        Bunun için YouTube Data API kullanılır — API anahtarı yoksa veya
        istek başarısız olursa otomatik olarak arama sayfasına düşer,
        hiçbir şey bozulmaz.

        Spotify: arama sonucunu açtıktan sonra klavyeden Enter göndererek
        ilk sonucu otomatik çalmayı dener.
        """
        import webbrowser
        import urllib.parse

        from services.security import validate_user_text
        query = validate_user_text(
            args.get("query", ""), name="Arama sorgusu", max_length=500
        )
        platform = args.get("platform", "google").lower()

        if not query:
            return "Arama sorgusu boş."

        encoded = urllib.parse.quote(query)

        if platform == "youtube":
            video_id = self._youtube_find_video_id(query)
            if video_id:
                webbrowser.open(f"https://www.youtube.com/watch?v={video_id}")
                return f"YouTube'da '{query}' videosu doğrudan açıldı."
            # API anahtarı yok veya istek başarısız oldu — güvenli geri düşüş
            webbrowser.open(f"https://www.youtube.com/results?search_query={encoded}")
            return f"YouTube'da '{query}' arandı."

        elif platform == "spotify":
            return self._spotify_search_and_play(query, encoded)

        elif platform == "maps":
            webbrowser.open(f"https://www.google.com/maps/search/{encoded}")
            return f"Haritada '{query}' arandı."

        else:
            webbrowser.open(f"https://www.google.com/search?q={encoded}")
            return f"Google'da '{query}' arandı."

    def _youtube_find_video_id(self, query: str) -> str | None:
        """
        YouTube Data API v3 ile arama yapar, ilk videonun ID'sini döndürür.
        Anahtar yoksa veya herhangi bir hata olursa None döner —
        çağıran taraf bunu görüp arama sayfasına geri düşer.
        """
        import requests
        import utils.config as config

        api_key = getattr(config, "YOUTUBE_API_KEY", "")
        if not api_key:
            return None

        try:
            r = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part":       "snippet",
                    "q":          query,
                    "type":       "video",
                    "maxResults": 1,
                    "key":        api_key,
                },
                timeout=8,
                allow_redirects=False,
            )
            r.raise_for_status()
            items = r.json().get("items", [])
            if items:
                video_id = str(items[0]["id"]["videoId"])
                if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
                    return video_id
        except Exception as e:
            from services.security import safe_error
            print(
                "[UYARI] YouTube API hatası, arama sayfasına geçiliyor: "
                f"{safe_error(e)}"
            )

        return None

    def _spotify_search_and_play(self, query: str, encoded: str) -> str:
        """
        Spotify'da şarkı arar ve otomatik çalmayı dener.

        Spotify'ın (ücretsiz hesaplarda) "ilk sonucu direkt çal" diye
        resmi bir yolu yok. Bunun yerine: arama ekranını açıp klavyeden
        Enter göndererek ilk sonucu seçtiriyoruz. Küçük bekleme süreleri
        (sleep) var çünkü Spotify uygulamasının açılıp arama sonucunu
        göstermesi zaman alıyor — çok hızlı Enter gönderirsek uygulama
        henüz hazır olmadığı için tuş boşa gider.
        """
        import os
        import time

        try:
            os.startfile(f"spotify:search:{encoded}")

            return (
                f"Spotify'da '{query}' araması açıldı. Güvenlik nedeniyle "
                "başka pencereye otomatik tuş gönderilmedi."
            )

        except Exception as e:
            return f"Spotify'da '{query}' arandı ama otomatik çalma başarısız oldu: {e}"

    # ─────────────────────────────────────────
    #  Takvim
    # ─────────────────────────────────────────

    def _get_calendar(self, args: dict) -> str:
        from services.calendar_reader import get_upcoming_events

        events = get_upcoming_events(days=365)
        if not events:
            return "Takvimde önümüzdeki 365 gün içinde etkinlik yok."

        filt = args.get("filter", "all")

        if filt == "today":
            events = [e for e in events if e["days_left"] == 0]
        elif filt == "tomorrow":
            events = [e for e in events if e["days_left"] == 1]
        elif filt == "week":
            events = [e for e in events if e["days_left"] <= 7]

        if not events:
            return "Bu dönem için etkinlik yok."

        # LLM'e HAM VERİ veriyoruz — cümleyi o kursun
        lines = []
        for e in events[:20]:
            tarih = e["start"].strftime("%d.%m.%Y")
            lines.append(f"- {e['title']} | {tarih} | {e['days_left']} gün sonra")

        return "Takvim etkinlikleri:\n" + "\n".join(lines)

    def _create_calendar_event(self, args: dict) -> str:
        from services.calendar_reader import create_calendar_event
        return create_calendar_event(
            args.get("title", "").strip(),
            args.get("start_at", "").strip(),
            args.get("end_at", "").strip(),
            args.get("description", "").strip(),
        )

    def _update_calendar_event(self, args: dict) -> str:
        from services.calendar_reader import update_calendar_event
        return update_calendar_event(
            query=args.get("query", "").strip(),
            title=args.get("title", "").strip(),
            start_at=args.get("start_at", "").strip(),
            end_at=args.get("end_at", "").strip(),
            description=args.get("description", "").strip(),
        )

    def _delete_calendar_event(self, args: dict) -> str:
        from services.calendar_reader import delete_calendar_event
        return delete_calendar_event(args.get("query", "").strip())

    # ─────────────────────────────────────────
    #  Gmail
    # ─────────────────────────────────────────

    def _get_emails(self, args: dict) -> str:
        from services.gmail_reader import (
            get_unread_emails, get_today_emails, search_emails
        )

        filt = args.get("filter", "unread")

        if filt == "today":
            return get_today_emails()
        elif filt == "search":
            return search_emails(args.get("query", ""))
        else:
            return get_unread_emails()

    def _read_email(self, args: dict) -> str:
        from services.gmail_reader import read_email
        query = (args.get("query") or "").strip()
        if not query:
            return "Okunacak mail için gönderen, konu veya anahtar kelime gerekli."
        return read_email(query)

    def _send_email(self, args: dict) -> str:
        from email.utils import parseaddr
        from services.gmail_reader import send_email

        recipient = (args.get("to") or "").strip()
        subject = (args.get("subject") or "").strip()
        body = (args.get("body") or "").strip()
        parsed = parseaddr(recipient)[1]
        if not parsed or "@" not in parsed:
            return "⚠️ Geçerli bir alıcı e-posta adresi gerekli."
        if not subject:
            return "⚠️ Mail konusu boş olamaz."
        if not body:
            return "⚠️ Mail içeriği boş olamaz."

        return send_email(
            parsed,
            subject,
            body,
        )

    # ─────────────────────────────────────────
    #  Sistem
    # ─────────────────────────────────────────

    def _get_system_status(self, args: dict) -> str:
        from services.system_info import get_system_status
        return get_system_status()

    def _analyze_screen(self, args: dict) -> str:
        from services.screen_vision import analyze_screen
        import utils.config as config

        image_data = args.pop("_image_data", "")
        args.pop("_image_width", None)
        args.pop("_image_height", None)
        if not getattr(config, "SCREEN_VISION_ENABLED", False):
            return (
                "Ekran farkındalığı kapatıldığı için görüntü analiz servisine "
                "gönderilmedi."
            )
        if not image_data:
            return (
                "Ekran görüntüsü alınmadı. Gizliliğin için işlemi sohbet "
                "kartındaki Onayla düğmesiyle yeniden başlatmalısın."
            )
        return analyze_screen(
            image_data,
            args.get("question", ""),
            api_key=config.GROQ_API_KEY or "",
            api_url=config.API_URL,
            model=config.VISION_MODEL,
        )

    def _get_shared_activity(self, args: dict) -> str:
        if self.shared_workspace is None:
            return "Paylaşılan başka bir sohbet çalışması yok."
        items = self.shared_workspace.recent(
            limit=int(args.get("limit", 10)),
            exclude_session=self.session_id,
        )
        if not items:
            return "Diğer sohbet pencerelerinde henüz paylaşılmış bir çalışma yok."
        lines = ["Diğer sohbetlerin son çalışmaları:"]
        for item in reversed(items):
            lines.append(
                f"- [{item.get('session_id')}] {item.get('title')}: "
                f"{item.get('content', '')[:700]}"
            )
        return "\n".join(lines)

    def _read_text_file(self, args: dict) -> str:
        from services.file_reader import read_text_file

        item = read_text_file(args.get("path", ""))
        suffix = "\n\n[Dosya uzun olduğu için içerik kısaltıldı.]" if item["truncated"] else ""
        result = (
            f"DOSYA: {item['name']}\nYOL: {item['path']}\n"
            f"BOYUT: {item['size']} bayt\n\n{item['content']}{suffix}"
        )
        if self.shared_workspace is not None:
            self.shared_workspace.publish(
                self.session_id,
                "file",
                f"Dosya incelendi: {item['name']}",
                f"{item['path']}\n{item['content'][:1200]}",
            )
        return result

    def _read_document(self, args: dict) -> str:
        from services.document_reader import read_document

        item = read_document(args.get("path", ""))
        suffix = (
            "\n\n[Belge güvenli çıktı sınırı nedeniyle kısaltıldı.]"
            if item["truncated"] else ""
        )
        result = (
            f"Belge: {item['name']}\nTür: {item['kind']}\n"
            f"Kapsam: {item['unit_count']} {item['unit_name']}\n\n"
            f"{item['content']}{suffix}"
        )
        if self.shared_workspace is not None:
            self.shared_workspace.publish(
                self.session_id,
                "document",
                f"Belge incelendi: {item['name']}",
                item["content"][:1600],
            )
        return result

    @staticmethod
    def _project_workspace():
        from services.project_workspace import ProjectWorkspace
        from utils.config import HEKO_PROJECT_ROOT
        return ProjectWorkspace(HEKO_PROJECT_ROOT)

    def _list_project_files(self, args: dict) -> str:
        item = self._project_workspace().list_files(
            args.get("query", ""), int(args.get("limit", 120))
        )
        lines = [f"PROJE: {item['root']}", "DOSYALAR:"]
        lines.extend(f"- {path}" for path in item["files"])
        if item["truncated"]:
            lines.append("[Liste sınır nedeniyle kısaltıldı.]")
        return "\n".join(lines)

    def _read_project_file(self, args: dict) -> str:
        item = self._project_workspace().read_file(args.get("path", ""))
        result = (
            f"PROJE DOSYASI: {item['path']}\nSHA256: {item['sha256']}\n"
            f"BOYUT: {item['size']} bayt\n\n{item['content']}"
        )
        if self.shared_workspace is not None:
            self.shared_workspace.publish(
                self.session_id, "project_file", f"Kod okundu: {item['path']}",
                result[:6000],
            )
        return result

    def _update_project_file(self, args: dict) -> str:
        item = self._project_workspace().apply_change(
            args.get("path", ""), args.get("content", ""),
            args.get("expected_sha256", ""),
        )
        if not item["changed"]:
            return f"Değişiklik yok: {item['path']} zaten aynı içerikte."
        result = f"Proje dosyası güncellendi: {item['path']}"
        if item["backup"]:
            result += f"\nÖnceki sürüm yedeklendi: {item['backup']}"
        if self.shared_workspace is not None:
            self.shared_workspace.publish(
                self.session_id, "code_change", f"Kod güncellendi: {item['path']}",
                item["diff"][:6000],
            )
        return result

    # ─────────────────────────────────────────
    #  Hafıza
    # ─────────────────────────────────────────

    def _remember_about_user(self, args: dict) -> str:
        from services.security import contains_sensitive_data
        category = args.get("category", "misc")
        value    = args.get("value", "").strip()

        if not value:
            return "Kaydedilecek bilgi boş."
        if len(value) > 5000 or contains_sensitive_data(value):
            return "Parola, API anahtarı veya çok uzun içerik kalıcı hafızaya kaydedilemez."

        # LLM'in kategori adları -> user_memory alan adları
        mapping = {
            "name":       "name",
            "profession": "profession",
            "preference": "preferences",
            "schedule":   "schedule",
            "goal":       "goals",
            "misc":       "misc",
        }
        self.user_memory.add_to(mapping.get(category, "misc"), value)
        return f"Kaydedildi: {value}"

    def _list_user_memory(self, args: dict) -> str:
        memories = self.user_memory.get_all()
        if not any(memories.values()):
            return "Kullanıcı hakkında kayıtlı kalıcı bilgi yok."
        labels = {
            "name": "Hitap / isim",
            "profession": "Meslek / rol",
            "preferences": "Tercihler",
            "schedule": "Günlük düzen",
            "goals": "Hedefler",
            "misc": "Diğer bilgiler",
        }
        lines = ["Senin hakkında hatırladıklarım:"]
        for category, label in labels.items():
            value = memories.get(category)
            if not value:
                continue
            values = value if isinstance(value, list) else [value]
            lines.append(f"\n{label}:")
            lines.extend(f"• {item}" for item in values)

        misc = " ".join(str(item).casefold() for item in memories.get("misc", []))
        if memories.get("name") and any(key in misc for key in ("adım", "ismim")):
            lines.append(
                "\nNot: İsimle ilgili birden fazla kayıt olabilir. "
                "Hafızayı Yönet ekranından doğru olanı bırakabilirsin."
            )
        return "\n".join(lines)

    def _forget_user_memory(self, args: dict) -> str:
        category = args.get("category", "")
        value = args.get("value", "")
        if self.user_memory.remove(category, value):
            return f"Unutuldu: {value}"
        return "Bu ifadeyle tam eşleşen bir hafıza kaydı bulunamadı."

    def _clear_history(self, args: dict) -> str:
        self.context.clear()
        return "Konuşma geçmişi silindi."
