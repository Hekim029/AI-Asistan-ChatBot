import sys
import os
 
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

import sys
import keyboard
from PySide6.QtWidgets import QApplication, QWidget, QMenu
from PySide6.QtCore import QTimer, Qt, Signal, QObject
from PySide6.QtGui import QPainter, QColor, QFont, QLinearGradient, QRadialGradient
from ui.chat_window import ChatWindow

class HotkeySignal(QObject):
    triggered = Signal()

class FloatingButton(QWidget):

    def __init__(self, chat_window: ChatWindow):
        super().__init__()
        self._flash_timer = QTimer()
        self._flash_timer.timeout.connect(self._flash_step)
        self._flash_count = 0
        self._is_flashing = False
        self._chat = chat_window
        self._drag_pos = None
        self._drag_moved = False
        self._hotkey_signal = HotkeySignal()
        self._hotkey_signal.triggered.connect(self._toggle_chat)
        self._setup()

    def start_flash(self):
        if self._is_flashing:
            return
        self._is_flashing = True
        self._flash_count = 0
        self._flash_timer.start(150)

    def stop_flash(self):
        self._flash_timer.stop()
        self._is_flashing = False
        self._flash_count = 0
        self.update()

    def _flash_step(self):
        self._flash_count += 1
        if self._flash_count > 12:
            self.stop_flash()
            return
        self.update()

    def _setup(self):
        self.setFixedSize(64, 64)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setToolTip("AI Assistant — Sağ tık: Kapat")

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 90, screen.height() - 130)

        keyboard.add_hotkey("ctrl+shift+space", self._hotkey_signal.triggered.emit)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        glow = QRadialGradient(32, 32, 32)
        glow.setColorAt(0.6, QColor(74, 158, 255, 60))
        glow.setColorAt(1.0, QColor(74, 158, 255, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 64, 64)

        if self._is_flashing and self._flash_count % 2 == 0:
            c1, c2 = QColor("#00ff88"), QColor("#00aa55")
        else:
            c1, c2 = QColor("#1a6fd4"), QColor("#0a3d7a")

        gradient = QLinearGradient(8, 8, 56, 56)
        gradient.setColorAt(0, c1)
        gradient.setColorAt(1, c2)
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(8, 8, 48, 48)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(74, 158, 255, 180))
        painter.drawEllipse(8, 8, 48, 48)

        painter.setFont(QFont("Segoe UI Emoji", 20))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(self.rect(), Qt.AlignCenter, "🚀")

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            menu = QMenu()
            menu.setStyleSheet("""
                QMenu { background-color: #161b22; color: #e6edf3; border: 1px solid #30363d; border-radius: 6px; padding: 4px; }
                QMenu::item { padding: 6px 20px; border-radius: 4px; }
                QMenu::item:selected { background-color: #e74c3c; }
            """)
            quit_action = menu.addAction("✕  Kapat")
            quit_action.triggered.connect(QApplication.quit)
            menu.exec(event.globalPosition().toPoint())
        elif event.button() == Qt.LeftButton:
            self._drag_moved = False
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self._drag_moved = True
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and not self._drag_moved:
            self._toggle_chat()
        self._drag_pos = None
        self._drag_moved = False

    def _toggle_chat(self):
        if self._chat.isVisible():
            self._chat.hide()
            return

        screen = QApplication.primaryScreen().availableGeometry()
        btn = self.frameGeometry()
        chat_w = self._chat.width()
        chat_h = self._chat.height()

        x = btn.x() - chat_w + 64
        x = max(0, min(x, screen.width() - chat_w))

        if btn.y() - chat_h - 10 >= screen.top():
            y = btn.y() - chat_h - 10
        else:
            y = btn.y() + btn.height() + 10

        y = max(screen.top(), min(y, screen.bottom() - chat_h))

        self._chat.move(x, y)
        self._chat.show()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    chat = ChatWindow()
    button = FloatingButton(chat)
    chat._on_response_callback = button.start_flash
    button.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()