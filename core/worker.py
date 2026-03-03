from PySide6.QtCore import QThread, Signal


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