import os
APPS = {
    "chrome": "chrome",
    "spotify": "spotify",
    "not defteri": "notepad",
    "hesap makinesi": "calc",
    "discord": "discord",
    "görev yöneticisi": "taskmgr",
    "kod": "code",
}

def launch_app(app_name):
    app_name = app_name.lower().strip()
    
    executable = APPS.get(app_name)
    
    if not executable:
        return None 

    try:
        os.startfile(executable)
        return f"🚀 **{app_name.capitalize()}** başlatılıyor..."
    except Exception:
        return None