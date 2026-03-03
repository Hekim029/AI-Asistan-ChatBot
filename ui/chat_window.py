from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QScrollArea, QLabel, QFrame, QApplication, QMenu
)
from PySide6.QtCore import Qt, QDateTime, QTimer
from PySide6.QtGui import QFont, QPainter, QColor, QPixmap
from core.router import Router
from core.worker import ResponseWorker

WORLD_MAP_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 580">
  <defs>
    <radialGradient id="planetGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#4a9eff" stop-opacity="0.25"/>
      <stop offset="100%" stop-color="#4a9eff" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="centerGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#4a9eff" stop-opacity="0.12"/>
      <stop offset="100%" stop-color="#4a9eff" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <ellipse cx="200" cy="290" rx="200" ry="200" fill="url(#centerGlow)"/>
  <circle cx="200" cy="230" r="70" fill="url(#planetGlow)"/>
  <circle cx="200" cy="230" r="70" fill="none" stroke="#4a9eff" stroke-width="1" opacity="0.35"/>
  <circle cx="200" cy="230" r="52" fill="none" stroke="#4a9eff" stroke-width="0.5" opacity="0.2"/>
  <g stroke="#4a9eff" stroke-width="0.7" opacity="0.25" fill="none">
    <path d="M145,215 Q200,200 255,215"/>
    <path d="M140,230 Q200,218 260,230"/>
    <path d="M143,245 Q200,238 257,245"/>
    <path d="M152,260 Q200,255 248,260"/>
  </g>
  <ellipse cx="200" cy="230" rx="105" ry="18" fill="none" stroke="#4a9eff" stroke-width="1" opacity="0.3"/>
  <ellipse cx="200" cy="230" rx="118" ry="22" fill="none" stroke="#4a9eff" stroke-width="0.5" opacity="0.15"/>
  <g fill="none" stroke="#4a9eff" opacity="0.15">
    <ellipse cx="200" cy="290" rx="170" ry="55" stroke-width="0.7"/>
    <ellipse cx="200" cy="290" rx="130" ry="42" stroke-width="0.5"/>
  </g>
  <circle cx="38" cy="278" r="3" fill="#4a9eff" opacity="0.5"/>
  <circle cx="362" cy="302" r="2.5" fill="#4a9eff" opacity="0.4"/>
  <circle cx="200" cy="248" r="2" fill="#4a9eff" opacity="0.45"/>
  <g fill="#ffffff">
    <circle cx="40" cy="50" r="1.8" opacity="0.9"/><circle cx="110" cy="30" r="1.4" opacity="0.7"/>
    <circle cx="180" cy="55" r="1.2" opacity="0.6"/><circle cx="260" cy="25" r="1.8" opacity="0.85"/>
    <circle cx="340" cy="48" r="1.5" opacity="0.75"/><circle cx="375" cy="20" r="1.2" opacity="0.6"/>
    <circle cx="70" cy="100" r="1.3" opacity="0.65"/><circle cx="150" cy="90" r="1.6" opacity="0.8"/>
    <circle cx="310" cy="85" r="1.4" opacity="0.7"/><circle cx="370" cy="110" r="1.2" opacity="0.6"/>
    <circle cx="25" cy="400" r="1.6" opacity="0.75"/><circle cx="90" cy="430" r="1.3" opacity="0.65"/>
    <circle cx="160" cy="410" r="1.5" opacity="0.7"/><circle cx="240" cy="445" r="1.8" opacity="0.85"/>
    <circle cx="320" cy="420" r="1.4" opacity="0.7"/><circle cx="380" cy="450" r="1.2" opacity="0.6"/>
    <circle cx="50" cy="510" r="1.5" opacity="0.75"/><circle cx="130" cy="530" r="1.3" opacity="0.65"/>
    <circle cx="210" cy="515" r="1.6" opacity="0.8"/><circle cx="290" cy="540" r="1.4" opacity="0.7"/>
    <circle cx="360" cy="520" r="1.2" opacity="0.6"/>
  </g>
  <g stroke="#ffffff" stroke-width="0.6" opacity="0.7">
    <line x1="68" y1="58" x2="68" y2="66"/><line x1="64" y1="62" x2="72" y2="62"/>
    <line x1="295" y1="42" x2="295" y2="50"/><line x1="291" y1="46" x2="299" y2="46"/>
    <line x1="355" y1="130" x2="355" y2="138"/><line x1="351" y1="134" x2="359" y2="134"/>
  </g>
  <g stroke="#4a9eff" stroke-width="0.4" opacity="0.18">
    <line x1="40" y1="50" x2="110" y2="30"/><line x1="110" y1="30" x2="180" y2="55"/>
    <line x1="180" y1="55" x2="260" y2="25"/><line x1="260" y1="25" x2="340" y2="48"/>
    <line x1="150" y1="90" x2="310" y2="85"/><line x1="25" y1="400" x2="90" y2="430"/>
    <line x1="240" y1="445" x2="320" y2="420"/><line x1="50" y1="510" x2="130" y2="530"/>
    <line x1="210" y1="515" x2="290" y2="540"/>
  </g>
  <g fill="#4a9eff" opacity="0.3" font-family="Courier New" font-size="7">
    <text x="6" y="12">SYS:ONLINE</text>
    <text x="6" y="22">LAT:38.6°N LON:39.2°E</text>
  </g>
