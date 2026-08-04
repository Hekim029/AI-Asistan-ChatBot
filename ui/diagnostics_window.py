from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from services.diagnostics import run_diagnostics
from services.error_logger import LOG_PATH


class DiagnosticsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Heko Sistem Kontrolü")
        self.setMinimumSize(460, 430)
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("background:#161b22; color:#e6edf3;")

        layout = QVBoxLayout(self)
        title = QLabel("Sistem Kontrolü")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self._results = QLabel()
        self._results.setWordWrap(True)
        self._results.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._results.setStyleSheet(
            "background:#0d1117; border:1px solid #30363d; "
            "border-radius:10px; padding:14px;"
        )
        self._log_path = QLabel(f"Hata günlüğü:\n{LOG_PATH}")
        self._log_path.setWordWrap(True)
        self._log_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._log_path.setStyleSheet("color:#8b949e;")
        refresh = QPushButton("Yeniden Kontrol Et")
        refresh.setFixedHeight(36)
        refresh.setStyleSheet(
            "QPushButton{background:#1f4f8f;border:0;border-radius:8px;color:white;}"
            "QPushButton:hover{background:#4a9eff;}"
        )
        refresh.clicked.connect(self.refresh)

        layout.addWidget(title)
        layout.addWidget(self._results, 1)
        layout.addWidget(self._log_path)
        layout.addWidget(refresh)
        self.refresh()

    def refresh(self):
        lines = []
        for check in run_diagnostics():
            icon = "✅" if check["ok"] else "⚠️"
            lines.append(f"{icon} {check['name']}\n    {check['detail']}")
        self._results.setText("\n\n".join(lines))
