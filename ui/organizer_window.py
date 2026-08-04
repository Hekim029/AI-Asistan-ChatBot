from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class OrganizerWindow(QWidget):
    """Görev, not ve hatırlatıcıları sohbetten bağımsız yöneten merkez."""

    def __init__(self, task_manager, reminder_manager, shared_workspace=None):
        super().__init__()
        self._tasks = task_manager
        self._reminders = reminder_manager
        self._workspace = shared_workspace
        self._drag_pos = None
        self.setFixedSize(520, 600)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
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
            "background:#0d1117;border-top-left-radius:11px;"
            "border-top-right-radius:11px;"
        )
        row = QHBoxLayout(header)
        row.setContentsMargins(16, 0, 12, 0)
        title = QLabel("Kontrol Merkezi")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title.setStyleSheet("color:#e6edf3;")
        refresh = QPushButton("Yenile")
        refresh.setFixedSize(62, 28)
        refresh.clicked.connect(self.refresh)
        refresh.setStyleSheet(self._button_style("#17263a", "#79b8ff", "#264f78"))
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
        row.addWidget(refresh)
        row.addWidget(close)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane{border:none;background:#161b22;}"
            "QTabBar::tab{background:#0d1117;color:#8b949e;padding:10px 18px;"
            "border:none;border-bottom:2px solid transparent;}"
            "QTabBar::tab:selected{color:#e6edf3;border-bottom-color:#4a9eff;}"
        )
        self._task_page, self._task_list = self._make_page()
        self._note_page, self._note_list = self._make_page()
        self._reminder_page, self._reminder_list = self._make_page()
        self._activity_page, self._activity_list = self._make_page()
        self._tabs.addTab(self._task_page, "Görevler")
        self._tabs.addTab(self._note_page, "Notlar")
        self._tabs.addTab(self._reminder_page, "Hatırlatıcılar")
        self._tabs.addTab(self._activity_page, "Çalışmalar")

        root.addWidget(header)
        root.addWidget(self._tabs, 1)

    @staticmethod
    def _make_page():
        page = QWidget()
        page.setStyleSheet("background:#161b22;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        content = QWidget()
        content.setStyleSheet("background:transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        return page, content_layout

    @staticmethod
    def _button_style(background, color, border):
        return (
            f"QPushButton{{background:{background};color:{color};border:1px solid "
            f"{border};border-radius:7px;}}"
            "QPushButton:hover{background:#21456b;color:white;}"
        )

    @staticmethod
    def _clear(layout):
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show(self):
        self.refresh()
        super().show()
        self.raise_()

    def refresh(self):
        self._refresh_tasks()
        self._refresh_notes()
        self._refresh_reminders()
        self._refresh_activity()

    def _empty(self, text):
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color:#8b949e;padding:40px;")
        return label

    def _card(self, title, detail="", action_text="", action=None):
        card = QFrame()
        card.setStyleSheet(
            "QFrame{background:#1e242c;border:1px solid #30363d;border-radius:9px;}"
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 10, 10)
        texts = QVBoxLayout()
        main = QLabel(title)
        main.setWordWrap(True)
        main.setStyleSheet("color:#e6edf3;border:none;background:transparent;")
        texts.addWidget(main)
        if detail:
            sub = QLabel(detail)
            sub.setWordWrap(True)
            sub.setStyleSheet("color:#8b949e;font-size:10px;border:none;background:transparent;")
            texts.addWidget(sub)
        row.addLayout(texts, 1)
        if action_text and action:
            button = QPushButton(action_text)
            button.setFixedSize(72, 30)
            button.setStyleSheet(self._button_style("#17263a", "#79b8ff", "#264f78"))
            button.clicked.connect(action)
            row.addWidget(button)
        return card

    def _refresh_tasks(self):
        self._clear(self._task_list)
        items = self._tasks.pending_tasks()
        self._tabs.setTabText(0, f"Görevler ({len(items)})")
        if not items:
            self._task_list.insertWidget(0, self._empty("Bekleyen görev yok."))
        for item in items:
            due = self._format_date(item.get("due_at", ""))
            if item.get("due_at"):
                try:
                    parsed_due = datetime.fromisoformat(item["due_at"]).astimezone()
                    if parsed_due < datetime.now().astimezone():
                        due = f"GECİKMİŞ: {due}"
                except (TypeError, ValueError):
                    pass
            self._task_list.insertWidget(
                self._task_list.count() - 1,
                self._card(
                    item.get("title", ""),
                    f"Tarih: {due}" if due else "Tarih belirtilmedi",
                    "Tamamla",
                    lambda checked=False, i=item: self._complete_task(i["id"]),
                ),
            )

    def _refresh_notes(self):
        self._clear(self._note_list)
        items = self._tasks.notes()
        self._tabs.setTabText(1, f"Notlar ({len(items)})")
        if not items:
            self._note_list.insertWidget(0, self._empty("Kayıtlı not yok."))
        for item in items:
            tags = ", ".join(item.get("tags") or [])
            self._note_list.insertWidget(
                self._note_list.count() - 1,
                self._card(item.get("text", ""), f"Etiketler: {tags}" if tags else ""),
            )

    def _refresh_reminders(self):
        self._clear(self._reminder_list)
        items = self._reminders.pending()
        self._tabs.setTabText(2, f"Hatırlatıcılar ({len(items)})")
        if not items:
            self._reminder_list.insertWidget(0, self._empty("Bekleyen hatırlatıcı yok."))
        for item in items:
            self._reminder_list.insertWidget(
                self._reminder_list.count() - 1,
                self._card(
                    item.get("text", ""),
                    self._format_date(item.get("due_at", "")),
                    "İptal et",
                    lambda checked=False, i=item: self._cancel_reminder(i["id"]),
                ),
            )

    def _refresh_activity(self):
        self._clear(self._activity_list)
        items = self._workspace.recent(limit=30) if self._workspace is not None else []
        sessions = {item.get("session_id") for item in items}
        self._tabs.setTabText(3, f"Çalışmalar ({len(sessions)})")
        if not items:
            self._activity_list.insertWidget(0, self._empty("Paylaşılan çalışma yok."))
        for item in items:
            created = self._format_date(item.get("created_at", ""))
            detail = f"{item.get('session_id')} · {created}\n{item.get('content', '')[:350]}"
            self._activity_list.insertWidget(
                self._activity_list.count() - 1,
                self._card(item.get("title", "Çalışma"), detail),
            )

    def _complete_task(self, task_id):
        self._tasks.complete_task(task_id=task_id)
        self.refresh()

    def _cancel_reminder(self, reminder_id):
        self._reminders.cancel(reminder_id=reminder_id)
        self.refresh()

    @staticmethod
    def _format_date(value):
        if not value:
            return ""
        try:
            return datetime.fromisoformat(value).astimezone().strftime("%d.%m.%Y %H:%M")
        except (TypeError, ValueError):
            return str(value)
