# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QScrollArea, QLabel, QFrame, QApplication, QMenu
)
from PySide6.QtCore import Qt, QDateTime, QTimer
from PySide6.QtGui import QFont, QPainter, QColor, QPixmap, QPainterPath
from core.router import Router
from core.worker import ResponseWorker
from ui.settings_window import SettingsWindow
from core.daily_motivation import get_today_motivation


class ChatWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.router = Router()
        self._settings = SettingsWindow()
        self._drag_pos = None
        self._typing_dots = 0
        self._typing_timer = QTimer()
        self._typing_timer.timeout.connect(self._animate_typing)
        self._typing_label = None
        self._typing_wrapper = None
        self._worker = None
        self._is_online = True
        self._on_response_callback = None
        self._setup_window()
        self._setup_ui()
        QTimer.singleShot(500, self._show_welcome)

    def _setup_window(self):
        self.setWindowTitle("Heko")
        self.setFixedSize(404, 584)
        self.setStyleSheet("background-color: transparent;")
        self.setAttribute(Qt.WA_TranslucentBackground)
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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        painter.setClipPath(path)
        painter.fillPath(path, QColor("#111318"))
        painter.setPen(QColor("#000000"))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    def _setup_ui(self):
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: transparent;")
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

        title = QLabel("AI Assistant")
        title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title.setStyleSheet("color: #e6edf3; margin-left: 8px;")

        self._status_btn = QPushButton("● online")
        self._status_btn.setFont(QFont("Segoe UI", 8))
        self._status_btn.setCheckable(True)
        self._status_btn.setChecked(True)
        self._status_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #3fb950;
                border: 1px solid #3fb950;
                border-radius: 8px;
                padding: 2px 8px;
            }
            QPushButton:checked {
                background-color: transparent;
                color: #3fb950;
                border: 1px solid #3fb950;
            }
            QPushButton:!checked {
                color: #8b949e;
                border: 1px solid #8b949e;
            }
        """)
        self._status_btn.clicked.connect(self._toggle_online)

        self._search_btn = QPushButton("🔍")
        self._search_btn.setFixedSize(28, 28)
        self._search_btn.setFont(QFont("Segoe UI", 11))
        self._search_btn.setCheckable(True)
        self._search_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #8b949e; border: none; border-radius: 14px; }
            QPushButton:hover { background-color: #21262d; color: #4a9eff; }
            QPushButton:checked { color: #4a9eff; }
        """)
        self._search_btn.setToolTip("Mesaj ara")
        self._search_btn.clicked.connect(self._toggle_search)

        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(28, 28)
        settings_btn.setFont(QFont("Segoe UI", 11))
        settings_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #8b949e; border: none; border-radius: 14px; }
            QPushButton:hover { background-color: #21262d; color: #4a9eff; }
        """)
        settings_btn.setToolTip("Ayarlar")
        settings_btn.clicked.connect(self._open_settings)

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
        layout.addWidget(self._status_btn)
        layout.addStretch()
        layout.addWidget(self._search_btn)
        layout.addWidget(settings_btn)
        layout.addWidget(clear_btn)
        layout.addWidget(close_btn)

        return header_widget

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
        input_widget.setStyleSheet("background-color: #161b22; border: none;")

        layout = QVBoxLayout(input_widget)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText("Mesajlarda ara...")
        self._search_bar.setFont(QFont("Segoe UI", 9))
        self._search_bar.setFixedHeight(30)
        self._search_bar.setVisible(False)
        self._search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #0d1117;
                color: #e6edf3;
                border: 1px solid #4a9eff;
                border-radius: 14px;
                padding: 0px 12px;
            }
        """)
        self._search_bar.textChanged.connect(self._search_messages)

        send_layout = QHBoxLayout()
        send_layout.setSpacing(8)
        send_layout.setContentsMargins(0, 0, 0, 0)

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

        send_layout.addWidget(self.input_field)
        send_layout.addWidget(send_btn)

        layout.addWidget(self._search_bar)
        layout.addLayout(send_layout)

        return input_widget

    def _show_welcome(self):
        self._add_message("Merhaba Ben Heko Sana Nasıl Yardımcı Olabilirim?", is_user=False)
        motivation = get_today_motivation()
        if motivation:
            QTimer.singleShot(1000, lambda: self._add_message(motivation, is_user=False))

    def _toggle_online(self):
        self._is_online = self._status_btn.isChecked()
        if self._is_online:
            self._status_btn.setText("● online")
            motivation = get_today_motivation()
            msg = "Uyandım! Sana yardımcı olmaya hazırım. 👋"
            if motivation:
                msg += f"\n\n{motivation}"
            self._add_message(msg, is_user=False)
        else:
            self._status_btn.setText("● offline")
            self._add_message("Uyuyorum... Uyandırmak için online yap. 💤", is_user=False)

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
                if child.styleSheet() and "border-radius" in child.styleSheet():
                    bubble = child
                    break
            if not bubble:
                continue
            if not query:
                wrapper.setVisible(True)
            else:
                wrapper.setVisible(query in bubble.text().lower())

    def _add_message(self, text: str, is_user: bool):
        timestamp = QDateTime.currentDateTime().toString("hh:mm")

        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setFont(QFont("Gill Sans MT", 10, QFont.Bold))
        bubble.setTextFormat(Qt.PlainText)
        bubble.setMaximumWidth(290)
        bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bubble.mouseReleaseEvent = lambda e: self._on_selection_changed(bubble)

        time_label = QLabel(timestamp)
        time_label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        time_label.setStyleSheet("color: #8b949e; margin: 0px 4px;")
        time_label.setAlignment(Qt.AlignBottom)

        if is_user:
            bubble.setStyleSheet("""
                background-color: #1f4f8f;
                color: #e6edf3;
                border-radius: 14px;
                border-bottom-right-radius: 3px;
                padding: 10px 14px;
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
                padding: 10px 14px;
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

        if not self._is_online:
            self._add_message("💤 Şu an uyuyorum, uyandırmak için online yap.", is_user=False)
            self.input_field.clear()
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
        if self._on_response_callback:
            self._on_response_callback()

    def _on_error(self, error: str):
        self._hide_typing_indicator()
        self._add_message(f"⚠️ {error}", is_user=False)
        self.input_field.setEnabled(True)
        self._worker = None

    def _on_selection_changed(self, label: QLabel):
        selected = label.selectedText()
        if selected.strip():
            QTimer.singleShot(100, lambda: self._show_selection_popup(selected, label))

    def _show_selection_popup(self, selected_text: str, label: QLabel):
        if not selected_text.strip():
            return

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e242c;
                color: #e6edf3;
                border: 1px solid #4a9eff;
                border-radius: 12px;
                padding: 2px;
            }
            QMenu::item {
                padding: 4px 8px;
                border-radius: 12px;
            }
            QMenu::item:selected { background-color: #1f4f8f; }
        """)

        ask_action = menu.addAction("💬  Bunu sor")
        ask_action.triggered.connect(lambda: self._ask_about_selection(selected_text))

        cursor_pos = label.mapToGlobal(label.rect().center())
        menu.exec(cursor_pos)

    def _ask_about_selection(self, selected_text: str):
        self.input_field.setText(f"\"{selected_text}\" hakkında: ")
        self.input_field.setFocus()
        self.input_field.setCursorPosition(len(self.input_field.text()))


class MapBackgroundWidget(QWidget):

    def __init__(self):
        super().__init__()
        self._pixmap = QPixmap("assets/arka_plan_3.jpg")

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        else:
            painter.fillRect(self.rect(), QColor("#111318"))
