from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QLineEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPainter, QColor, QPainterPath
import utils.config as config

class SettingsWindow(QWidget):

    saved = Signal()

    def __init__(self):
        super().__init__()
        self._drag_pos = None
        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        self.setFixedSize(380, 480)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        painter.setClipPath(path)
        painter.fillPath(path, QColor("#161b22"))
        painter.setPen(QColor("#30363d"))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())
        layout.addLayout(self._build_content())

    def _build_header(self):
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet("background-color: #0d1117; border-radius: 12px;")

        h = QHBoxLayout(header)
        h.setContentsMargins(16, 0, 16, 0)

        title = QLabel("⚙  Ayarlar")
        title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title.setStyleSheet("color: #e6edf3;")

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #8b949e; border: none; border-radius: 14px; }
            QPushButton:hover { background-color: #e74c3c; color: #ffffff; }
        """)
        close_btn.clicked.connect(self.hide)

        h.addWidget(title)
        h.addStretch()
        h.addWidget(close_btn)

        return header

    def _select_mode(self, mode_name: str):
        for name, btn in self._mode_buttons.items():
            btn.setChecked(name == mode_name)
        self._prompt_edit.setPlainText(config.MODES[mode_name])

    def _build_content(self):
        content = QVBoxLayout()
        content.setContentsMargins(20, 16, 20, 20)
        content.setSpacing(12)

        mode_label = QLabel("🎭  Mod Seç")
        mode_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        mode_label.setStyleSheet("color: #8b949e;")

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(6)
        self._mode_buttons = {}

        for mode_name in config.MODES.keys():
            btn = QPushButton(mode_name.capitalize())
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setFont(QFont("Segoe UI", 8))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0d1117;
                    color: #8b949e;
                    border: 1px solid #30363d;
                    border-radius: 8px;
                    padding: 0px 10px;
                }
                QPushButton:checked {
                    background-color: #1f4f8f;
                    color: #e6edf3;
                    border: 1px solid #4a9eff;
                }
                QPushButton:hover { border: 1px solid #4a9eff; }
            """)
            btn.clicked.connect(lambda checked, m=mode_name: self._select_mode(m))
            mode_layout.addWidget(btn)
            self._mode_buttons[mode_name] = btn

        self._mode_buttons["normal"].setChecked(True)

        prompt_label = QLabel("🤖  Asistan Kişiliği")
        prompt_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        prompt_label.setStyleSheet("color: #8b949e;")

        self._prompt_edit = QTextEdit()
        self._prompt_edit.setPlainText(config.SYSTEM_PROMPT)
        self._prompt_edit.setFont(QFont("Segoe UI", 9))
        self._prompt_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 8px;
            }
            QTextEdit:focus { border: 1px solid #4a9eff; }
        """)
        self._prompt_edit.setFixedHeight(200)

        name_label = QLabel("✏️  Asistan Adı (header'da görünür)")
        name_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        name_label.setStyleSheet("color: #8b949e;")

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Heko")
        self._name_edit.setFont(QFont("Segoe UI", 9))
        self._name_edit.setFixedHeight(36)
        self._name_edit.setStyleSheet("""
            QLineEdit {
                background-color: #0d1117;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 0px 10px;
            }
            QLineEdit:focus { border: 1px solid #4a9eff; }
        """)

        save_btn = QPushButton("💾  Kaydet")
        save_btn.setFixedHeight(38)
        save_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #1f4f8f;
                color: #e6edf3;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #4a9eff; }
        """)
        save_btn.clicked.connect(self._save)

        content.addWidget(mode_label)
        content.addLayout(mode_layout)
        content.addWidget(prompt_label)
        content.addWidget(self._prompt_edit)
        content.addWidget(name_label)
        content.addWidget(self._name_edit)
        content.addStretch()
        content.addWidget(save_btn)

        return content

    def _save(self):
        config.SYSTEM_PROMPT = self._prompt_edit.toPlainText().strip()
        print(f"KAYDEDILDI: {config.SYSTEM_PROMPT[:80]}")
        self.saved.emit()
        self.hide()
