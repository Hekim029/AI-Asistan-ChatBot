from PySide6.QtCore import QThread, Signal
from PySide6.QtCore import QObject, Signal
import threading

class ResponseWorker(QThread):

    response_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, router, message: str):
        super().__init__()
        self._router = router
        self._message = message

    def run(self):
        try:
            response = self._router.get_response(self._message)
            self.response_ready.emit(response)
        except Exception as e:
            self.error_occurred.emit(str(e))

class MicWorker(QObject):
    text_ready = Signal(str)

    def __init__(self):
        super().__init__()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            from services.speech_listener import listen_and_transcribe
            text = listen_and_transcribe(duration=5)
            self.text_ready.emit(text or "")
        except Exception:
            self.text_ready.emit("")

    def isRunning(self):
        return self._thread and self._thread.is_alive()