# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPainter, QColor, QPainterPath
from memory.context_manager import ContextManager
import utils.config as config


class HistoryWindow(QWidget):

    def __init__(self, context: ContextManager):
        super().__init__()
        self._context = context
        self._drag_pos = None
        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        self.setFixedSize(360, 500)
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
        layout.addWidget(self._build_scroll(), stretch=1)

    def _build_header(self):
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet("background-color: #0d1117; border-radius: 12px;")

        h = QHBoxLayout(header)
        h.setContentsMargins(16, 0, 16, 0)

        title = QLabel("📜  Konuşma Geçmişi")
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

    def _build_scroll(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background-color: transparent;")
        scroll.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical { width: 3px; background: transparent; }
            QScrollBar::handle:vertical { background: #30363d; border-radius: 2px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        self._content = QWidget()
        self._content.setStyleSheet("background-color: transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(16, 12, 16, 12)
        self._content_layout.setSpacing(8)
        self._content_layout.addStretch()

        scroll.setWidget(self._content)
        self._scroll = scroll
        return scroll

    def show(self):
        self._load_history()
        super().show()
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def _load_history(self):
        # Önce temizle
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        history = self._context.get_history()
        if not history:
            empty = QLabel("Henüz konuşma yok.")
            empty.setFont(QFont("Segoe UI", 9))
            empty.setStyleSheet("color: #8b949e;")
            empty.setAlignment(Qt.AlignCenter)
            self._content_layout.insertWidget(0, empty)
            return

        for i, msg in enumerate(history):
            role = msg.get("role", "")
            text = msg.get("content", "")
            is_user = role == "user"

            outer = QHBoxLayout()
            outer.setContentsMargins(0, 0, 0, 0)

            bubble = QLabel(text)
            bubble.setWordWrap(True)
            bubble.setFont(QFont("Segoe UI", 9))
            bubble.setTextFormat(Qt.PlainText)
            bubble.setMaximumWidth(260)

            if is_user:
                bubble.setStyleSheet(f"""
                    background-color: {config.ACCENT_COLOR};
                    color: #e6edf3;
                    border-radius: 12px;
                    border-bottom-right-radius: 3px;
                    padding: 8px 12px;
                """)
                outer.addStretch()
                outer.addWidget(bubble)
            else:
                bubble.setStyleSheet(f"""
                    background-color: {config.AI_COLOR};
                    color: #e6edf3;
                    border-radius: 12px;
                    border-bottom-left-radius: 3px;
                    padding: 8px 12px;
                """)
                outer.addWidget(bubble)
                outer.addStretch()

            wrapper = QWidget()
            wrapper.setStyleSheet("background-color: transparent;")
            wrapper.setLayout(outer)
            self._content_layout.insertWidget(self._content_layout.count() - 1, wrapper)