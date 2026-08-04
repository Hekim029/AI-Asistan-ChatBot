from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


CATEGORY_NAMES = {
    "name": "İsim",
    "profession": "Meslek",
    "preferences": "Tercih",
    "schedule": "Düzen",
    "goals": "Hedef",
    "misc": "Diğer",
}


class MemoryWindow(QWidget):
    """Kullanıcının kalıcı Heko hafızasını görmesini ve yönetmesini sağlar."""

    def __init__(self, user_memory):
        super().__init__()
        self._memory = user_memory
        self._drag_pos = None
        self.setFixedSize(430, 540)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
        )
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
            self._drag_pos = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )

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
        header.setFixedHeight(52)
        header.setStyleSheet(
            "background:#0d1117; border-top-left-radius:11px;"
            "border-top-right-radius:11px;"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 12, 0)
        title = QLabel("Heko Hafızası")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title.setStyleSheet("color:#e6edf3;")
        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#8b949e;border:none;"
            "border-radius:14px;font-size:18px;}"
            "QPushButton:hover{background:#e74c3c;color:white;}"
        )
        close_btn.clicked.connect(self.hide)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)

        intro = QLabel(
            "Heko'nun senin hakkında kalıcı olarak tuttuğu bilgiler. "
            "İstemediğin kayıtları buradan silebilirsin."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#8b949e; padding:14px 16px 10px;")

        self._search = QLineEdit()
        self._search.setPlaceholderText("Hafızada ara...")
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet(
            "QLineEdit{background:#0d1117;color:#e6edf3;border:1px solid "
            "#30363d;border-radius:8px;padding:8px 10px;margin:0 14px 8px;}"
            "QLineEdit:focus{border-color:#4a9eff;}"
        )
        self._search.textChanged.connect(self.refresh)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._content = QWidget()
        self._content.setStyleSheet("background:transparent;")
        self._list = QVBoxLayout(self._content)
        self._list.setContentsMargins(14, 6, 14, 14)
        self._list.setSpacing(8)
        self._list.addStretch()
        scroll.setWidget(self._content)
        self._scroll = scroll

        root.addWidget(header)
        root.addWidget(intro)
        root.addWidget(self._search)
        root.addWidget(scroll, 1)

    def show(self):
        self.refresh()
        super().show()
        self.raise_()

    def refresh(self):
        while self._list.count() > 1:
            item = self._list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        entries = self._memory.get_entries()
        query = self._search.text().strip().casefold()
        if query:
            entries = [
                entry for entry in entries
                if query in str(entry.get("value", "")).casefold()
                or query in CATEGORY_NAMES.get(
                    entry.get("category"), entry.get("category", "")
                ).casefold()
            ]
        if not entries:
            empty = QLabel(
                "Aramayla eşleşen kayıt yok."
                if query else "Henüz kayıtlı bir bilgi yok."
            )
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color:#8b949e; padding:40px;")
            self._list.insertWidget(0, empty)
            return

        for entry in entries:
            self._list.insertWidget(
                self._list.count() - 1,
                self._build_entry(entry),
            )

    def _build_entry(self, entry):
        card = QFrame()
        card.setStyleSheet(
            "QFrame{background:#1e242c;border:1px solid #30363d;"
            "border-radius:10px;}"
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 8, 10)

        text_column = QVBoxLayout()
        category = QLabel(
            CATEGORY_NAMES.get(entry.get("category"), entry.get("category", ""))
        )
        category.setFont(QFont("Segoe UI", 8, QFont.Bold))
        category.setStyleSheet("color:#4a9eff;border:none;background:transparent;")
        value = QLabel(str(entry.get("value", "")))
        value.setWordWrap(True)
        value.setFont(QFont("Segoe UI", 9))
        value.setStyleSheet("color:#e6edf3;border:none;background:transparent;")
        updated = QLabel(entry.get("updated_at", "").replace("T", " "))
        updated.setFont(QFont("Segoe UI", 7))
        updated.setStyleSheet("color:#6e7681;border:none;background:transparent;")
        text_column.addWidget(category)
        text_column.addWidget(value)
        text_column.addWidget(updated)

        edit_btn = QPushButton("Düzenle")
        edit_btn.setFixedSize(62, 28)
        edit_btn.setStyleSheet(
            "QPushButton{background:#17263a;color:#79b8ff;border:1px solid "
            "#264f78;border-radius:7px;}"
            "QPushButton:hover{background:#21456b;color:white;}"
        )
        edit_btn.clicked.connect(
            lambda checked=False, e=entry: self._edit_entry(e)
        )

        delete_btn = QPushButton("Sil")
        delete_btn.setFixedSize(48, 28)
        delete_btn.setStyleSheet(
            "QPushButton{background:#2d1b1b;color:#f08888;border:1px solid "
            "#5a2d2d;border-radius:7px;}"
            "QPushButton:hover{background:#5a2424;color:white;}"
        )
        delete_btn.clicked.connect(
            lambda checked=False, e=entry: self._delete_entry(e)
        )
        row.addLayout(text_column, 1)
        actions = QVBoxLayout()
        actions.setSpacing(6)
        actions.addWidget(edit_btn)
        actions.addWidget(delete_btn)
        row.addLayout(actions)
        return card

    def _edit_entry(self, entry):
        old_value = str(entry.get("value", ""))
        value, accepted = QInputDialog.getText(
            self,
            "Hafızayı düzenle",
            "Bilgi:",
            QLineEdit.Normal,
            old_value,
        )
        if not accepted or not value.strip():
            return

        keys = list(CATEGORY_NAMES)
        labels = [CATEGORY_NAMES[key] for key in keys]
        current = keys.index(entry.get("category")) if entry.get("category") in keys else 0
        label, accepted = QInputDialog.getItem(
            self,
            "Hafıza kategorisi",
            "Kategori:",
            labels,
            current,
            False,
        )
        if not accepted:
            return
        category = keys[labels.index(label)]
        if self._memory.update_entry(entry.get("id", ""), category, value):
            self.refresh()
            QTimer.singleShot(0, self.raise_)

    def _delete_entry(self, entry):
        value = str(entry.get("value", ""))
        answer = QMessageBox.question(
            self,
            "Hafızadan sil",
            f"'{value}' bilgisi kalıcı hafızadan silinsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        entry_id = entry.get("id", "")
        if entry_id:
            self._memory.remove_by_id(entry_id)
        else:
            self._memory.remove(entry.get("category", ""), value)
        self.refresh()
        QTimer.singleShot(0, self.raise_)
