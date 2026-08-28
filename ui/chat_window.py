from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QTextEdit, QPushButton, QScrollArea, QLabel, QFrame, QApplication,
    QMenu, QToolTip,
)
from PySide6.QtCore import (
    Qt, QTimer, Signal, QRectF, QThread, QBuffer, QByteArray, QIODevice,
)
from PySide6.QtGui import (
    QFont, QPainter, QColor, QPixmap, QPainterPath, QRadialGradient,
    QLinearGradient, QPen
)
from core.router import Router
from core.worker import ResponseWorker
import utils.config as config
from ui.settings_window import SettingsWindow
from ui.history_window import HistoryWindow
from ui.project_diff_window import ProjectDiffWindow
from core.daily_motivation import get_today_motivation
from services.daily_briefing import DailyBriefingService
from services.speech_output import SpeechOutputManager
from datetime import datetime, timezone, timedelta
import math
import os
import base64


class DailyBriefingWorker(QThread):
    ready = Signal(str)

    def __init__(self, service):
        super().__init__()
        self._service = service

    def run(self):
        try:
            self.ready.emit(self._service.build())
        except Exception:
            self.ready.emit("")


def _chat_column_width(window_width: int) -> int:
    """Mesajlar ve yazma alanı için ortak, duyarlı kolon genişliği."""
    return max(360, min(900, window_width - 28))


def response_for_display(response: str, pending_info: dict | None = None) -> str:
    """İç protokol/karma ayrıntılarını sohbet kullanıcısından gizler."""
    text = str(response or "")
    if text.startswith("ONAY_GEREKLİ:"):
        tool_name = (pending_info or {}).get("tool_name", "")
        if tool_name == "update_project_file":
            return (
                "Kod değişikliği hazırlandı. Diff penceresinden ayrıntıları "
                "inceleyip uygulayabilir veya reddedebilirsin."
            )
        if tool_name in {"delete_file", "delete_project_file"}:
            return (
                "Dosyayı Çöp Kutusu'na taşıma işlemi hazırlandı. "
                "Aşağıdaki işlem kartından onaylayabilir veya iptal edebilirsin."
            )
        if tool_name == "analyze_screen":
            return (
                "Ekranını inceleme isteği hazır. Görüntü henüz alınmadı. "
                "Aşağıdaki karttan onay verirsen tek kare alınarak analiz edilecek."
            )
        return (
            "İşlem hazırlandı. Ayrıntıları aşağıdaki güvenlik kartından "
            "inceleyip onaylayabilir veya iptal edebilirsin."
        )
    if text.startswith("PROJE DOSYASI:"):
        lines = text.splitlines()
        path = lines[0].partition(":")[2].strip()
        size = next(
            (line.partition(":")[2].strip() for line in lines if line.startswith("BOYUT:")),
            "",
        )
        separator = next((index for index, line in enumerate(lines) if not line), None)
        content = "\n".join(lines[separator + 1:]) if separator is not None else ""
        header = f"Proje dosyası: {path}"
        if size:
            header += f"\nBoyut: {size}"
        return f"{header}\n\n{content}".rstrip()
    return text


class ChatInputBox(QTextEdit):
    """
    QLineEdit'in yerine geçen, çok satırlı mesaj kutusu.

    NEDEN GEREKLİ:
      QLineEdit yapısal olarak tek satırlıktır — uzun yazınca metni
      SAĞA doğru kaydırır, göstermez. Bu yüzden "yazdıklarımı göremiyorum"
      sorunu Ctrl+Enter eksikliğinden değil, widget'ın türünden kaynaklanıyordu.

    DAVRANIŞ:
      - Normal Enter  -> mesajı gönderir (send_requested sinyali)
      - Ctrl+Enter    -> gerçek bir alt satıra geçer
      - Uzun tek cümle yazılsa bile otomatik satır kaydırır ve kutu büyür
      - MAX_HEIGHT'a ulaşınca büyümeyi durdurup iç kaydırmaya geçer

    UYUMLULUK:
      text(), setText(), clear(), setCursorPosition() metodları eklendi
      ki geri kalan kod (ChatWindow içindeki diğer metodlar) hiç
      değişmeden, QLineEdit varmış gibi çalışmaya devam etsin.
    """

    send_requested = Signal()

    MIN_HEIGHT = 38
    MAX_HEIGHT = 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)          # sadece düz metin yapıştırılsın
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedHeight(self.MIN_HEIGHT)
        self.textChanged.connect(self._auto_resize)

    # ── Tuş davranışı ──────────────────────────
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ControlModifier:
                # Ctrl+Enter -> gerçek alt satır ekle
                self.textCursor().insertText("\n")
                return
            else:
                # Normal Enter -> gönder, satır EKLEME
                self.send_requested.emit()
                return
        super().keyPressEvent(event)

    # ── Otomatik büyüme ────────────────────────
    def _auto_resize(self):
        width = self.viewport().width()
        if width > 0:
            # Metin sarma (word-wrap) hesaplamasının doğru olması için
            # belge genişliğini gerçek viewport genişliğine eşitliyoruz.
            self.document().setTextWidth(width)

        doc_height = int(self.document().size().height())
        new_height = min(max(doc_height + 16, self.MIN_HEIGHT), self.MAX_HEIGHT)

        if new_height != self.height():
            self.setFixedHeight(new_height)

    # ── QLineEdit uyumluluk katmanı ─────────────
    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str):
        self.setPlainText(text)

    def clear(self):
        super().clear()
        self.setFixedHeight(self.MIN_HEIGHT)

    def setCursorPosition(self, pos: int):
        cursor = self.textCursor()
        cursor.setPosition(min(pos, len(self.toPlainText())))
        self.setTextCursor(cursor)


