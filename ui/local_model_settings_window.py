"""Ollama yerel model tercihi ve bağlantı testi penceresi."""

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import utils.config as config
from services.local_model import probe_ollama, save_local_model_settings


class OllamaProbeWorker(QThread):
    finished_with_result = Signal(object)

    def __init__(self, model: str, base_url: str, parent=None):
        super().__init__(parent)
        self._model = model
        self._base_url = base_url

    def run(self):
        try:
            result = probe_ollama(self._model, self._base_url)
        except (TypeError, ValueError) as exc:
            result = {"ok": False, "message": str(exc), "models": []}
        self.finished_with_result.emit(result)


class LocalModelSettingsWindow(QWidget):
    saved = Signal()

    def __init__(self, llm_client=None):
        super().__init__()
        self._llm_client = llm_client
        self._probe_worker = None
        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        self.setWindowTitle("Yerel Model Ayarları")
        self.setFixedSize(430, 330)
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)

    def _setup_ui(self):
        self.setStyleSheet("background-color: #161b22; color: #e6edf3;")
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(10)

        title = QLabel("Yerel Model (Ollama)")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        description = QLabel(
            "Groq kullanılamadığında devreye girecek modeli seç. "
            "Bağlantı güvenlik nedeniyle yalnızca bu bilgisayara yapılır."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #8b949e;")

        model_label = QLabel("Model")
        model_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.setMaxVisibleItems(8)
        self._model_combo.lineEdit().setMaxLength(120)
        initial_model = getattr(config, "OLLAMA_MODEL", "")
        self._model_combo.addItem(initial_model or "qwen3:8b")
        self._model_combo.setCurrentText(initial_model)

        url_label = QLabel("Ollama adresi")
        url_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self._url_edit = QLineEdit(
            getattr(config, "OLLAMA_URL", "http://127.0.0.1:11434")
        )
        self._url_edit.setMaxLength(256)

        field_style = """
            QLineEdit, QComboBox {
                background: #0d1117; color: #e6edf3;
                border: 1px solid #30363d; border-radius: 7px;
                padding: 7px;
            }
            QLineEdit:focus, QComboBox:focus { border-color: #4a9eff; }
            QComboBox QAbstractItemView {
                background: #0d1117; color: #e6edf3;
                selection-background-color: #1f4f8f;
            }
        """
        self._model_combo.setStyleSheet(field_style)
        self._url_edit.setStyleSheet(field_style)

        self._status = QLabel("Henüz bağlantı testi yapılmadı.")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: #8b949e;")

        button_row = QHBoxLayout()
        self._test_btn = QPushButton("Bağlantıyı Test Et")
        save_btn = QPushButton("Kaydet ve Kullan")
        for button in (self._test_btn, save_btn):
            button.setFixedHeight(36)
            button.setStyleSheet("""
                QPushButton {
                    background: #1f4f8f; color: #ffffff;
                    border: none; border-radius: 8px; padding: 0 14px;
                }
                QPushButton:hover { background: #4a9eff; }
                QPushButton:disabled { background: #30363d; color: #8b949e; }
            """)
        self._test_btn.clicked.connect(self._test_connection)
        save_btn.clicked.connect(self._save)
        button_row.addWidget(self._test_btn)
        button_row.addWidget(save_btn)

        root.addWidget(title)
        root.addWidget(description)
        root.addWidget(model_label)
        root.addWidget(self._model_combo)
        root.addWidget(url_label)
        root.addWidget(self._url_edit)
        root.addWidget(self._status)
        root.addStretch()
        root.addLayout(button_row)

    def _values(self) -> tuple[str, str]:
        return self._model_combo.currentText().strip(), self._url_edit.text().strip()

    def _test_connection(self):
        if self._probe_worker and self._probe_worker.isRunning():
            return
        model, base_url = self._values()
        self._status.setText("Ollama kontrol ediliyor...")
        self._status.setStyleSheet("color: #d29922;")
        self._test_btn.setEnabled(False)
        self._probe_worker = OllamaProbeWorker(model, base_url, self)
        self._probe_worker.finished_with_result.connect(self._show_probe_result)
        self._probe_worker.finished.connect(lambda: self._test_btn.setEnabled(True))
        self._probe_worker.start()

    def _show_probe_result(self, result: dict):
        models = result.get("models", [])
        current = self._model_combo.currentText()
        for model in models:
            if self._model_combo.findText(model, Qt.MatchFixedString) < 0:
                self._model_combo.addItem(model)
        self._model_combo.setCurrentText(current)
        self._status.setText(result.get("message", "Test tamamlandı."))
        self._status.setStyleSheet(
            "color: #3fb950;" if result.get("ok") else "color: #f85149;"
        )

    def _save(self):
        model, base_url = self._values()
        try:
            data = save_local_model_settings(
                config.OLLAMA_SETTINGS_PATH, model, base_url
            )
            config.OLLAMA_MODEL = data["model"]
            config.OLLAMA_URL = data["base_url"]
            if self._llm_client is not None:
                self._llm_client.configure_local_model(
                    data["model"], data["base_url"]
                )
        except (OSError, TypeError, ValueError) as exc:
            self._status.setText(f"Ayar kaydedilemedi: {exc}")
            self._status.setStyleSheet("color: #f85149;")
            return
        if data["model"]:
            self._status.setText(
                f"‘{data['model']}’ kaydedildi ve kullanıma hazırlandı."
            )
        else:
            self._status.setText("Yerel model geri dönüşü kapatıldı.")
        self._status.setStyleSheet("color: #3fb950;")
        self.saved.emit()
