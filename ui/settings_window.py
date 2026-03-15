from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QFont, QPainter, QColor, QPainterPath
import utils.config as config
from utils.startup import enable_startup, disable_startup, is_startup_enabled

COLOR_PAIRS = [
    ("#4a9eff", "#1e242c", "Okyanus"),
    ("#9b59b6", "#2d1b4e", "Gece"),
    ("#3fb950", "#1a3d20", "Orman"),
    ("#f0883e", "#4a2a0e", "Gün Batimi"),
    ("#e74c3c", "#4a1010", "Kirmizi"),
    ("#ff6eb4", "#4a1a35", "Pembe"),
    ("#00d4ff", "#003a4a", "Buz"),
]

class SplitColorButton(QWidget):
    pair_selected = Signal(str, str)

    def __init__(self, user_color: str, ai_color: str, name: str):
        super().__init__()
        self.user_color = user_color
        self.ai_color = ai_color
        self.name = name
        self.is_selected = False
        self.setFixedSize(38, 38)
        self.setToolTip(name)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        left_path = QPainterPath()
        left_path.moveTo(19, 3)
        left_path.arcTo(3, 3, 32, 32, 90, 180)
        left_path.closeSubpath()
        painter.fillPath(left_path, QColor(self.user_color))
        right_path = QPainterPath()
        right_path.moveTo(19, 3)
        right_path.arcTo(3, 3, 32, 32, 90, -180)
        right_path.closeSubpath()
        painter.fillPath(right_path, QColor(self.ai_color))
        painter.setPen(QColor("#161b22"))
        painter.drawLine(19, 3, 19, 35)
        if self.is_selected:
            painter.setPen(QColor("#ffffff"))
        else:
            painter.setPen(QColor("#30363d"))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(2, 2, 34, 34))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pair_selected.emit(self.user_color, self.ai_color)

class SettingsWindow(QWidget):

    saved = Signal()

    def __init__(self):
        super().__init__()
        self._drag_pos = None
        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        self.setFixedSize(380, 560)
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
                    background-color: #0d1117; color: #8b949e;
                    border: 1px solid #30363d; border-radius: 8px; padding: 0px 10px;
                }
                QPushButton:checked { background-color: #1f4f8f; color: #e6edf3; border: 1px solid #4a9eff; }
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
                background-color: #0d1117; color: #e6edf3;
                border: 1px solid #30363d; border-radius: 8px; padding: 8px;
            }
            QTextEdit:focus { border: 1px solid #4a9eff; }
        """)
        self._prompt_edit.setFixedHeight(140)

        color_label = QLabel("🎨  Tema Seç  —  ◑  Sol: Sen  |  Sağ: AI")
        color_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        color_label.setStyleSheet("color: #8b949e;")

        color_layout = QHBoxLayout()
        color_layout.setSpacing(8)
        self._split_buttons = []
        for user_color, ai_color, name in COLOR_PAIRS:
            btn = SplitColorButton(user_color, ai_color, name)
            btn.pair_selected.connect(self._select_pair)
            color_layout.addWidget(btn)
            self._split_buttons.append(btn)
        color_layout.addStretch()

        startup_label = QLabel("🚀  Başlangıç")
        startup_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        startup_label.setStyleSheet("color: #8b949e;")

        startup_row = QHBoxLayout()
        startup_desc = QLabel("Windows açılınca otomatik başlat")
        startup_desc.setFont(QFont("Segoe UI", 8))
        startup_desc.setStyleSheet("color: #8b949e;")

        self._startup_btn = QPushButton()
        self._startup_btn.setFixedSize(80, 28)
        self._startup_btn.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self._startup_enabled = is_startup_enabled()
        self._update_startup_btn()
        self._startup_btn.clicked.connect(self._toggle_startup)

        startup_row.addWidget(startup_desc)
        startup_row.addStretch()
        startup_row.addWidget(self._startup_btn)

        save_btn = QPushButton("💾  Kaydet")
        save_btn.setFixedHeight(38)
        save_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        save_btn.setStyleSheet("""
            QPushButton { background-color: #1f4f8f; color: #e6edf3; border: none; border-radius: 8px; }
            QPushButton:hover { background-color: #4a9eff; }
        """)
        save_btn.clicked.connect(self._save)

        content.addWidget(mode_label)
        content.addLayout(mode_layout)
        content.addWidget(prompt_label)
        content.addWidget(self._prompt_edit)
        content.addWidget(color_label)
        content.addLayout(color_layout)
        content.addWidget(startup_label)
        content.addLayout(startup_row)
        content.addStretch()
        content.addWidget(save_btn)

        return content

    def _update_startup_btn(self):
        if self._startup_enabled:
            self._startup_btn.setText("✅ Açık")
            self._startup_btn.setStyleSheet("""
                QPushButton { background-color: #1a3d20; color: #3fb950; border: 1px solid #3fb950; border-radius: 8px; }
                QPushButton:hover { background-color: #2d5a35; }
            """)
        else:
            self._startup_btn.setText("⭕ Kapalı")
            self._startup_btn.setStyleSheet("""
                QPushButton { background-color: #0d1117; color: #8b949e; border: 1px solid #30363d; border-radius: 8px; }
                QPushButton:hover { border: 1px solid #4a9eff; }
            """)

    def _toggle_startup(self):
        if self._startup_enabled:
            disable_startup()
            self._startup_enabled = False
        else:
            enable_startup()
            self._startup_enabled = True
        self._update_startup_btn()

    def _select_pair(self, user_color: str, ai_color: str):
        config.ACCENT_COLOR = user_color
        config.AI_COLOR = ai_color
        for btn in self._split_buttons:
            btn.is_selected = (btn.user_color == user_color and btn.ai_color == ai_color)
            btn.update()

    def _save(self):
        config.SYSTEM_PROMPT = self._prompt_edit.toPlainText().strip()
        self.saved.emit()
        self.hide()