class EdgeResizeGrip(QWidget):
    """Çerçevesiz pencerenin bir kenarını işletim sistemi üzerinden sürükler."""

    def __init__(self, target: QWidget, edges, cursor):
        super().__init__(target)
        self._target = target
        self._edges = edges
        self.setCursor(cursor)
        self.setToolTip("Pencereyi yeniden boyutlandır")
        self.setStyleSheet("background: transparent;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            handle = self._target.windowHandle()
            if handle is not None:
                handle.startSystemResize(self._edges)
            event.accept()

    def paintEvent(self, event):
        if self._edges != (Qt.RightEdge | Qt.BottomEdge):
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(139, 148, 158, 115), 1.2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(8, 16, 16, 8)
        painter.drawLine(12, 16, 16, 12)


class ChatWindow(QMainWindow):

    new_window_requested = Signal()
    sessions_requested = Signal()

    def __init__(
        self,
        shared_state=None,
        session_id="main",
        display_name="Sohbet 1",
        speech_manager=None,
    ):
        super().__init__()
        self.session_id = session_id
        self.display_name = display_name
        self.router = Router(shared_state=shared_state, session_id=session_id)
        self._daily_briefing = DailyBriefingService(
            self.router.tasks, self.router.reminders
        )
        self._speech = speech_manager or SpeechOutputManager(
            auto_speak=getattr(config, "TTS_AUTO_SPEAK", False),
            voice_id=getattr(config, "TTS_VOICE_ID", ""),
            rate=getattr(config, "TTS_RATE", 0.0),
            volume=getattr(config, "TTS_VOLUME", 0.85),
        )
        self._settings = SettingsWindow(
            self.router.user_memory,
            self.router.tasks,
            self.router.reminders,
            self._daily_briefing,
            self.router.workspace,
            self.router.llm,
            self._speech,
        )
        self._drag_pos = None
        self._typing_dots = 0
        self._typing_timer = QTimer()
        self._typing_timer.timeout.connect(self._animate_typing)
        self._operation_timer = QTimer(self)
        self._operation_timer.setInterval(1000)
        self._operation_timer.timeout.connect(self._tick_operation)
        self._operation_elapsed = 0
        self._operation_status_text = ""
        self._approval_timer = QTimer(self)
        self._approval_timer.setInterval(1000)
        self._approval_timer.timeout.connect(self._update_approval_countdown)
        self._approval_widget = None
        self._approval_countdown = None
        self._approval_buttons = []
        self._diff_window = None
        self._settings.saved.connect(self._apply_accent)
        self._typing_label = None
        self._typing_wrapper = None
        self._worker = None
        self._worker_had_pending_action = False
        self._screen_capture_in_progress = False
        self._is_online = True
        self._message_count = 0
        self._is_expanded = False
        self._normal_geometry = None
        self._on_response_callback = None
        self._on_status_callback = None
        self._on_error_callback = None
        self._on_presence_callback = None
        self._on_activity_callback = None
        self._active_speech_button = None
        self._speech.state_changed.connect(self._on_speech_state_changed)
        self._mic_worker = None
        self._history = HistoryWindow(self.router.context)
        self._briefing_worker = None
        self._setup_window()
        self._setup_ui()
        self._update_message_widths()
        self._create_resize_grips()
        self._position_resize_grips()
        QTimer.singleShot(500, self._show_welcome)

    def _setup_window(self):
        self.setWindowTitle(f"Heko — {self.display_name}")
        # Üst araç çubuğundaki tüm kontroller 404 px genişlikte rahatça
        # görünür; daha dar ölçüler başlık ve durum rozetini sıkıştırıyor.
        self.setMinimumSize(404, 500)
        self.resize(404, 584)
        self.setStyleSheet("background-color: transparent;")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)

    def closeEvent(self, event):
        if self._mic_worker and self._mic_worker.isRunning():
            self._mic_worker.quit()
            self._mic_worker.wait(2000)
        event.ignore()
        self.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._is_expanded:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_resize_grips()
        self._update_message_widths()

    def _create_resize_grips(self):
        definitions = (
            (Qt.LeftEdge, Qt.SizeHorCursor),
            (Qt.RightEdge, Qt.SizeHorCursor),
            (Qt.TopEdge, Qt.SizeVerCursor),
            (Qt.BottomEdge, Qt.SizeVerCursor),
            (Qt.LeftEdge | Qt.TopEdge, Qt.SizeFDiagCursor),
            (Qt.RightEdge | Qt.TopEdge, Qt.SizeBDiagCursor),
            (Qt.LeftEdge | Qt.BottomEdge, Qt.SizeBDiagCursor),
            (Qt.RightEdge | Qt.BottomEdge, Qt.SizeFDiagCursor),
        )
        self._resize_grips = [
            EdgeResizeGrip(self, edges, cursor) for edges, cursor in definitions
        ]
        for grip in self._resize_grips:
            grip.show()

    def _position_resize_grips(self):
        if not hasattr(self, "_resize_grips"):
            return
        edge, corner = 7, 14
        width, height = self.width(), self.height()
        geometries = (
            (0, corner, edge, max(1, height - corner * 2)),
            (width - edge, corner, edge, max(1, height - corner * 2)),
            (corner, 0, max(1, width - corner * 2), edge),
            (corner, height - edge, max(1, width - corner * 2), edge),
            (0, 0, corner, corner),
            (width - corner, 0, corner, corner),
            (0, height - corner, corner, corner),
            (width - corner, height - corner, corner, corner),
        )
        for grip, geometry in zip(self._resize_grips, geometries):
            grip.setGeometry(*geometry)
            grip.raise_()

    def _update_message_widths(self):
        if not hasattr(self, "_messages_widget"):
            return
        window_width = self.width()
        conversation_width = _chat_column_width(window_width)
        side_margin = max(
            12,
            (window_width - conversation_width) // 2 + (
                18 if window_width >= 900 else 0
            ),
        )
        self._messages_layout.setContentsMargins(
            side_margin, 16 if window_width >= 900 else 12, side_margin, 12
        )
        self._messages_layout.setSpacing(12 if window_width >= 900 else 8)

        card_width = max(290, min(560, int(conversation_width * 0.58)))
        minimum_card_width = 230 if window_width >= 900 else 0
        message_font_size = 11 if window_width >= 900 else 10
        for card in self._messages_widget.findChildren(QWidget, "messageCard"):
            card.setMinimumWidth(minimum_card_width)
            card.setMaximumWidth(card_width)
            card.layout().setContentsMargins(
                18 if window_width >= 900 else 14,
                12 if window_width >= 900 else 9,
                18 if window_width >= 900 else 14,
                9 if window_width >= 900 else 7,
            )
            for label in card.findChildren(QLabel):
                if label.property("message_text"):
                    label.setMaximumWidth(card_width - 36)
                    label.setFont(
                        QFont(
                            "Segoe UI",
                            message_font_size,
                            QFont.Weight.Medium,
                        )
                    )

        if hasattr(self, "_composer_panel"):
            composer_width = _chat_column_width(window_width)
            self._composer_panel.setFixedWidth(composer_width)
            self._search_bar.setFixedWidth(composer_width)

    def _toggle_expanded(self):
        if self._is_expanded:
            self._is_expanded = False
            if self._normal_geometry is not None:
                self.setGeometry(self._normal_geometry)
            self._maximize_btn.setText("□")
            self._maximize_btn.setToolTip("Ekranı kapla")
            for grip in self._resize_grips:
                grip.show()
            self._position_resize_grips()
            return

        self._normal_geometry = self.geometry()
        screen = QApplication.screenAt(self.frameGeometry().center())
        screen = screen or QApplication.primaryScreen()
        self._is_expanded = True
        self.setGeometry(screen.availableGeometry())
        self._maximize_btn.setText("❐")
        self._maximize_btn.setToolTip("Önceki boyuta dön")
        for grip in self._resize_grips:
            grip.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        outer_rect = QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5)
        path = QPainterPath()
        path.addRoundedRect(outer_rect, 13, 13)
        painter.fillPath(path, QColor("#111318"))

        # Tek katmanlı nötr hat: sınırı belli eder, arayüzün önüne geçmez.
        painter.setPen(QPen(QColor("#303844"), 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    def _setup_ui(self):
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: transparent;")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        # İnce çerçevenin çocuk widget'lar tarafından örtülmemesi için küçük pay.
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_header())
        main_layout.addWidget(self._build_divider())
        main_layout.addWidget(self._build_scroll_area(), stretch=1)
        main_layout.addWidget(self._build_input_area())

    def _build_header(self):
        header_widget = QWidget()
        header_widget.setFixedHeight(52)
        header_widget.setStyleSheet("""
            background-color: #161b22;
            border: none;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
        """)

        layout = QHBoxLayout(header_widget)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(2)

        self._icon_label = QLabel("◈")
        self._icon_label.setFont(QFont("Segoe UI", 13))
        self._icon_label.setStyleSheet(f"color: {config.ACCENT_COLOR};")

        self._title_label = QLabel(f"Heko · {self.display_name}")
        self._title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self._title_label.setStyleSheet("color: #e6edf3; margin-left: 8px;")

        self._status_btn = QPushButton("● online")
        self._status_btn.setFont(QFont("Segoe UI", 8))
        self._status_btn.setCheckable(True)
        self._status_btn.setChecked(True)
        self._status_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #3fb950; border: 1px solid #3fb950; border-radius: 8px; padding: 2px 8px; }
            QPushButton:checked { background-color: transparent; color: #3fb950; border: 1px solid #3fb950; }
            QPushButton:!checked { color: #8b949e; border: 1px solid #8b949e; }
        """)
        self._status_btn.clicked.connect(self._toggle_online)

        new_btn = QPushButton("+")
        new_btn.setFixedSize(26, 26)
        new_btn.setFont(QFont("Segoe UI", 14, QFont.Bold))
        new_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #8b949e; border: none; border-radius: 14px; }
            QPushButton:hover { background-color: #21262d; color: #e6edf3; }
        """)
        new_btn.setToolTip("Yeni sohbet penceresi")
        new_btn.clicked.connect(self.new_window_requested.emit)

        sessions_btn = QPushButton("▦")
        sessions_btn.setFixedSize(26, 26)
        sessions_btn.setFont(QFont("Segoe UI Symbol", 11))
        sessions_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #8b949e; border: none; border-radius: 14px; }
            QPushButton:hover { background-color: #21262d; color: #e6edf3; }
        """)
        sessions_btn.setToolTip("Sohbet oturumlarını yönet")
        sessions_btn.clicked.connect(self.sessions_requested.emit)

        history_btn = QPushButton("📜")
        history_btn.setFixedSize(26, 26)
        history_btn.setFont(QFont("Segoe UI", 11))
        history_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #8b949e; border: none; border-radius: 14px; }
            QPushButton:hover { background-color: #21262d; color: #8b949e; }
        """)
        history_btn.setToolTip("Konuşma geçmişi")
        history_btn.clicked.connect(self._open_history)

        self._search_btn = QPushButton("🔍")
        self._search_btn.setFixedSize(26, 26)
        self._search_btn.setFont(QFont("Segoe UI", 11))
        self._search_btn.setCheckable(True)
        self._search_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: #8b949e; border: none; border-radius: 14px; }}
            QPushButton:hover {{ background-color: #21262d; color: {config.ACCENT_COLOR}; }}
            QPushButton:checked {{ color: {config.ACCENT_COLOR}; }}
        """)
        self._search_btn.setToolTip("Mesaj ara")
        self._search_btn.clicked.connect(self._toggle_search)

        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(26, 26)
        settings_btn.setFont(QFont("Segoe UI", 11))
        settings_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #8b949e; border: none; border-radius: 14px; }
            QPushButton:hover { background-color: #21262d; color: #8b949e; }
        """)
        settings_btn.setToolTip("Ayarlar")
        settings_btn.clicked.connect(self._open_settings)

        clear_btn = QPushButton("⟳")
        clear_btn.setFixedSize(26, 26)
        clear_btn.setFont(QFont("Segoe UI", 12))
        clear_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #8b949e; border: none; border-radius: 14px; }
            QPushButton:hover { background-color: #21262d; color: #8b949e; }
        """)
        clear_btn.setToolTip("Konuşmayı temizle")
        clear_btn.clicked.connect(self.clear_conversation)

        self._maximize_btn = QPushButton("□")
        self._maximize_btn.setFixedSize(26, 26)
        self._maximize_btn.setFont(QFont("Segoe UI Symbol", 11))
        self._maximize_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #8b949e; border: none; border-radius: 14px; }
            QPushButton:hover { background-color: #21262d; color: #e6edf3; }
        """)
        self._maximize_btn.setToolTip("Ekranı kapla")
        self._maximize_btn.clicked.connect(self._toggle_expanded)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setFont(QFont("Segoe UI", 10))
        close_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #8b949e; border: none; border-radius: 14px; }
            QPushButton:hover { background-color: #e74c3c; color: #ffffff; }
        """)
        close_btn.clicked.connect(self.hide)

        layout.addWidget(self._icon_label)
        layout.addWidget(self._title_label)
        layout.addWidget(self._status_btn)
        layout.addStretch()
        layout.addWidget(new_btn)
        layout.addWidget(sessions_btn)
        layout.addWidget(history_btn)
        layout.addWidget(self._search_btn)
        layout.addWidget(settings_btn)
        layout.addWidget(clear_btn)
        layout.addWidget(self._maximize_btn)
        layout.addWidget(close_btn)

        return header_widget

    def set_display_name(self, name: str):
        clean = " ".join((name or "").strip().split())
        if not clean:
            return
        self.display_name = clean
        self.setWindowTitle(f"Heko — {clean}")
        if hasattr(self, "_title_label"):
            self._title_label.setText(f"Heko · {clean}")

    def _open_settings(self):
        pos = self.frameGeometry().topLeft()
        self._settings.move(pos.x() + 10, pos.y() + 60)
        self._settings.show()

    def clear_conversation(self):
        self.router.context.clear()
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._message_count = 0
        self._messages_widget.set_message_count(0)
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

        self._messages_widget = MapBackgroundWidget()
        self._messages_layout = QVBoxLayout(self._messages_widget)
        self._messages_layout.setContentsMargins(12, 12, 12, 12)
        self._messages_layout.setSpacing(8)
        self._messages_layout.addStretch()

        scroll.setWidget(self._messages_widget)
        self._scroll = scroll
        return scroll

    def _build_input_area(self):
        input_widget = QWidget()
        input_widget.setStyleSheet("""
            background-color: #161b22;
            border: none;
            border-bottom-left-radius: 10px;
            border-bottom-right-radius: 10px;
        """)

        layout = QVBoxLayout(input_widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText("Mesajlarda ara...")
        self._search_bar.setFont(QFont("Segoe UI", 9))
        self._search_bar.setFixedHeight(30)
        self._search_bar.setVisible(False)
        self._search_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0d1117;
                color: #e6edf3;
                border: 1px solid {config.ACCENT_COLOR};
                border-radius: 14px;
                padding: 0px 12px;
            }}
        """)
        self._search_bar.textChanged.connect(self._search_messages)

        self._composer_panel = QWidget()
        self._composer_panel.setStyleSheet("background: transparent;")
        send_layout = QHBoxLayout(self._composer_panel)
        send_layout.setSpacing(8)
        send_layout.setContentsMargins(0, 0, 0, 0)

        # Çok satırlı, otomatik büyüyen mesaj kutusu.
        # Normal Enter gönderir, Ctrl+Enter alt satıra geçer.
        self.input_field = ChatInputBox()
        self.input_field.setPlaceholderText("Mesaj yaz...")
        self.input_field.setFont(QFont("Segoe UI", 10))
        self.input_field.setStyleSheet(f"""
            QTextEdit {{
                background-color: #21262d;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 18px;
                padding: 8px 14px;
            }}
            QTextEdit:focus {{ border: 1px solid {config.ACCENT_COLOR}; }}
        """)
        self.input_field.send_requested.connect(self._send_message)

        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setFixedSize(38, 38)
        self._mic_btn.setFont(QFont("Segoe UI", 13))
        self._mic_btn.setStyleSheet("""
            QPushButton { background-color: #21262d; color: #8b949e; border: none; border-radius: 19px; }
            QPushButton:hover { background-color: #30363d; }
            QPushButton:pressed { background-color: #e74c3c; color: #ffffff; }
        """)
        self._mic_btn.pressed.connect(self._start_mic)
        self._mic_btn.released.connect(self._stop_mic)

        self._send_btn = QPushButton("↑")
        self._send_btn.setFixedSize(38, 38)
        self._send_btn.setFont(QFont("Arial", 13))
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {config.ACCENT_COLOR};
                color: #ffffff;
                border: none;
                border-radius: 19px;
            }}
            QPushButton:hover {{ background-color: {config.ACCENT_COLOR}cc; }}
            QPushButton:pressed {{ background-color: {config.ACCENT_COLOR}99; }}
        """)
        self._send_btn.clicked.connect(self._handle_send_button)

        self._operation_label = QLabel()
        self._operation_label.setVisible(False)
        self._operation_label.setWordWrap(True)
        self._operation_label.setStyleSheet(
            "color:#9da7b3;background:#111820;border:1px solid #293444;"
            "border-radius:8px;padding:6px 10px;"
        )

        # Kutu büyüdükçe mikrofon/gönder butonları alta sabitlensin,
        # üste doğru garip biçimde uzamasınlar.
        send_layout.addWidget(self.input_field)
        send_layout.addWidget(self._mic_btn, alignment=Qt.AlignBottom)
        send_layout.addWidget(self._send_btn, alignment=Qt.AlignBottom)

        layout.addWidget(self._search_bar)
        layout.setAlignment(self._search_bar, Qt.AlignHCenter)
        layout.addWidget(self._operation_label)
        layout.addWidget(self._composer_panel, 0, Qt.AlignHCenter)

        return input_widget

    def _show_welcome(self):
        self._add_message("Merhaba Ben Heko Sana Nasıl Yardımcı Olabilirim?", is_user=False)
        motivation = get_today_motivation()
        if motivation:
            QTimer.singleShot(1000, lambda: self._add_message(motivation, is_user=False))
        QTimer.singleShot(1400, self._start_daily_briefing)

    def _start_daily_briefing(self):
        if not self._daily_briefing.should_show():
            return
        if self._briefing_worker and self._briefing_worker.isRunning():
            return
        self._briefing_worker = DailyBriefingWorker(self._daily_briefing)
        self._briefing_worker.ready.connect(self._show_daily_briefing)
        self._briefing_worker.start()

    def _show_daily_briefing(self, message: str):
        if not message:
            return
        self._daily_briefing.mark_shown()
        self.router.context.add_message("assistant", message)
        self._add_message(message, is_user=False)

    def _toggle_online(self):
        self._is_online = self._status_btn.isChecked()
        if self._is_online:
            self._status_btn.setText("● online")
            motivation = get_today_motivation()
            msg = "Uyandım! Sana yardımcı olmaya hazırım. 👋"
            if motivation:
                msg += f"\n\n{motivation}"
            self._add_message(msg, is_user=False)
            if self._on_presence_callback:
                self._on_presence_callback("idle")
        else:
            self._status_btn.setText("● offline")
            self._add_message("Uyuyorum... Uyandırmak için online yap. 💤", is_user=False)
            if self._on_presence_callback:
                self._on_presence_callback("sleeping")

    def _toggle_search(self):
        is_active = self._search_btn.isChecked()
        self._search_bar.setVisible(is_active)
        if is_active:
            self._search_bar.setFocus()
        else:
            self._search_bar.clear()
            self._search_messages("")

    def _search_messages(self, query: str):
        query = query.lower().strip()
        for i in range(self._messages_layout.count() - 1):
            item = self._messages_layout.itemAt(i)
            if not item or not item.widget():
                continue
            wrapper = item.widget()
            bubble = None
            for child in wrapper.findChildren(QLabel):
                if child.property("message_text"):
                    bubble = child
                    break
            if not bubble:
                continue
            if not query:
                wrapper.setVisible(True)
            else:
                wrapper.setVisible(query in bubble.text().lower())

    def _add_message(self, text: str, is_user: bool):
        timestamp = datetime.now(
            MapBackgroundWidget.TURKEY_TIMEZONE
        ).strftime("%H:%M")

        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        bubble.setMaximumWidth(260)
        bubble.setProperty("message_text", True)
        bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bubble.mouseReleaseEvent = lambda e: self._on_selection_changed(bubble)
        bubble.setTextFormat(Qt.MarkdownText)
        bubble.setStyleSheet("background: transparent; color: #f0f3f6; border: none;")

        time_label = QLabel(timestamp)
        time_label.setFont(QFont("Segoe UI", 7, QFont.Weight.Normal))
        time_label.setStyleSheet(
            "color: rgba(230, 237, 243, 145); background: transparent; border: none;"
        )

        card = QWidget()
        card.setObjectName("messageCard")
        card.setProperty("message_role", "user" if is_user else "assistant")
        card.setMaximumWidth(290)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 9, 14, 7)
        card_layout.setSpacing(2)
        card_layout.addWidget(bubble)

        if is_user:
            card.setStyleSheet(f"""
                QWidget#messageCard {{
                    background-color: {config.ACCENT_COLOR};
                    border-radius: 14px;
                    border-bottom-right-radius: 3px;
                }}
            """)
            card_layout.addWidget(time_label, 0, Qt.AlignRight)
            outer.addStretch()
            outer.addWidget(card)
        else:
            card.setStyleSheet(f"""
                QWidget#messageCard {{
                    background-color: {config.AI_COLOR};
                    border: 1px solid rgba(255, 255, 255, 18);
                    border-radius: 14px;
                    border-bottom-left-radius: 3px;
                }}
            """)
            footer = QHBoxLayout()
            footer.setContentsMargins(0, 0, 0, 0)
            footer.setSpacing(5)
            speech_btn = QPushButton("🔊")
            speech_btn.setProperty("speech_button", True)
            speech_btn.setFixedSize(24, 20)
            speech_btn.setToolTip("Bu yanıtı seslendir")
            speech_btn.setStyleSheet("""
                QPushButton {
                    background:transparent;color:#8b949e;border:none;
                    border-radius:6px;font-size:11px;
                }
                QPushButton:hover { background:#30363d;color:#ffffff; }
            """)
            speech_btn.clicked.connect(
                lambda _checked=False, value=text, button=speech_btn:
                self._speak_message(value, button)
            )
            footer.addWidget(time_label)
            footer.addStretch()
            footer.addWidget(speech_btn)
            card_layout.addLayout(footer)
            outer.addWidget(card)
            outer.addStretch()

        wrapper = QWidget()
        wrapper.setStyleSheet("background-color: transparent;")
        wrapper.setLayout(outer)
        wrapper.setContextMenuPolicy(Qt.CustomContextMenu)
        wrapper.customContextMenuRequested.connect(lambda pos, t=text: self._show_message_menu(pos, t, wrapper))

        self._messages_layout.insertWidget(self._messages_layout.count() - 1, wrapper)
        self._message_count += 1
        self._messages_widget.set_message_count(self._message_count)
        self._update_message_widths()
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))
        if not is_user and self._speech.auto_speak:
            QTimer.singleShot(0, lambda value=text: self._speech.speak(value))

    def _speak_message(self, text: str, button: QPushButton):
        if self._active_speech_button and self._active_speech_button is not button:
            self._active_speech_button.setText("🔊")
            self._active_speech_button.setToolTip("Bu yanıtı seslendir")
        self._active_speech_button = button
        ok, message = self._speech.toggle(text)
        if not ok:
            button.setText("🔊")
            self._active_speech_button = None
            QToolTip.showText(button.mapToGlobal(button.rect().bottomLeft()), message, button)
            return
        if self._speech.is_speaking:
            button.setText("■")
            button.setToolTip("Seslendirmeyi durdur")

    def _on_speech_state_changed(self, state: str):
        if state in {"ready", "error"} and self._active_speech_button:
            self._active_speech_button.setText("🔊")
            self._active_speech_button.setToolTip("Bu yanıtı seslendir")
            self._active_speech_button = None

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
        if self._screen_capture_in_progress:
            return
        if self._worker and self._worker.isRunning():
            return
        text = self.input_field.text().strip()
        if not text:
            return

        if not self._is_online:
            self._add_message("💤 Şu an uyuyorum, uyandırmak için online yap.", is_user=False)
            self.input_field.clear()
            return

        pending_info = self.router.executor.pending_action_info()
        normalized = " ".join(text.casefold().split())
        if (
            pending_info
            and pending_info.get("tool_name") == "analyze_screen"
            and normalized in {
                "onaylıyorum", "onayla", "evet", "evet yap",
                "tamam yap", "işlemi yap",
            }
        ):
            self._begin_screen_capture(text)
            return

        self._add_message(text, is_user=True)
        self.input_field.clear()
        self._start_response_worker(text)

    def _start_response_worker(self, text: str):
        self.input_field.setEnabled(False)
        self._show_typing_indicator()

        self._worker = ResponseWorker(self.router, text)
        worker = self._worker
        self._worker_had_pending_action = self.router.executor.has_pending_action()
        worker.response_ready.connect(self._on_response)
        worker.error_occurred.connect(self._on_error)
        worker.status_update.connect(self._on_status)
        worker.finished.connect(lambda w=worker: self._on_worker_finished(w))
        self._begin_operation("İstek hazırlanıyor...")
        worker.start()

    def _begin_screen_capture(self, approval_text: str):
        """Onaydan sonra sohbeti gizleyip tek kareyi UI iş parçacığında alır."""
        if not getattr(config, "SCREEN_VISION_ENABLED", False):
            self.router.executor.execute("cancel_pending_action", {})
            self._add_message(
                "Ekran farkındalığı Ayarlar > Sistem bölümünden kapatılmış; "
                "bu nedenle görüntü alınmadı.",
                is_user=False,
            )
            return
        self._screen_capture_in_progress = True
        self._approval_timer.stop()
        for button in self._approval_buttons:
            button.setEnabled(False)
        self._add_message(approval_text, is_user=True)
        self.input_field.clear()
        self.input_field.setEnabled(False)
        self._begin_operation("Ekran görüntüsü hazırlanıyor...")
        screen = QApplication.screenAt(self.frameGeometry().center())
        screen = screen or QApplication.primaryScreen()
        self.hide()
        QTimer.singleShot(
            180, lambda: self._capture_screen_and_continue(screen, approval_text)
        )

    def _capture_screen_and_continue(self, screen, approval_text: str):
        try:
            if screen is None:
                raise RuntimeError("Kullanılabilir ekran bulunamadı.")
            pixmap = screen.grabWindow(0)
            if pixmap.isNull():
                raise RuntimeError("Ekran görüntüsü alınamadı.")
            image = pixmap.toImage()
            if image.width() > 1600 or image.height() > 1200:
                image = image.scaled(
                    1600, 1200, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            encoded = QByteArray()
            buffer = QBuffer(encoded)
            if not buffer.open(QIODevice.WriteOnly):
                raise RuntimeError("Görüntü belleğe hazırlanamadı.")
            if not image.save(buffer, "JPEG", 72):
                raise RuntimeError("Ekran görüntüsü sıkıştırılamadı.")
            buffer.close()
            image_data = "data:image/jpeg;base64," + base64.b64encode(
                bytes(encoded)
            ).decode("ascii")
            self.router.executor.attach_pending_screen_capture(
                image_data, image.width(), image.height()
            )
        except Exception as exc:
            from services.security import safe_error
            self.router.executor.execute("cancel_pending_action", {})
            self.show()
            self.raise_()
            self.activateWindow()
            self._screen_capture_in_progress = False
            self.input_field.setEnabled(True)
            self._finish_operation()
            self._add_message(
                f"Ekran görüntüsü alınamadı: {safe_error(exc)}", is_user=False
            )
            return

        self.show()
        self.raise_()
        self.activateWindow()
        self._screen_capture_in_progress = False
        self._start_response_worker(approval_text)

    def _handle_send_button(self):
        if self._screen_capture_in_progress:
            return
        if self._worker and self._worker.isRunning():
            self._cancel_current_response()
            return
        self._send_message()

    def _cancel_current_response(self):
        if not self._worker or not self._worker.isRunning():
            return
        if self._worker.is_cancelled:
            return
        self._worker.cancel()
        self._operation_status_text = "İptal ediliyor; mevcut ağ adımı bitince duracak..."
        self._refresh_operation_label()
        self._send_btn.setEnabled(False)

    def _on_status(self, text: str):
        """
        Worker'dan gelen anlık durum bilgisini (Düşünüyor..., Klasör
        açılıyor... vb.) dışarıya iletir. Pet'in yanındaki durum
        balonu bunu kullanır.
        """
        self._operation_status_text = text or "İşlem sürüyor..."
        self._refresh_operation_label()
        if self._on_status_callback:
            self._on_status_callback(text)

    def _on_response(self, response: str):
        self._hide_typing_indicator()
        pending_info = self.router.executor.pending_action_info()
        self._add_message(
            response_for_display(response, pending_info),
            is_user=False,
        )
        if pending_info:
            self._show_approval_card()
        else:
            self._remove_approval_card()
        self.input_field.setEnabled(True)
        self.input_field.setFocus()
        self._finish_operation()
        if self._on_response_callback:
            self._on_response_callback(response)

    def _on_worker_finished(self, worker):
        if worker is not self._worker:
            return
        if worker.is_cancelled:
            self._hide_typing_indicator()
            if (
                not self._worker_had_pending_action
                and self.router.executor.has_pending_action()
            ):
                self.router.executor.execute("cancel_pending_action", {})
            message = (
                "İşlem durduruldu. Başlamış bir dış işlem varsa geri alınmış "
                "sayılmaz; ancak yeni model ve araç adımları çalıştırılmadı."
            )
            self.router.context.add_message("assistant", message)
            self._add_message(message, is_user=False)
            self.input_field.setEnabled(True)
            self.input_field.setFocus()
            self._finish_operation()
        self._worker = None

    def _begin_operation(self, status: str):
        was_active = self._operation_timer.isActive()
        self._operation_elapsed = 0
        self._operation_status_text = status
        self._operation_label.setVisible(True)
        self._operation_timer.start()
        self._style_send_button(running=True)
        self._refresh_operation_label()
        if not was_active and self._on_activity_callback:
            self._on_activity_callback(True)

    def _finish_operation(self):
        was_active = self._operation_timer.isActive()
        self._operation_timer.stop()
        self._operation_label.setVisible(False)
        self._send_btn.setEnabled(True)
        self._style_send_button(running=False)
        if was_active and self._on_activity_callback:
            self._on_activity_callback(False)

    def _tick_operation(self):
        self._operation_elapsed += 1
        self._refresh_operation_label()

    def _refresh_operation_label(self):
        minutes, seconds = divmod(self._operation_elapsed, 60)
        self._operation_label.setText(
            f"{self._operation_status_text}   •   {minutes:02d}:{seconds:02d}"
        )

    def _style_send_button(self, running: bool):
        if running:
            self._send_btn.setText("■")
            self._send_btn.setToolTip("İşlemi durdur")
            self._send_btn.setStyleSheet(
                "QPushButton{background:#b4232d;color:white;border:none;"
                "border-radius:19px;} QPushButton:hover{background:#d03540;}"
                "QPushButton:disabled{background:#5d252a;color:#c7a0a3;}"
            )
            return
        color = config.ACCENT_COLOR
        self._send_btn.setText("↑")
        self._send_btn.setToolTip("Mesajı gönder")
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color}; color: #ffffff;
                border: none; border-radius: 19px;
            }}
            QPushButton:hover {{ background-color: {color}cc; }}
            QPushButton:pressed {{ background-color: {color}99; }}
        """)

    def _show_approval_card(self):
        self._remove_approval_card()
        info = self.router.executor.pending_action_info()
        if not info:
            return

        card = QWidget()
        card.setStyleSheet(
            "QWidget#approvalCard{background:#171e29;"
            "border:1px solid #4a6078;border-radius:12px;}"
        )
        card.setObjectName("approvalCard")
        card.setMaximumWidth(420)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        title = QLabel(
            "Ekran paylaşımı onayı"
            if info.get("tool_name") == "analyze_screen"
            else "İşlem onayı"
        )
        title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title.setStyleSheet("color:#e6edf3;border:none;")
        summary = QLabel(info["summary"])
        summary.setWordWrap(True)
        summary.setStyleSheet("color:#c9d1d9;border:none;")
        self._approval_countdown = QLabel()
        self._approval_countdown.setStyleSheet("color:#8b949e;border:none;")

        buttons = QHBoxLayout()
        cancel_btn = QPushButton("İptal")
        approve_btn = QPushButton("Onayla")
        for button in (cancel_btn, approve_btn):
            button.setFixedHeight(32)
        cancel_btn.setStyleSheet(
            "QPushButton{background:#21262d;color:#c9d1d9;border:1px solid "
            "#30363d;border-radius:8px;} QPushButton:hover{background:#30363d;}"
        )
        approve_btn.setStyleSheet(
            f"QPushButton{{background:{config.ACCENT_COLOR};color:white;"
            "border:none;border-radius:8px;font-weight:600;}"
            f"QPushButton:hover{{background:{config.ACCENT_COLOR}cc;}}"
        )
        cancel_btn.clicked.connect(
            lambda: self._submit_approval("iptal")
        )
        approve_btn.clicked.connect(
            lambda: self._submit_approval("onaylıyorum")
        )
        buttons.addWidget(cancel_btn)
        buttons.addWidget(approve_btn)

        layout.addWidget(title)
        layout.addWidget(summary)
        layout.addWidget(self._approval_countdown)
        project_change = info.get("project_change")
        if project_change:
            inspect_btn = QPushButton("Değişikliği ayrıntılı incele")
            inspect_btn.setFixedHeight(32)
            inspect_btn.setStyleSheet(
                "QPushButton{background:#1c2735;color:#79c0ff;border:1px solid "
                "#365675;border-radius:8px;} QPushButton:hover{background:#24364a;}"
            )
            inspect_btn.clicked.connect(
                lambda _checked=False, detail=project_change: self._open_project_diff(detail)
            )
            layout.addWidget(inspect_btn)
        layout.addLayout(buttons)

        wrapper = QWidget()
        wrapper.setStyleSheet("background:transparent;")
        outer = QHBoxLayout(wrapper)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        outer.addStretch()
        self._messages_layout.insertWidget(
            self._messages_layout.count() - 1, wrapper
        )
        self._approval_widget = wrapper
        self._approval_buttons = [cancel_btn, approve_btn]
        self._update_approval_countdown()
        self._approval_timer.start()
        if project_change:
            QTimer.singleShot(0, lambda: self._open_project_diff(project_change))
        QTimer.singleShot(
            0,
            lambda: self._scroll.verticalScrollBar().setValue(
                self._scroll.verticalScrollBar().maximum()
            ),
        )

    def _submit_approval(self, message: str):
        for button in self._approval_buttons:
            button.setEnabled(False)
        self._approval_timer.stop()
        self.input_field.setText(message)
        self._send_message()

    def _open_project_diff(self, preview: dict):
        if self._diff_window and self._diff_window.isVisible():
            self._diff_window.raise_()
            self._diff_window.activateWindow()
            return
        window = ProjectDiffWindow(
            preview,
            self.router.executor.pending_action_info,
            self,
        )
        window.approve_requested.connect(
            lambda: self._submit_approval("onaylıyorum")
        )
        window.cancel_requested.connect(
            lambda: self._submit_approval("iptal")
        )
        window.destroyed.connect(lambda: setattr(self, "_diff_window", None))
        self._diff_window = window
        window.show()
        window.raise_()
        window.activateWindow()

    def _update_approval_countdown(self):
        info = self.router.executor.pending_action_info()
        if not info:
            self._approval_timer.stop()
            return
        remaining = info["seconds_remaining"]
        if remaining <= 0:
            self._approval_timer.stop()
            result = self.router.executor.execute(
                "cancel_pending_action", {}
            )
            for button in self._approval_buttons:
                button.setEnabled(False)
            if self._approval_countdown:
                self._approval_countdown.setText(
                    "Onay süresi doldu — işlem yapılmadı."
                )
            self._add_message(result, is_user=False)
            return
        minutes, seconds = divmod(remaining, 60)
        if self._approval_countdown:
            self._approval_countdown.setText(
                f"Kalan süre: {minutes:02d}:{seconds:02d}"
            )

    def _remove_approval_card(self):
        self._approval_timer.stop()
        if self._diff_window:
            self._diff_window.close()
            self._diff_window = None
        if self._approval_widget:
            self._approval_widget.deleteLater()
        self._approval_widget = None
        self._approval_countdown = None
        self._approval_buttons = []

    def _on_error(self, error: str):
        self._hide_typing_indicator()
        self._add_message(f"⚠️ {error}", is_user=False)
        self.input_field.setEnabled(True)
        self._finish_operation()
        if self._on_error_callback:
            self._on_error_callback(error)

    def _on_selection_changed(self, label: QLabel):
        selected = label.selectedText()
        if selected.strip():
            QTimer.singleShot(100, lambda: self._show_selection_popup(selected, label))

    def _show_selection_popup(self, selected_text: str, label: QLabel):
        if not selected_text.strip():
            return

        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: #1e242c;
                color: #e6edf3;
                border: 1px solid {config.ACCENT_COLOR};
                border-radius: 12px;
                padding: 2px;
            }}
            QMenu::item {{
                padding: 4px 8px;
                border-radius: 12px;
            }}
            QMenu::item:selected {{ background-color: {config.ACCENT_COLOR}55; }}
        """)

        ask_action = menu.addAction("💬  Bunu sor")
        ask_action.triggered.connect(lambda: self._ask_about_selection(selected_text))

        cursor_pos = label.mapToGlobal(label.rect().center())
        menu.exec(cursor_pos)

    def _ask_about_selection(self, selected_text: str):
        self.input_field.setText(f"\"{selected_text}\" hakkında: ")
        self.input_field.setFocus()
        self.input_field.setCursorPosition(len(self.input_field.text()))

    def _apply_accent(self):
        color = config.ACCENT_COLOR
        ai_color = config.AI_COLOR

        self._icon_label.setStyleSheet(f"color: {color};")
        self.update()

        self._search_btn.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; color: #8b949e; border: none; border-radius: 14px; }}
            QPushButton:hover {{ background-color: #21262d; color: {color}; }}
            QPushButton:checked {{ color: {color}; }}
        """)

        self._search_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0d1117;
                color: #e6edf3;
                border: 1px solid {color};
                border-radius: 14px;
                padding: 0px 12px;
            }}
        """)

        self.input_field.setStyleSheet(f"""
            QTextEdit {{
                background-color: #21262d;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 18px;
                padding: 8px 14px;
            }}
            QTextEdit:focus {{ border: 1px solid {color}; }}
        """)

        self._style_send_button(
            running=bool(self._worker and self._worker.isRunning())
        )

        for i in range(self._messages_layout.count() - 1):
            item = self._messages_layout.itemAt(i)
            if not item or not item.widget():
                continue
            for card in item.widget().findChildren(QWidget, "messageCard"):
                if card.property("message_role") == "user":
                    card.setStyleSheet(f"""
                        QWidget#messageCard {{
                            background-color: {color};
                            border-radius: 14px;
                            border-bottom-right-radius: 3px;
                        }}
                    """)
                else:
                    card.setStyleSheet(f"""
                        QWidget#messageCard {{
                            background-color: {ai_color};
                            border: 1px solid rgba(255, 255, 255, 18);
                            border-radius: 14px;
                            border-bottom-left-radius: 3px;
                        }}
                    """)

    def _open_history(self):
        pos = self.frameGeometry().topLeft()
        self._history.move(pos.x() + 10, pos.y() + 60)
        self._history.show()

    def _start_mic(self):
        self._speech.stop()
        self._mic_btn.setText("⏹")
        self.input_field.setPlaceholderText("Dinleniyor...")
        from core.worker import MicWorker
        self._mic_worker = MicWorker()
        self._mic_worker.text_ready.connect(self._on_mic_result)
        self._mic_worker.start()
        if self._on_presence_callback:
            self._on_presence_callback("listening")

    def _stop_mic(self):
        self._mic_btn.setText("🎤")
        self.input_field.setPlaceholderText("Mesaj yaz...")

    def _on_mic_result(self, text: str):
        self._mic_btn.setChecked(False)
        self._mic_btn.setText("🎤")
        self.input_field.setPlaceholderText("Mesaj yaz...")
        if text:
            if self._on_presence_callback:
                self._on_presence_callback("idle")
            self.input_field.setText(text)
            self._send_message()
        else:
            if self._on_presence_callback:
                self._on_presence_callback("alert")
            self._add_message("🎤 Ses anlaşılamadı, tekrar dene.", is_user=False)

    def _toggle_mic(self):
        if self._mic_btn.isChecked():
            self._mic_btn.setChecked(False)
            self._stop_mic()
        else:
            self._mic_btn.setChecked(True)
            self._start_mic()


class MapBackgroundWidget(QWidget):

    # Türkiye UTC+3'ü yıl boyunca sabit kullanır.
    LATITUDE = 41.0082
    LONGITUDE = 28.9784
    TURKEY_TIMEZONE = timezone(timedelta(hours=3), name="Türkiye")

    def __init__(self):
        super().__init__()
        portrait_path = os.path.join(
            config.RESOURCE_DIR,
            "assets",
            "chaos_observatory_background.png",
        )
        landscape_path = os.path.join(
            config.RESOURCE_DIR,
            "assets",
            "chaos_observatory_background_wide.png",
        )
        self._portrait_pixmap = QPixmap(portrait_path)
        self._landscape_pixmap = QPixmap(landscape_path)
        self._pixmap = self._portrait_pixmap
        self._scaled = QPixmap()
        self._cached_viewport_size = None
        self._message_count = 0

        # Güneş/ay konumu ve ışık rengi gerçek saat ilerledikçe güncellenir.
        self._sky_timer = QTimer(self)
        self._sky_timer.setInterval(30_000)
        self._sky_timer.timeout.connect(self.update)
        self._sky_timer.start()

    def set_message_count(self, count: int):
        """Sohbet yoğunlaştıkça arka planı kademeli olarak geri plana iter."""
        self._message_count = max(0, count)
        self.update()

    def _draw_conversation_scrim(
        self, painter: QPainter, width: int, height: int
    ):
        # İlk mesajda sahne canlı kalır; her yeni mesaj küçük bir kademe ekler.
        alpha = min(48, max(0, (self._message_count - 1) * 8))
        if alpha:
            painter.fillRect(0, 0, width, height, QColor(5, 9, 16, alpha))

    @staticmethod
    def _draw_chat_glass(
        painter: QPainter, width: int, height: int
    ):
        """Geniş ekranda mesajları tek bir hafif cam kolonunda toplar."""
        if width < 900:
            return

        column_width = _chat_column_width(width)
        x = (width - column_width) / 2
        panel_rect = QRectF(x, 12, column_width, max(1, height - 24))
        panel_path = QPainterPath()
        panel_path.addRoundedRect(panel_rect, 24, 24)

        glass = QLinearGradient(panel_rect.left(), 0, panel_rect.right(), 0)
        glass.setColorAt(0.0, QColor(8, 11, 20, 54))
        glass.setColorAt(0.08, QColor(8, 11, 20, 92))
        glass.setColorAt(0.50, QColor(8, 11, 20, 72))
        glass.setColorAt(0.92, QColor(8, 11, 20, 92))
        glass.setColorAt(1.0, QColor(8, 11, 20, 54))

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillPath(panel_path, glass)
        painter.setPen(QPen(QColor(255, 255, 255, 16), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(panel_path)
        painter.restore()

    @staticmethod
    def _smoothstep(value: float) -> float:
        value = max(0.0, min(1.0, value))
        return value * value * (3.0 - 2.0 * value)

    @classmethod
    def _solar_time(cls, date_value, sunrise: bool) -> float:
        """NOAA yaklaşımıyla yerel gün doğumu/batımı saatini hesaplar."""
        day_number = date_value.timetuple().tm_yday
        longitude_hour = cls.LONGITUDE / 15.0
        base_hour = 6.0 if sunrise else 18.0
        approximate = day_number + ((base_hour - longitude_hour) / 24.0)

        mean_anomaly = (0.9856 * approximate) - 3.289
        true_longitude = (
            mean_anomaly
            + 1.916 * math.sin(math.radians(mean_anomaly))
            + 0.020 * math.sin(math.radians(2 * mean_anomaly))
            + 282.634
        ) % 360.0

        right_ascension = math.degrees(
            math.atan(0.91764 * math.tan(math.radians(true_longitude)))
        ) % 360.0
        longitude_quadrant = math.floor(true_longitude / 90.0) * 90.0
        ascension_quadrant = math.floor(right_ascension / 90.0) * 90.0
        right_ascension = (
            right_ascension + longitude_quadrant - ascension_quadrant
        ) / 15.0

        sin_declination = 0.39782 * math.sin(math.radians(true_longitude))
        cos_declination = math.cos(math.asin(sin_declination))
        cos_hour_angle = (
            math.cos(math.radians(90.833))
            - sin_declination * math.sin(math.radians(cls.LATITUDE))
        ) / (cos_declination * math.cos(math.radians(cls.LATITUDE)))
        cos_hour_angle = max(-1.0, min(1.0, cos_hour_angle))

        hour_angle = math.degrees(math.acos(cos_hour_angle))
        if sunrise:
            hour_angle = 360.0 - hour_angle
        hour_angle /= 15.0

        local_mean_time = (
            hour_angle + right_ascension - 0.06571 * approximate - 6.622
        )
        utc_hour = (local_mean_time - longitude_hour) % 24.0
        return (utc_hour + 3.0) % 24.0

    @classmethod
    def _light_levels(cls, now: datetime) -> tuple[float, float, float, float]:
        """
        night, warm, sun_progress ve moon_progress değerlerini döndürür.
        Geçişler gün doğumu/batımının çevresinde yumuşatılır.
        """
        hour = now.hour + now.minute / 60.0 + now.second / 3600.0
        sunrise = cls._solar_time(now.date(), sunrise=True)
        sunset = cls._solar_time(now.date(), sunrise=False)

        dawn_start, dawn_end = sunrise - 1.0, sunrise + 0.55
        dusk_start, dusk_end = sunset - 0.75, sunset + 1.0

        if hour < dawn_start or hour >= dusk_end:
            night = 1.0
        elif dawn_start <= hour < dawn_end:
            night = 1.0 - cls._smoothstep((hour - dawn_start) / (dawn_end - dawn_start))
        elif dusk_start <= hour < dusk_end:
            night = cls._smoothstep((hour - dusk_start) / (dusk_end - dusk_start))
        else:
            night = 0.0

        sunrise_glow = math.exp(-((hour - sunrise) / 0.75) ** 2)
        sunset_glow = math.exp(-((hour - sunset) / 0.9) ** 2)
        warm = max(sunrise_glow, sunset_glow)

        sun_progress = max(0.0, min(1.0, (hour - sunrise) / max(0.1, sunset - sunrise)))
        night_length = (24.0 - sunset) + sunrise
        if hour >= sunset:
            elapsed_night = hour - sunset
        elif hour < sunrise:
            elapsed_night = hour + 24.0 - sunset
        else:
            # Ay, gün batımından önceki alacakaranlıkta doğu ufkunda belirir.
            elapsed_night = 0.0
        moon_progress = max(0.0, min(1.0, elapsed_night / max(0.1, night_length)))
        return night, warm, sun_progress, moon_progress

    def _ensure_scaled(self, width: int, height: int):
        use_landscape = width / max(1, height) > 1.05
        size_key = (width, height, use_landscape)
        if size_key == self._cached_viewport_size:
            return
        self._cached_viewport_size = size_key
        self._pixmap = (
            self._landscape_pixmap
            if use_landscape and not self._landscape_pixmap.isNull()
            else self._portrait_pixmap
        )
        self._scaled = self._pixmap.scaled(
            width,
            height,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )

    @staticmethod
    def _draw_sun(
        painter: QPainter, x: float, y: float, radius: float, opacity: float
    ):
        if opacity <= 0.01:
            return
        painter.save()
        painter.setOpacity(opacity)

        glow = QRadialGradient(x, y, radius * 3.2)
        glow.setColorAt(0.0, QColor(255, 238, 145, 190))
        glow.setColorAt(0.30, QColor(255, 205, 78, 88))
        glow.setColorAt(1.0, QColor(255, 177, 45, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(
            QRectF(
                x - radius * 3.2,
                y - radius * 3.2,
                radius * 6.4,
                radius * 6.4,
            )
        )

        ray_pen = QPen(
            QColor(255, 224, 116, 118),
            max(1.15, radius * 0.075),
        )
        ray_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(ray_pen)
        ray_angles = (7, 46, 89, 133, 178, 221, 267, 311, 344)
        for index, degrees in enumerate(ray_angles):
            angle = math.radians(degrees)
            inner = radius * (1.38 + (index % 2) * 0.06)
            outer = radius * (1.70 + (index % 3) * 0.10)
            painter.drawLine(
                int(x + math.cos(angle) * inner),
                int(y + math.sin(angle) * inner),
                int(x + math.cos(angle) * outer),
                int(y + math.sin(angle) * outer),
            )

        core = QRadialGradient(x - radius * 0.28, y - radius * 0.30, radius * 1.4)
        core.setColorAt(0.0, QColor("#fffbd0"))
        core.setColorAt(0.55, QColor("#ffe47c"))
        core.setColorAt(1.0, QColor("#f6bd45"))
        painter.setPen(QPen(QColor(255, 246, 184, 190), 1.0))
        painter.setBrush(core)
        painter.drawEllipse(QRectF(x - radius, y - radius, radius * 2, radius * 2))
        painter.restore()

    @staticmethod
    def _draw_moon(
        painter: QPainter, x: float, y: float, radius: float, opacity: float
    ):
        if opacity <= 0.01:
            return
        painter.save()
        painter.setOpacity(opacity)

        glow = QRadialGradient(x, y, radius * 3.0)
        glow.setColorAt(0.0, QColor(213, 226, 255, 165))
        glow.setColorAt(0.38, QColor(128, 157, 225, 65))
        glow.setColorAt(1.0, QColor(82, 112, 185, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(
            QRectF(
                x - radius * 3.0,
                y - radius * 3.0,
                radius * 6.0,
                radius * 6.0,
            )
        )

        disc = QRadialGradient(
            x - radius * 0.32, y - radius * 0.36, radius * 1.55
        )
        disc.setColorAt(0.0, QColor("#ffffff"))
        disc.setColorAt(0.58, QColor("#e8efff"))
        disc.setColorAt(1.0, QColor("#aebddd"))
        painter.setPen(QPen(QColor(235, 242, 255, 180), 1.0))
        painter.setBrush(disc)
        painter.drawEllipse(QRectF(x - radius, y - radius, radius * 2, radius * 2))

        painter.setPen(Qt.NoPen)
        craters = (
            (-0.34, -0.24, 0.23, 60),
            (0.31, -0.12, 0.17, 48),
            (-0.05, 0.35, 0.27, 42),
            (0.43, 0.36, 0.10, 36),
        )
        for dx, dy, scale, alpha in craters:
            crater_radius = radius * scale
            painter.setBrush(QColor(105, 127, 170, alpha))
            painter.drawEllipse(
                QRectF(
                    x + radius * dx - crater_radius,
                    y + radius * dy - crater_radius,
                    crater_radius * 2,
                    crater_radius * 2,
                )
            )
        painter.restore()

    @staticmethod
    def _draw_chaos_planet(
        painter: QPainter,
        width: int,
        height: int,
        orbit_progress: float,
        night: float,
    ):
        """Türkiye saatine bağlı, 24 saatte bir eliptik tur atan temsili gezegen."""
        angle = (2.0 * math.pi * orbit_progress) - math.pi
        x = width * (0.50 + 0.34 * math.cos(angle))
        y = height * (0.29 + 0.17 * math.sin(angle))
        radius = max(13.0, min(width, height) * 0.052)

        painter.save()
        glow = QRadialGradient(x, y, radius * 3.1)
        glow.setColorAt(0.0, QColor(139, 83, 194, 130))
        glow.setColorAt(0.38, QColor(91, 48, 145, 55))
        glow.setColorAt(1.0, QColor(42, 25, 73, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(
            QRectF(
                x - radius * 3.1,
                y - radius * 3.1,
                radius * 6.2,
                radius * 6.2,
            )
        )

        painter.translate(x, y)
        painter.rotate(-17)
        ring_rect = QRectF(
            -radius * 1.85,
            -radius * 0.48,
            radius * 3.70,
            radius * 0.96,
        )
        ring_pen = QPen(QColor(180, 125, 215, 125), max(1.2, radius * 0.09))
        ring_pen.setCapStyle(Qt.RoundCap)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(ring_pen)
        painter.drawEllipse(ring_rect)

        disc = QRadialGradient(
            -radius * 0.30,
            -radius * 0.34,
            radius * 1.55,
        )
        disc.setColorAt(0.0, QColor("#9b6aae"))
        disc.setColorAt(0.42, QColor("#55345f"))
        disc.setColorAt(0.78, QColor("#28213c"))
        disc.setColorAt(1.0, QColor("#121522"))
        painter.setPen(QPen(QColor(167, 117, 190, 155), 1.0))
        painter.setBrush(disc)
        painter.drawEllipse(
            QRectF(-radius, -radius, radius * 2.0, radius * 2.0)
        )

        # Gezegen yüzeyinde iki sade kaos yarığı.
        crack_pen = QPen(QColor(214, 91, 158, 150), max(1.0, radius * 0.055))
        crack_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(crack_pen)
        crack = QPainterPath()
        crack.moveTo(-radius * 0.18, -radius * 0.78)
        crack.lineTo(-radius * 0.05, -radius * 0.25)
        crack.lineTo(-radius * 0.25, radius * 0.10)
        crack.lineTo(-radius * 0.10, radius * 0.70)
        painter.drawPath(crack)

        # Ön taraftaki halka parçası kürenin üstünden geçer.
        front_ring = QPen(
            QColor(208, 150, 225, 165),
            max(1.3, radius * 0.095),
        )
        front_ring.setCapStyle(Qt.RoundCap)
        painter.setPen(front_ring)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(ring_rect, 200 * 16, 140 * 16)
        painter.restore()

    def _draw_time_layer(
        self,
        painter: QPainter,
        width: int,
        height: int,
        scene_x: int = 0,
        scene_width: int | None = None,
    ):
        now = datetime.now(self.TURKEY_TIMEZONE)
        night, _, _, _ = self._light_levels(now)
        seconds = now.hour * 3600 + now.minute * 60 + now.second
        orbit_progress = seconds / 86_400.0
        scene_width = scene_width or width

        # Dünya zaten karanlık; saat farkı yalnızca çok yumuşak bir ortam
        # tonuyla hissedilir. Ani gündüz/gece geçişi yapılmaz.
        ambient_alpha = int(12 + night * 36)
        painter.fillRect(
            0,
            0,
            width,
            height,
            QColor(3, 5, 16, ambient_alpha),
        )

        # Az sayıda, düşük kontrastlı kozmik parçacık.
        painter.save()
        painter.setPen(Qt.NoPen)
        particle_alpha = int(42 + night * 34)
        for index in range(13):
            unit_x = (
                math.sin((index + 3) * 17.123) * 31847.221
            ) % 1.0
            unit_y = (
                math.sin((index + 5) * 61.731) * 19114.537
            ) % 1.0
            x = scene_x + scene_width * (0.05 + unit_x * 0.90)
            y = height * (0.04 + unit_y * 0.48)
            radius = 0.65 + (index % 2) * 0.35
            painter.setBrush(QColor(191, 164, 218, particle_alpha))
            painter.drawEllipse(
                QRectF(
                    x - radius,
                    y - radius,
                    radius * 2,
                    radius * 2,
                )
            )
        painter.restore()

        painter.save()
        painter.translate(scene_x, 0)
        self._draw_chaos_planet(
            painter, scene_width, height, orbit_progress, night
        )
        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self._pixmap.isNull():
            # Widget mesajlarla uzasa bile arka plan yalnızca görünür viewport
            # ölçüsüne göre ölçeklenir. Böylece sohbet ettikçe yakınlaşmaz.
            visible = self.visibleRegion().boundingRect()
            viewport = self.parentWidget()
            width = viewport.width() if viewport else visible.width()
            height = viewport.height() if viewport else visible.height()
            width = max(1, width)
            height = max(1, height)
            self._ensure_scaled(width, height)

            painter.save()
            painter.setClipRect(visible)
            painter.translate(visible.topLeft())
            painter.fillRect(0, 0, width, height, QColor("#181426"))
            x = (width - self._scaled.width()) // 2
            # Alt kenarı koru; fazla yükseklik yalnızca gökyüzünden kırpılır.
            y = height - self._scaled.height()
            painter.drawPixmap(x, y, self._scaled)
            self._draw_conversation_scrim(painter, width, height)
            self._draw_time_layer(
                painter, width, height, x, self._scaled.width()
            )
            self._draw_chat_glass(painter, width, height)
            painter.restore()
        else:
            painter.fillRect(self.rect(), QColor("#111318"))
