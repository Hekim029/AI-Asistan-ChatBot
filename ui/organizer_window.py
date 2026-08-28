from datetime import datetime

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QCheckBox, QDateTimeEdit, QDialog, QDialogButtonBox, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)


class OrganizerItemDialog(QDialog):
    """Görev, not ve hatırlatıcı için ortak, sade düzenleme formu."""

    TITLES = {
        "task": "Görev", "note": "Not", "reminder": "Hatırlatıcı",
        "activity": "Çalışma",
    }

    def __init__(self, item_type: str, item: dict | None = None, parent=None):
        super().__init__(parent)
        self._item_type = item_type
        self._item = item or {}
        action = "Düzenle" if item else "Yeni Ekle"
        self.setWindowTitle(f"{self.TITLES[item_type]} · {action}")
        self.setModal(True)
        self.setFixedWidth(470)
        self.setStyleSheet(self._style())
        self._setup_ui()

    @staticmethod
    def _style():
        return """
            QDialog { background:#161b22; color:#e6edf3; }
            QLabel { color:#c9d1d9; }
            QLineEdit, QTextEdit, QDateTimeEdit {
                background:#0d1117; color:#e6edf3; border:1px solid #30363d;
                border-radius:7px; padding:7px;
            }
            QLineEdit:focus, QTextEdit:focus, QDateTimeEdit:focus {
                border-color:#4a9eff;
            }
            QPushButton {
                background:#1f4f8f; color:white; border:none;
                border-radius:7px; padding:8px 18px;
            }
            QPushButton:hover { background:#4a9eff; }
            QCheckBox { color:#8b949e; spacing:8px; }
        """

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)
        heading = QLabel(self.windowTitle())
        heading.setFont(QFont("Segoe UI", 12, QFont.Bold))
        root.addWidget(heading)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignTop)
        if self._item_type == "note":
            self._text = QTextEdit()
            self._text.setFixedHeight(120)
            self._text.setPlainText(self._item.get("text", ""))
            self._text.setPlaceholderText("Hatırlanmasını istediğin notu yaz...")
            self._tags = QLineEdit(", ".join(self._item.get("tags") or []))
            self._tags.setPlaceholderText("Örn: proje, tasarım, fikir")
            form.addRow("Not", self._text)
            form.addRow("Etiketler", self._tags)
        elif self._item_type == "activity":
            self._title = QLineEdit(self._item.get("title", ""))
            self._title.setMaxLength(300)
            self._title.setPlaceholderText("Örn: Python araştırması")
            self._text = QTextEdit()
            self._text.setFixedHeight(150)
            self._text.setPlainText(self._item.get("content", ""))
            self._text.setPlaceholderText(
                "Heko'nun diğer pencerelerde de bilmesini istediğin çalışma özeti..."
            )
            form.addRow("Başlık", self._title)
            form.addRow("İçerik", self._text)
        else:
            self._text = QLineEdit(
                self._item.get("title", "")
                if self._item_type == "task"
                else self._item.get("text", "")
            )
            self._text.setMaxLength(2000)
            self._text.setPlaceholderText(
                "Görev başlığı" if self._item_type == "task" else "Hatırlatıcı metni"
            )
            form.addRow(
                "Başlık" if self._item_type == "task" else "Metin", self._text
            )
            self._use_due = QCheckBox("Tarih ve saat kullan")
            self._due = QDateTimeEdit()
            self._due.setCalendarPopup(True)
            self._due.setDisplayFormat("dd.MM.yyyy HH:mm")
            self._due.setMinimumDateTime(
                QDateTime.currentDateTime()
                if self._item_type == "reminder"
                else QDateTime.currentDateTime().addYears(-10)
            )
            current_due = self._item.get("due_at", "")
            parsed = QDateTime.fromString(current_due, Qt.ISODate) if current_due else QDateTime()
            self._due.setDateTime(
                parsed if parsed.isValid() else QDateTime.currentDateTime().addSecs(3600)
            )
            if self._item_type == "reminder":
                self._use_due.setChecked(True)
                self._use_due.hide()
            else:
                self._use_due.setChecked(bool(current_due))
                self._use_due.toggled.connect(self._due.setEnabled)
                form.addRow("", self._use_due)
            self._due.setEnabled(self._use_due.isChecked())
            form.addRow("Tarih", self._due)

        root.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Kaydet")
        buttons.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def values(self) -> dict:
        if self._item_type == "note":
            return {
                "text": self._text.toPlainText().strip(),
                "tags": [v.strip() for v in self._tags.text().split(",") if v.strip()],
            }
        if self._item_type == "activity":
            return {
                "title": self._title.text().strip(),
                "content": self._text.toPlainText().strip(),
            }
        due_at = self._due.dateTime().toString(Qt.ISODate) if self._use_due.isChecked() else ""
        if self._item_type == "task":
            return {"title": self._text.text().strip(), "due_at": due_at}
        return {"text": self._text.text().strip(), "due_at": due_at}


