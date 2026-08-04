from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class DailySettingsWindow(QWidget):
    saved = Signal()

    def __init__(self, service):
        super().__init__()
        self._service = service
        self._drag_pos = None
        self.setFixedSize(380, 330)
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
        root.setContentsMargins(18, 14, 18, 18)
        root.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("Günlük Özet Ayarları")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        title.setStyleSheet("color:#e6edf3;")
        close = QPushButton("×")
        close.setFixedSize(28, 28)
        close.clicked.connect(self.hide)
        close.setStyleSheet(
            "QPushButton{background:transparent;color:#8b949e;border:none;"
            "border-radius:14px;font-size:18px;}"
            "QPushButton:hover{background:#e74c3c;color:white;}"
        )
        header.addWidget(title)
        header.addStretch()
        header.addWidget(close)

        description = QLabel(
            "Sabah özeti 05.00–11.59, akşam özeti 18.00–23.59 arasında "
            "günde bir kez gösterilir."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color:#8b949e;")

        self._enabled = QCheckBox("Otomatik günlük özetleri etkinleştir")
        self._morning = QCheckBox("Sabah özetini göster")
        self._evening = QCheckBox("Akşam özetini göster")
        for box in (self._enabled, self._morning, self._evening):
            box.setStyleSheet("QCheckBox{color:#c9d1d9;spacing:8px;}")

        city_label = QLabel("Hava durumu şehri")
        city_label.setStyleSheet("color:#8b949e;")
        self._city = QLineEdit()
        self._city.setPlaceholderText("İstanbul")
        self._city.setStyleSheet(
            "QLineEdit{background:#0d1117;color:#e6edf3;border:1px solid "
            "#30363d;border-radius:8px;padding:8px;}"
            "QLineEdit:focus{border-color:#4a9eff;}"
        )
        save = QPushButton("Kaydet")
        save.setFixedHeight(36)
        save.clicked.connect(self._save)
        save.setStyleSheet(
            "QPushButton{background:#1f4f8f;color:#e6edf3;border:none;border-radius:8px;}"
            "QPushButton:hover{background:#4a9eff;}"
        )

        root.addLayout(header)
        root.addWidget(description)
        root.addWidget(self._enabled)
        root.addWidget(self._morning)
        root.addWidget(self._evening)
        root.addWidget(city_label)
        root.addWidget(self._city)
        root.addStretch()
        root.addWidget(save)

    def show(self):
        settings = self._service.get_settings()
        self._enabled.setChecked(bool(settings["enabled"]))
        self._morning.setChecked(bool(settings["morning_enabled"]))
        self._evening.setChecked(bool(settings["evening_enabled"]))
        self._city.setText(settings["city"])
        super().show()
        self.raise_()

    def _save(self):
        self._service.update_settings(
            enabled=self._enabled.isChecked(),
            morning_enabled=self._morning.isChecked(),
            evening_enabled=self._evening.isChecked(),
            city=self._city.text(),
        )
        self.saved.emit()
        self.hide()
