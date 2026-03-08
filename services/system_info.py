import psutil

def get_system_status():
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    battery = psutil.sensors_battery()
    
    status = "🖥️ **Sistem Durumu**\n"
    status += "━━━━━━━━━━━━━━━\n"
    status += f"🧠 CPU Kullanımı: %{cpu}\n"
    status += f"💾 RAM Kullanımı: %{ram}\n"
    
    if battery:
        plugged = "🔌 Takılı" if battery.power_plugged else "🔋 Deşarj"
        status += f"🪫 Pil: %{battery.percent} ({plugged})"
    
    return status