class OrganizerWindow(QWidget):
    """Heko ve kullanıcı tarafından ortak kullanılan düzenleme merkezi."""

    def __init__(self, task_manager, reminder_manager, shared_workspace=None):
        super().__init__()
        self._tasks = task_manager
        self._reminders = reminder_manager
        self._workspace = shared_workspace
        self._drag_pos = None
        self.setFixedSize(720, 650)
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
        header.setFixedHeight(58)
        header.setStyleSheet(
            "background:#0d1117;border-top-left-radius:11px;border-top-right-radius:11px;"
        )
        row = QHBoxLayout(header)
        row.setContentsMargins(18, 0, 14, 0)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title = QLabel("Kontrol Merkezi")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet("color:#e6edf3;")
        subtitle = QLabel("Heko ile aynı görev, not ve hatırlatıcıları kullanır")
        subtitle.setStyleSheet("color:#6e7681;font-size:9px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        refresh = QPushButton("Yenile")
        refresh.setFixedSize(72, 30)
        refresh.clicked.connect(self.refresh)
        refresh.setStyleSheet(self._button_style("#17263a", "#79b8ff", "#264f78"))
        close = QPushButton("×")
        close.setFixedSize(30, 30)
        close.clicked.connect(self.hide)
        close.setStyleSheet(
            "QPushButton{background:transparent;color:#8b949e;border:none;"
            "border-radius:15px;font-size:18px;}"
            "QPushButton:hover{background:#e74c3c;color:white;}"
        )
        row.addLayout(title_box)
        row.addStretch()
        row.addWidget(refresh)
        row.addWidget(close)

        self._tabs = QTabWidget()
        self._tabs.tabBar().setExpanding(True)
        self._tabs.tabBar().setUsesScrollButtons(False)
        self._tabs.setStyleSheet(
            "QTabWidget::pane{border:none;background:#161b22;}"
            "QTabBar::tab{background:#0d1117;color:#8b949e;padding:11px 10px;"
            "border:none;border-bottom:2px solid transparent;}"
            "QTabBar::tab:selected{color:#e6edf3;border-bottom-color:#4a9eff;}"
            "QTabBar::tab:hover{color:#c9d1d9;}"
        )
        self._task_page, self._task_list = self._make_page("+ Yeni Görev", self._add_task)
        self._note_page, self._note_list = self._make_page("+ Yeni Not", self._add_note)
        self._reminder_page, self._reminder_list = self._make_page(
            "+ Yeni Hatırlatıcı", self._add_reminder
        )
        self._activity_page, self._activity_list = self._make_page(
            "+ Yeni Çalışma", self._add_activity
        )
        self._tabs.addTab(self._task_page, "Görevler")
        self._tabs.addTab(self._note_page, "Notlar")
        self._tabs.addTab(self._reminder_page, "Hatırlatıcılar")
        self._tabs.addTab(self._activity_page, "Çalışmalar")
        root.addWidget(header)
        root.addWidget(self._tabs, 1)

    def _make_page(self, add_text="", add_action=None):
        page = QWidget()
        page.setStyleSheet("background:#161b22;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)
        if add_text and add_action:
            toolbar = QHBoxLayout()
            hint = QLabel("Değişiklikler Heko'ya anında yansır.")
            hint.setStyleSheet("color:#6e7681;font-size:9px;")
            add_button = QPushButton(add_text)
            add_button.setFixedHeight(34)
            add_button.setStyleSheet(self._button_style("#1f4f8f", "#ffffff", "#4a9eff"))
            add_button.clicked.connect(add_action)
            toolbar.addWidget(hint)
            toolbar.addStretch()
            toolbar.addWidget(add_button)
            layout.addLayout(toolbar)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        content = QWidget()
        content.setStyleSheet("background:transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(9)
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        return page, content_layout

    @staticmethod
    def _button_style(background, color, border):
        return (
            f"QPushButton{{background:{background};color:{color};border:1px solid "
            f"{border};border-radius:7px;padding:0 12px;}}"
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
        label.setStyleSheet("color:#8b949e;padding:48px;")
        return label

    def _card(self, title, detail="", actions=None):
        card = QFrame()
        card.setStyleSheet("QFrame{background:#1e242c;border:1px solid #30363d;border-radius:10px;}")
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 12, 12, 12)
        row.setSpacing(12)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        main = QLabel(title)
        main.setWordWrap(True)
        main.setTextInteractionFlags(Qt.TextSelectableByMouse)
        main.setStyleSheet("color:#e6edf3;border:none;background:transparent;")
        texts.addWidget(main)
        if detail:
            sub = QLabel(detail)
            sub.setWordWrap(True)
            sub.setStyleSheet("color:#8b949e;font-size:10px;border:none;background:transparent;")
            texts.addWidget(sub)
        row.addLayout(texts, 1)
        if actions:
            action_row = QHBoxLayout()
            action_row.setSpacing(6)
            for text, callback, danger in actions:
                button = QPushButton(text)
                button.setFixedHeight(30)
                button.setStyleSheet(self._button_style(
                    "#351b20" if danger else "#17263a",
                    "#ff7b72" if danger else "#79b8ff",
                    "#6e2b33" if danger else "#264f78",
                ))
                button.clicked.connect(callback)
                action_row.addWidget(button)
            row.addLayout(action_row)
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
                    if datetime.fromisoformat(item["due_at"]).astimezone() < datetime.now().astimezone():
                        due = f"GECİKMİŞ: {due}"
                except (TypeError, ValueError):
                    pass
            self._task_list.insertWidget(self._task_list.count() - 1, self._card(
                item.get("title", ""), f"Tarih: {due}" if due else "Tarih belirtilmedi",
                [
                    ("Düzenle", lambda checked=False, i=item: self._edit_task(i), False),
                    ("Tamamla", lambda checked=False, i=item: self._complete_task(i["id"]), False),
                    ("Sil", lambda checked=False, i=item: self._delete_task(i), True),
                ],
            ))

    def _refresh_notes(self):
        self._clear(self._note_list)
        items = self._tasks.notes()
        self._tabs.setTabText(1, f"Notlar ({len(items)})")
        if not items:
            self._note_list.insertWidget(0, self._empty("Kayıtlı not yok."))
        for item in items:
            tags = ", ".join(item.get("tags") or [])
            self._note_list.insertWidget(self._note_list.count() - 1, self._card(
                item.get("text", ""), f"Etiketler: {tags}" if tags else "Etiket yok",
                [
                    ("Düzenle", lambda checked=False, i=item: self._edit_note(i), False),
                    ("Sil", lambda checked=False, i=item: self._delete_note(i), True),
                ],
            ))

    def _refresh_reminders(self):
        self._clear(self._reminder_list)
        items = self._reminders.pending()
        self._tabs.setTabText(2, f"Hatırlatıcılar ({len(items)})")
        if not items:
            self._reminder_list.insertWidget(0, self._empty("Bekleyen hatırlatıcı yok."))
        for item in items:
            self._reminder_list.insertWidget(self._reminder_list.count() - 1, self._card(
                item.get("text", ""), self._format_date(item.get("due_at", "")),
                [
                    ("Düzenle", lambda checked=False, i=item: self._edit_reminder(i), False),
                    ("İptal", lambda checked=False, i=item: self._cancel_reminder(i["id"]), False),
                    ("Sil", lambda checked=False, i=item: self._delete_reminder(i), True),
                ],
            ))

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
            self._activity_list.insertWidget(self._activity_list.count() - 1, self._card(
                item.get("title", "Çalışma"), detail,
                [
                    ("Düzenle", lambda checked=False, i=item: self._edit_activity(i), False),
                    ("Sil", lambda checked=False, i=item: self._delete_activity(i), True),
                ],
            ))

    def _dialog_values(self, item_type, item=None):
        dialog = OrganizerItemDialog(item_type, item, self)
        return dialog.values() if dialog.exec() == QDialog.Accepted else None

    def _run_change(self, action):
        try:
            result = action()
            if result is None:
                raise ValueError("Kayıt bulunamadı; listeyi yenileyip tekrar dene.")
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.warning(self, "İşlem tamamlanamadı", str(exc))
            return False
        self.refresh()
        return True

    def _confirm_delete(self, label):
        answer = QMessageBox.question(
            self, "Kaydı sil", f"“{label[:80]}” kaydı kalıcı olarak silinsin mi?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def _add_task(self):
        values = self._dialog_values("task")
        if values:
            self._run_change(lambda: self._tasks.add_task(**values))

    def _edit_task(self, item):
        values = self._dialog_values("task", item)
        if values:
            self._run_change(lambda: self._tasks.update_task(item["id"], **values))

    def _delete_task(self, item):
        if self._confirm_delete(item.get("title", "Görev")):
            self._run_change(lambda: self._tasks.delete_task(item["id"]))

    def _complete_task(self, task_id):
        self._run_change(lambda: self._tasks.complete_task(task_id=task_id))

    def _add_note(self):
        values = self._dialog_values("note")
        if values:
            self._run_change(lambda: self._tasks.add_note(**values))

    def _edit_note(self, item):
        values = self._dialog_values("note", item)
        if values:
            self._run_change(lambda: self._tasks.update_note(item["id"], **values))

    def _delete_note(self, item):
        if self._confirm_delete(item.get("text", "Not")):
            self._run_change(lambda: self._tasks.delete_note(item["id"]))

    def _add_reminder(self):
        values = self._dialog_values("reminder")
        if values:
            self._run_change(lambda: self._reminders.add(**values))

    def _edit_reminder(self, item):
        values = self._dialog_values("reminder", item)
        if values:
            self._run_change(lambda: self._reminders.update(item["id"], **values))

    def _cancel_reminder(self, reminder_id):
        self._run_change(lambda: self._reminders.cancel(reminder_id=reminder_id))

    def _delete_reminder(self, item):
        if self._confirm_delete(item.get("text", "Hatırlatıcı")):
            self._run_change(lambda: self._reminders.delete(item["id"]))

    def _add_activity(self):
        if self._workspace is None:
            QMessageBox.warning(self, "Kullanılamıyor", "Ortak çalışma alanı bağlı değil.")
            return
        values = self._dialog_values("activity")
        if values:
            self._run_change(
                lambda: self._workspace.publish("manual", "manual", **values)
            )

    def _edit_activity(self, item):
        values = self._dialog_values("activity", item)
        if values:
            self._run_change(
                lambda: self._workspace.update_event(item["id"], **values)
            )

    def _delete_activity(self, item):
        if self._confirm_delete(item.get("title", "Çalışma")):
            self._run_change(lambda: self._workspace.delete_event(item["id"]))

    @staticmethod
    def _format_date(value):
        if not value:
            return ""
        try:
            return datetime.fromisoformat(value).astimezone().strftime("%d.%m.%Y %H:%M")
        except (TypeError, ValueError):
            return str(value)
