from PySide6.QtCore import QThread, Signal, QObject
from services.security import safe_error


class ResponseWorker(QThread):
    """
    LLM ve Router işlemlerini ana thread'i yormadan çalıştırır.

    YENİ: status_update sinyali eklendi. Router bir araç çağırdığında
    (klasör açma, arama yapma vb.) bu sinyal tetiklenir, UI tarafında
    "Klasör açılıyor..." gibi anlık durumlar gösterilebilir.

    Not: QThread içinden sinyal emit etmek thread-safe'dir — Qt bunu
    otomatik olarak ana thread'e kuyruğa alır. Asıl tehlikeli olan
    thread içinden doğrudan widget'a dokunmaktır (setText, show vb.);
    biz bunu YAPMIYORUZ, sadece sinyal gönderiyoruz.
    """
    response_ready = Signal(str)
    error_occurred = Signal(str)
    status_update = Signal(str)

    def __init__(self, router, message: str):
        super().__init__()
        self._router = router
        self._message = message
        self._is_cancelled = False

    def cancel(self):
        """İşlemi iptal etmek için bayrak set eder."""
        self._is_cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self):
        try:
            if self._is_cancelled:
                return

            def on_status(text: str):
                if not self._is_cancelled:
                    self.status_update.emit(text)

            response = self._router.get_response(
                self._message,
                on_status=on_status,
                is_cancelled=lambda: self._is_cancelled,
            )

            if not self._is_cancelled:
                self.response_ready.emit(response)
        except Exception as e:
            if not self._is_cancelled:
                self.error_occurred.emit(str(e))


class MicWorker(QThread):
    """
    Ses dinleme işlemini QThread ile yönetir. 
    Threading.Thread yerine QThread kullanmak sinyal yönetimi için daha sağlıklıdır.
    """
    text_ready = Signal(str)
    finished_listening = Signal()

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            from services.speech_listener import listen_and_transcribe
            
            text = listen_and_transcribe(duration=5)
            self.text_ready.emit(text or "")
        except Exception as e:
            print(f"[MIKROFON HATASI] {safe_error(e)}")
            self.text_ready.emit("")
        finally:
            self.finished_listening.emit()

    def is_running(self):
        return self.isRunning()
