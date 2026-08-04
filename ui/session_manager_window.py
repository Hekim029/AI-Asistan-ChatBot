from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QInputDialog, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget
)


class SessionManagerWindow(QWidget):
    """Açık, gizli ve diskte kayıtlı sohbet oturumlarını yönetir."""

    def __init__(self, session_provider, show_callback, hide_callback, new_callback, rename_callback):
        super().__init__()
        self._provider = session_provider
        self._show_session = show_callback
        self._hide_session = hide_callback
        self._new_session = new_callback
        self._rename_session = rename_callback
        self._drag_pos = None
        self.setFixedSize(410, 480)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(750)
        self._refresh_timer.timeout.connect(self.refresh)
        self._setup_ui()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        painter.fillPath(path, QColor("#161b22"))
        painter.setPen(QColor("#30363d"))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)
        header = QWidget()
        header.setFixedHeight(54)
        header.setStyleSheet(
            "background:#0d1117;border-top-left-radius:11px;border-top-right-radius:11px;"
        )
        row = QHBoxLayout(header)
        row.setContentsMargins(14, 0, 10, 0)
        title = QLabel("Sohbet Oturumları")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title.setStyleSheet("color:#e6edf3;")
        new_btn = QPushButton("+ Yeni")
        new_btn.setFixedSize(66, 30)
        new_btn.clicked.connect(self._create_new)
        new_btn.setStyleSheet(self._blue_button())
        close = QPushButton("×")
        close.setFixedSize(28, 28)
        close.clicked.connect(self.hide)
        close.setStyleSheet(
            "QPushButton{background:transparent;color:#8b949e;border:none;"
            "border-radius:14px;font-size:18px;}"
            "QPushButton:hover{background:#e74c3c;color:white;}"
        )
        row.addWidget(title)
        row.addStretch()
        row.addWidget(new_btn)
        row.addWidget(close)

        intro = QLabel(
            "Kapatılan sohbetler silinmez; gizli duruma geçer. Buradan yeniden açabilirsin."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#8b949e;padding:12px 14px 6px;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        content = QWidget()
        content.setStyleSheet("background:transparent;")
        self._list = QVBoxLayout(content)
        self._list.setContentsMargins(12, 8, 12, 12)
        self._list.setSpacing(8)
        self._list.addStretch()
        scroll.setWidget(content)
        root.addWidget(header)
        root.addWidget(intro)
        root.addWidget(scroll, 1)

    @staticmethod
    def _blue_button():
        return (
            "QPushButton{background:#17263a;color:#79b8ff;border:1px solid "
            "#264f78;border-radius:7px;}"
            "QPushButton:hover{background:#21456b;color:white;}"
        )

    def show(self):
        self.refresh()
        super().show()
        self._refresh_timer.start()
        self.raise_()
        self.activateWindow()

    def hideEvent(self, event):
        self._refresh_timer.stop()
        super().hideEvent(event)

    def refresh(self):
        while self._list.count() > 1:
            item = self._list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        sessions = self._provider()
        if not sessions:
            empty = QLabel("Henüz sohbet oturumu yok.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color:#8b949e;padding:40px;")
            self._list.insertWidget(0, empty)
            return
        for session in sessions:
            self._list.insertWidget(self._list.count() - 1, self._card(session))

    def _card(self, session):
        card = QFrame()
        card.setStyleSheet(
            "QFrame{background:#1e242c;border:1px solid #30363d;border-radius:9px;}"
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 10, 10)
        texts = QVBoxLayout()
        name = QLabel(session["name"])
        name.setStyleSheet("color:#e6edf3;border:none;background:transparent;")
        state_text = "Açık" if session["visible"] else "Gizli — yeniden açılabilir"
        state = QLabel(state_text)
        state.setStyleSheet(
            f"color:{'#3fb950' if session['visible'] else '#8b949e'};"
            "font-size:10px;border:none;background:transparent;"
        )
        texts.addWidget(name)
        texts.addWidget(state)
        rename = QPushButton("Adlandır")
        rename.setFixedSize(68, 30)
        rename.setStyleSheet(self._blue_button())
        rename.clicked.connect(
            lambda checked=False, value=session: self._request_rename(value)
        )
        action = QPushButton("Gizle" if session["visible"] else "Aç")
        action.setFixedSize(62, 30)
        action.setStyleSheet(self._blue_button())
        if session["visible"]:
            action.clicked.connect(
                lambda checked=False, sid=session["id"]: self._toggle_hide(sid)
            )
        else:
            action.clicked.connect(
                lambda checked=False, sid=session["id"]: self._toggle_show(sid)
            )
        row.addLayout(texts, 1)
        row.addWidget(rename)
        row.addWidget(action)
        return card

    def _toggle_show(self, session_id):
        self._show_session(session_id)
        self.refresh()

    def _toggle_hide(self, session_id):
        self._hide_session(session_id)
        self.refresh()

    def _create_new(self):
        self._new_session()
        self.refresh()

    def _request_rename(self, session):
        value, accepted = QInputDialog.getText(
            self, "Sohbeti adlandır", "Sohbet adı:", text=session["name"]
        )
        if accepted and value.strip():
            self._rename_session(session["id"], value.strip())
            self.refresh()