</svg>"""

class ChatWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.router = Router()
        self._drag_pos = None
        self._typing_dots = 0
        self._typing_timer = QTimer()
        self._typing_timer.timeout.connect(self._animate_typing)
        self._typing_label = None
        self._typing_wrapper = None
        self._worker = None
        self._setup_window()
        self._setup_ui()
        QTimer.singleShot(500, self._show_welcome)

    def _setup_window(self):
        self.setWindowTitle("AI Assistant")
        self.setFixedSize(400, 580)
        self.setStyleSheet("background-color: #111318; border: 1px solid #2a3a5c;")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)

    def closeEvent(self, event):
        event.ignore()
        self.hide()
    
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
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_header())
        main_layout.addWidget(self._build_divider())
        main_layout.addWidget(self._build_scroll_area(), stretch=1)
        main_layout.addWidget(self._build_input_area())

    def _build_header(self):
        header_widget = QWidget()
        header_widget.setFixedHeight(52)
        header_widget.setStyleSheet("background-color: #161b22; border: none;")

        layout = QHBoxLayout(header_widget)
        layout.setContentsMargins(16, 0, 16, 0)

        icon = QLabel("◈")
        icon.setFont(QFont("Segoe UI", 13))
        icon.setStyleSheet("color: #4a9eff;")

        title = QLabel("Heko")
        title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title.setStyleSheet("color: #e6edf3; margin-left: 8px;")

        status = QLabel("● online")
        status.setFont(QFont("Segoe UI", 8))
        status.setStyleSheet("color: #3fb950; margin-left: 6px;")

        clear_btn = QPushButton("⟳")
        clear_btn.setFixedSize(28, 28)
        clear_btn.setFont(QFont("Segoe UI", 12))
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8b949e;
                border: none;
                border-radius: 14px;
            }
            QPushButton:hover { background-color: #21262d; color: #4a9eff; }
        """)
        clear_btn.setToolTip("Konuşmayı temizle")
        clear_btn.clicked.connect(self.clear_conversation)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setFont(QFont("Segoe UI", 10))
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8b949e;
                border: none;
                border-radius: 14px;
            }
            QPushButton:hover { background-color: #e74c3c; color: #ffffff; }
        """)
        close_btn.clicked.connect(self.hide)

        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(status)
        layout.addStretch()
        layout.addWidget(clear_btn)
        layout.addWidget(close_btn)

        return header_widget

    def clear_conversation(self):
        self.router.context.clear()
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        QTimer.singleShot(300, self._show_welcome)

    def _build_divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #21262d; border: none;")
        return line

    def _build_scroll_area(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background-color: transparent;")
        scroll.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical { width: 3px; background: transparent; }
            QScrollBar::handle:vertical { background: #30363d; border-radius: 2px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        self._messages_widget = MapBackgroundWidget(WORLD_MAP_SVG)
        self._messages_layout = QVBoxLayout(self._messages_widget)
        self._messages_layout.setContentsMargins(12, 12, 12, 12)
        self._messages_layout.setSpacing(8)
        self._messages_layout.addStretch()

        scroll.setWidget(self._messages_widget)
        self._scroll = scroll
        return scroll

    def _build_input_area(self):
        input_widget = QWidget()
        input_widget.setFixedHeight(62)
        input_widget.setStyleSheet("background-color: #161b22; border: none;")

        layout = QHBoxLayout(input_widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Mesaj yaz...")
        self.input_field.setFont(QFont("Segoe UI", 10))
        self.input_field.setFixedHeight(38)
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #21262d;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 18px;
                padding: 0px 14px;
            }
            QLineEdit:focus { border: 1px solid #4a9eff; }
        """)
        self.input_field.returnPressed.connect(self._send_message)

        send_btn = QPushButton("↑")
        send_btn.setFixedSize(38, 38)
        send_btn.setFont(QFont("Arial", 13))
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: #ffffff;
                border: none;
                border-radius: 19px;
            }
            QPushButton:hover { background-color: #6ab0ff; }
            QPushButton:pressed { background-color: #3080df; }
        """)
        send_btn.clicked.connect(self._send_message)

        layout.addWidget(self.input_field)
        layout.addWidget(send_btn)

        return input_widget

    def _show_welcome(self):
        self._add_message("Merhaba Ben Heko Sana Nasıl Yardımcı Olabilirim?", is_user=False)

    def _add_message(self, text: str, is_user: bool):
        timestamp = QDateTime.currentDateTime().toString("hh:mm")

        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setFont(QFont("Segoe UI", 9))
        bubble.setTextFormat(Qt.PlainText)
        bubble.setMaximumWidth(270)

        time_label = QLabel(timestamp)
        time_label.setFont(QFont("Segoe UI", 7))
        time_label.setStyleSheet("color: #8b949e; margin: 0px 4px;")
        time_label.setAlignment(Qt.AlignBottom)

        if is_user:
            bubble.setStyleSheet("""
                background-color: #1f4f8f;
                color: #e6edf3;
                border-radius: 14px;
                border-bottom-right-radius: 3px;
                padding: 8px 12px;
            """)
            outer.addStretch()
            outer.addWidget(time_label)
            outer.addWidget(bubble)
        else:
            bubble.setStyleSheet("""
                background-color: #1e242c;
                color: #e6edf3;
                border-radius: 14px;
                border-bottom-left-radius: 3px;
                padding: 8px 12px;
            """)
            outer.addWidget(bubble)
            outer.addWidget(time_label)
            outer.addStretch()

        wrapper = QWidget()
        wrapper.setStyleSheet("background-color: transparent;")
        wrapper.setLayout(outer)
        wrapper.setContextMenuPolicy(Qt.CustomContextMenu)
        wrapper.customContextMenuRequested.connect(lambda pos, t=text: self._show_message_menu(pos, t, wrapper))

        self._messages_layout.insertWidget(self._messages_layout.count() - 1, wrapper)
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def _show_message_menu(self, pos, text: str, widget: QWidget):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background-color: #161b22; color: #e6edf3; border: 1px solid #30363d; border-radius: 6px; padding: 4px; }
            QMenu::item { padding: 6px 20px; border-radius: 4px; }
            QMenu::item:selected { background-color: #21262d; }
        """)
        copy_action = menu.addAction("📋  Kopyala")
        copy_action.triggered.connect(lambda: QApplication.clipboard().setText(text))
        menu.exec(widget.mapToGlobal(pos))

    def _show_typing_indicator(self):
        self._typing_dots = 0
        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)

        self._typing_label = QLabel("●  ●  ●")
        self._typing_label.setFont(QFont("Segoe UI", 9))
        self._typing_label.setStyleSheet("""
            background-color: #1e242c;
            color: #8b949e;
            border-radius: 14px;
            border-bottom-left-radius: 3px;
            padding: 8px 14px;
        """)

        outer.addWidget(self._typing_label)
        outer.addStretch()

        self._typing_wrapper = QWidget()
        self._typing_wrapper.setStyleSheet("background-color: transparent;")
        self._typing_wrapper.setLayout(outer)

        self._messages_layout.insertWidget(self._messages_layout.count() - 1, self._typing_wrapper)
        self._typing_timer.start(400)

        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def _animate_typing(self):
        self._typing_dots = (self._typing_dots + 1) % 4
        dots = ["●  ○  ○", "●  ●  ○", "●  ●  ●", "○  ●  ●"][self._typing_dots]
        if self._typing_label:
            self._typing_label.setText(dots)

    def _hide_typing_indicator(self):
        self._typing_timer.stop()
        if self._typing_wrapper:
            self._typing_wrapper.deleteLater()
            self._typing_wrapper = None
            self._typing_label = None

    def _send_message(self):
        text = self.input_field.text().strip()
        if not text:
            return

        self._add_message(text, is_user=True)
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self._show_typing_indicator()

        self._worker = ResponseWorker(self.router, text)
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _on_response(self, response: str):
        self._hide_typing_indicator()
        self._add_message(response, is_user=False)
        self.input_field.setEnabled(True)
        self.input_field.setFocus()
        self._worker = None

    def _on_error(self, error: str):
        self._hide_typing_indicator()
        self._add_message(f"⚠️ {error}", is_user=False)
        self.input_field.setEnabled(True)
        self._worker = None

class MapBackgroundWidget(QWidget):

    def __init__(self, svg_text: str):
        super().__init__()
        self._pixmap = self._svg_to_pixmap(svg_text)

    def _svg_to_pixmap(self, svg_text: str) -> QPixmap:
        try:
            from PySide6.QtSvg import QSvgRenderer
            from PySide6.QtCore import QByteArray
            renderer = QSvgRenderer(QByteArray(svg_text.encode()))
            pixmap = QPixmap(1000, 500)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return pixmap
        except Exception:
            return QPixmap()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111318"))
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(self.width(), self.height(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)