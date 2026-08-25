import sys
import os
import math
import random

if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

ffmpeg_path = r"C:\Users\muham\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin"
os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")

import keyboard
from PySide6.QtWidgets import (
    QApplication, QWidget, QMenu, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PySide6.QtCore import QTimer, Qt, Signal, QObject, QPoint, QRect
from PySide6.QtGui import QPainter, QColor, QFont, QPixmap
from ui.chat_window import ChatWindow
from services.error_logger import configure_logging
from core.shared_state import SharedAssistantState
from ui.session_manager_window import SessionManagerWindow
from services.session_registry import SessionRegistry


class HotkeySignal(QObject):
    triggered = Signal()


class FloatingButton(QWidget):
    """
    Ekranda dolaşan mini asistan butonu.

    GEZİNME (WANDER) MANTIĞI:
      Kullanıcı butonu sürükleyip bir yere bıraktığında, o nokta "yuva"
      (anchor) olur. Buton kendi çapına oranlı küçük bir alan içinde
      (varsayılan: çapının ~2.5 katı yarıçap) kendi kendine gezinir:

        1) Rastgele bir süre (2-6 saniye) yerinde durur (idle)
        2) Yuvaya yakın rastgele bir nokta seçer
        3) O noktaya YAVAŞÇA kayar (adım adım, timer ile)
        4) Vardığında tekrar 1'e döner

      Kullanıcı butonu sürüklerken (fare basılıyken) gezinme DURUR —
      kullanıcının kontrolüyle çakışmaz. Bırakınca yeni yuva o an
      bulunduğu nokta olur ve gezinme oradan devam eder.
    """

    # Gezinme alanının yarıçapı, buton çapının kaç katı olacak
    WANDER_RADIUS_MULTIPLIER = 0.8

    # Saniyede kaç piksel hareket etsin (yavaş, doğal bir yürüyüş hissi için)
    WANDER_SPEED_PX_PER_TICK = 1.2
    WANDER_TICK_MS = 30

    # Bir noktaya vardıktan sonra ne kadar bekleyip tekrar hareket etsin (saniye)
    WANDER_IDLE_MIN_SEC = 2.0
    WANDER_IDLE_MAX_SEC = 6.0

    # Göz kırpma sıklığı (saniye) — rastgeleliği ile daha "canlı" hissettirir
    BLINK_MIN_SEC = 2.5
    BLINK_MAX_SEC = 6.0
    BLINK_DURATION_MS = 130

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

        # ── Gezinme durumu ──
        self._anchor = QPoint(0, 0)          # "yuva" — sürükleyip bıraktığın nokta
        self._wander_target = None            # şu an gitmekte olduğu nokta (None = duruyor)
        self._facing_left = False             # emoji/karakter hangi yöne baksın
        self._wander_step_timer = QTimer()
        self._wander_step_timer.timeout.connect(self._wander_step)
        self._wander_step_timer.setInterval(self.WANDER_TICK_MS)

        # ── Animasyon durumu (pet çizimi için) ──
        self._anim_frame = 0
        self._blinking = False
        self._pet_state = "idle"
        self._state_timer = QTimer()
        self._state_timer.setSingleShot(True)
        self._state_timer.timeout.connect(lambda: self.set_pet_state("idle"))
        sprite_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets",
            "void_herald_sprite_strip.png",
        )
        self._sprite = QPixmap(sprite_path)
        self._schedule_next_blink()

        self._setup()
        self._start_wandering_from_current_position()

        # main() tarafından atanır — sohbet penceresi açılınca
        # yanındaki durum balonunun gizlenmesi için kullanılır.
        self._on_chat_opened = None

    # ═════════════════════════════════════════
    #  Gezinme (Wander)
    # ═════════════════════════════════════════

    def _start_wandering_from_current_position(self):
        """Mevcut konumu yuva yapar ve gezinmeyi başlatır."""
        self._anchor = self.pos()
        self._wander_step_timer.start()
        self._schedule_next_move()

    def _schedule_next_move(self):
        """Rastgele bir bekleme süresinden sonra yeni bir hedef seçer."""
        idle_ms = int(random.uniform(
            self.WANDER_IDLE_MIN_SEC, self.WANDER_IDLE_MAX_SEC
        ) * 1000)
        QTimer.singleShot(idle_ms, self._pick_new_wander_target)

    def _pick_new_wander_target(self):
        """
        Yuvanın etrafında, yarıçap içinde rastgele bir hedef nokta seçer.
        Sürükleme sırasındaysa hedef seçmeyi erteler.
        """
        if self._drag_pos is not None:
            # Kullanıcı şu an sürüklüyor, gezinmeye karışma
            self._schedule_next_move()
            return

        radius = self.width() * self.WANDER_RADIUS_MULTIPLIER
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(0, radius)

        target_x = self._anchor.x() + dist * math.cos(angle)
        target_y = self._anchor.y() + dist * math.sin(angle)

        target_x, target_y = self._clamp_to_screen(target_x, target_y)
        self._wander_target = QPoint(int(target_x), int(target_y))

    def _wander_step(self):
        """
        Her tick'te çağrılır. İki işi var:
          1) Animasyon karesini ilerlet ve yeniden çizdir (bounce, yürüme
             efekti sürükleme/idle fark etmeksizin her zaman aksın diye)
          2) Sürükleme yoksa ve bir hedef varsa ona bir adım yaklaş
        """
        self._anim_frame += 1
        self.update()

        if self._drag_pos is not None or self._wander_target is None:
            return

        current = self.pos()
        dx = self._wander_target.x() - current.x()
        dy = self._wander_target.y() - current.y()
        dist = math.hypot(dx, dy)

        if dist <= self.WANDER_SPEED_PX_PER_TICK:
            # Hedefe vardı
            self.move(self._wander_target)
            self._wander_target = None
            self._schedule_next_move()
            return

        # Yön takibi — karakter hareket yönüne baksın
        if dx < -0.5:
            self._facing_left = True
        elif dx > 0.5:
            self._facing_left = False

        step_x = self.WANDER_SPEED_PX_PER_TICK * dx / dist
        step_y = self.WANDER_SPEED_PX_PER_TICK * dy / dist
        self.move(int(current.x() + step_x), int(current.y() + step_y))

    def _clamp_to_screen(self, x: float, y: float) -> tuple[float, float]:
        """Hedefin ekran dışına çıkmasını engeller (görev çubuğu dahil hesaba katılır)."""
        screen = QApplication.primaryScreen().availableGeometry()
        x = max(screen.left(), min(x, screen.right() - self.width()))
        y = max(screen.top(), min(y, screen.bottom() - self.height()))
        return x, y

    # ═════════════════════════════════════════
    #  Göz kırpma animasyonu
    # ═════════════════════════════════════════

    def _schedule_next_blink(self):
        """Rastgele bir süre sonra göz kırpmayı tetikler."""
        delay_ms = int(random.uniform(self.BLINK_MIN_SEC, self.BLINK_MAX_SEC) * 1000)
        QTimer.singleShot(delay_ms, self._do_blink)

    def _do_blink(self):
        """Gözleri kısa süreliğine kapatır, sonra tekrar açar."""
        self._blinking = True
        QTimer.singleShot(self.BLINK_DURATION_MS, self._end_blink)

    def _end_blink(self):
        self._blinking = False
        self._schedule_next_blink()

    def set_pet_state(self, state: str, reset_after_ms: int = 0):
        """Yapılan işe göre karakterin idle, busy veya alert pozunu gösterir."""
        if state not in {"idle", "busy", "alert"}:
            state = "idle"
        self._pet_state = state
        self._state_timer.stop()
        if reset_after_ms:
            self._state_timer.start(reset_after_ms)
        self.update()

    # ═════════════════════════════════════════
    #  Flash (yeni mesaj bildirimi)
    # ═════════════════════════════════════════

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

    # ═════════════════════════════════════════
    #  Kurulum
    # ═════════════════════════════════════════

    def _setup(self):
        self.setFixedSize(128, 116)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setToolTip("AI Assistant — Sağ tık: Kapat")

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 160, screen.height() - 180)

        keyboard.add_hotkey("ctrl+shift+space", self._hotkey_signal.triggered.emit)
        # Tek harfli global kısayol yanlışlıkla mikrofonu açabildiği için kaldırıldı.
        keyboard.add_hotkey("ctrl+shift+m", lambda: self._chat._toggle_mic())

    # ═════════════════════════════════════════
    #  Çizim
    # ═════════════════════════════════════════

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)

        if self._sprite.isNull():
            painter.setPen(QColor("#f0c995"))
            painter.drawText(self.rect(), Qt.AlignCenter, "AI")
            return

        # Yatay sprite şeridi: idle, blink, busy, alert.
        frame_w = self._sprite.width() // 4
        frame_h = self._sprite.height()
        if self._pet_state == "busy":
            frame_index = 2
        elif self._pet_state == "alert" or (
            self._is_flashing and self._flash_count % 2 == 0
        ):
            frame_index = 3
        elif self._blinking:
            frame_index = 1
        else:
            frame_index = 0
        source = QRect(frame_index * frame_w, 0, frame_w, frame_h)

        bounce = int(2 * math.sin(self._anim_frame * 0.12))
        target = QRect(3, 2 + bounce, self.width() - 6, self.height() - 6)

        painter.save()
        if self._facing_left:
            painter.translate(self.width(), 0)
            painter.scale(-1, 1)
        painter.drawPixmap(target, self._sprite, source)
        painter.restore()

    # ═════════════════════════════════════════
    #  Fare olayları
    # ═════════════════════════════════════════

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
            # Sürükleme başladı — o an gitmekte olduğu gezinme hedefini iptal et
            self._wander_target = None

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self._drag_moved = True
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and not self._drag_moved:
            self._toggle_chat()
        elif event.button() == Qt.LeftButton and self._drag_moved:
            # Bırakılan yer yeni yuva olur, gezinme buradan devam eder
            self._anchor = self.pos()
            self._schedule_next_move()
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

        x = btn.x() - chat_w + self.width()
        x = max(0, min(x, screen.width() - chat_w))

        if btn.y() - chat_h - 10 >= screen.top():
            y = btn.y() - chat_h - 10
        else:
            y = btn.y() + btn.height() + 10

        y = max(screen.top(), min(y, screen.bottom() - chat_h))

        self._chat.move(x, y)
        self._chat.show()

        if self._on_chat_opened:
            self._on_chat_opened()


class ThoughtBubble(QWidget):
    """
    Sohbet penceresi kapalıyken, pet'in yanında beliren küçük durum balonu.

    NEDEN GEREKLİ:
      Kullanıcı bir istek gönderip sohbet penceresini kapatırsa, arka
      planda cevap üretilmeye devam eder ama kullanıcı bunu göremez.
      Bu balon, pet'in yanında "Düşünüyor...", "Klasör açılıyor..." gibi
      anlık durumları gösterir; cevap gelince onu kısaca gösterip
      kendiliğinden kaybolur.

    NASIL ÇALIŞIR:
      show_status()/show_final() her çağrıldığında, balon pet'in O ANKİ
      konumuna göre yeniden konumlanır (pet dolaştığı için sabit bir
      yer kullanamayız).
    """

    AUTO_HIDE_MS = 8000
    MAX_WIDTH = 330

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._anchor = None
        self._expanded = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._card = QWidget()
        self._card.setFixedWidth(self.MAX_WIDTH)
        self._card.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 30, 242);
                border: 1px solid #474747;
                border-radius: 18px;
            }
        """)
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(18, 11, 18, 11)
        card_layout.setSpacing(2)

        self._title = QLabel("Heko çalışıyor")
        self._title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self._title.setStyleSheet("color: #f3f3f3; border: none; background: transparent;")

        self._subtitle = QLabel("")
        self._subtitle.setWordWrap(False)
        self._subtitle.setFont(QFont("Segoe UI", 9))
        self._subtitle.setStyleSheet("color: #858585; border: none; background: transparent;")
        card_layout.addWidget(self._title)
        card_layout.addWidget(self._subtitle)
        layout.addWidget(self._card)

        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        self._toggle_btn = QPushButton("⌄")
        self._toggle_btn.setFixedSize(30, 30)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.setStyleSheet("""
            QPushButton {
                color: #f2f2f2; background: #1d1d1d;
                border: 1px solid #555555; border-radius: 15px;
                font-size: 17px; padding-bottom: 5px;
            }
            QPushButton:hover { background: #2b2b2b; border-color: #777777; }
        """)
        self._toggle_btn.clicked.connect(self._toggle_expanded)
        toggle_row.addStretch()
        toggle_row.addWidget(self._toggle_btn)
        toggle_row.addStretch()
        layout.addLayout(toggle_row)

        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self._follow_timer = QTimer()
        self._follow_timer.setInterval(30)
        self._follow_timer.timeout.connect(self._follow_anchor)

    def _toggle_expanded(self):
        self._expanded = not self._expanded
        self._card.setVisible(self._expanded)
        self._toggle_btn.setText("⌄" if self._expanded else "⌃")
        self.adjustSize()
        self._follow_anchor()

    def _set_content(self, anchor: QWidget, title: str, text: str):
        self._anchor = anchor
        clean_title = " ".join(title.split())
        clean_text = " ".join(text.split())
        self._title.setText(
            clean_title if len(clean_title) <= 42 else clean_title[:39] + "..."
        )
        self._subtitle.setText(
            clean_text if len(clean_text) <= 58 else clean_text[:55] + "..."
        )
        self._expanded = True
        self._card.show()
        self._toggle_btn.setText("⌄")
        self.adjustSize()
        self._position_near(anchor)
        self.show()
        self._follow_timer.start()

    def show_status(self, anchor: QWidget, text: str, title: str = "Heko çalışıyor"):
        """Anlık durum göster — cevap gelene kadar açık kalır."""
        self._hide_timer.stop()
        self._set_content(anchor, title, text)

    def show_final(self, anchor: QWidget, text: str, title: str = "İşlem tamamlandı"):
        """Nihai cevabın kısa bir önizlemesini göster, birkaç saniye sonra kaybol."""
        preview = text if len(text) <= 160 else text[:157] + "..."
        self._set_content(anchor, title, preview)
        self._hide_timer.start(self.AUTO_HIDE_MS)

    def hideEvent(self, event):
        self._follow_timer.stop()
        super().hideEvent(event)

    def _follow_anchor(self):
        if self._anchor and self.isVisible():
            self._position_near(self._anchor)

    def _position_near(self, anchor: QWidget):
        """Balonu pet'in üstüne, ekran dışına taşmayacak şekilde yerleştirir."""
        anchor_pos = anchor.frameGeometry().topLeft()
        screen = QApplication.primaryScreen().availableGeometry()

        x = anchor_pos.x() + (anchor.width() - self.width()) // 2
        y = anchor_pos.y() - self.height() - 8

        x = max(screen.left(), min(x, screen.right() - self.width()))

        if y < screen.top():
            # Üstte yer yoksa altına koy
            y = anchor_pos.y() + anchor.height() + 8

        self.move(int(x), int(y))


def main():
    configure_logging()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    shared_state = SharedAssistantState()
    session_registry = SessionRegistry()
    windows = {}

    def _session_index(session_id):
        try:
            return int(session_id.split("-")[-1])
        except (TypeError, ValueError):
            return 9999

    def _known_session_ids():
        ids = set(windows)
        session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory", "sessions")
        if os.path.isdir(session_dir):
            for name in os.listdir(session_dir):
                if name.startswith("chat-") and name.endswith(".json"):
                    ids.add(name[:-5])
        return sorted(ids, key=_session_index)

    def _session_rows():
        rows = []
        for session_id in _known_session_ids():
            window = windows.get(session_id)
            index = _session_index(session_id)
            rows.append({
                "id": session_id,
                "name": session_registry.name_for(session_id, f"Sohbet {index}"),
                "visible": bool(window and window.isVisible()),
            })
        return rows

    def _create_chat_window(session_id=None):
        if session_id and session_id in windows:
            return windows[session_id]
        used = {_session_index(value) for value in _known_session_ids()}
        index = _session_index(session_id) if session_id else next(
            value for value in range(1, 1000) if value not in used
        )
        session_id = session_id or f"chat-{index}"
        chat_window = ChatWindow(
            shared_state=shared_state,
            session_id=session_id,
            display_name=session_registry.name_for(session_id, f"Sohbet {index}"),
        )
        windows[session_id] = chat_window
        chat_window.new_window_requested.connect(_show_new_chat)
        chat_window.sessions_requested.connect(_show_session_manager)
        return chat_window

    def _show_new_chat():
        new_chat = _create_chat_window()
        screen = QApplication.primaryScreen().availableGeometry()
        offset = 36 * (len(windows) - 1)
        new_chat.move(
            min(screen.right() - new_chat.width(), screen.left() + 80 + offset),
            min(screen.bottom() - new_chat.height(), screen.top() + 60 + offset),
        )
        new_chat.show()

    def _show_session(session_id):
        target = _create_chat_window(session_id)
        target.show()
        target.raise_()
        target.activateWindow()

    def _hide_session(session_id):
        target = windows.get(session_id)
        if target:
            target.hide()

    def _rename_session(session_id, name):
        clean = session_registry.rename(session_id, name)
        target = windows.get(session_id)
        if target:
            target.set_display_name(clean)

    session_manager = SessionManagerWindow(
        _session_rows,
        _show_session,
        _hide_session,
        _show_new_chat,
        _rename_session,
    )

    def _show_session_manager():
        screen = QApplication.primaryScreen().availableGeometry()
        session_manager.move(
            screen.center().x() - session_manager.width() // 2,
            screen.center().y() - session_manager.height() // 2,
        )
        session_manager.show()

    chat = _create_chat_window("chat-1")
    button = FloatingButton(chat)
    bubble = ThoughtBubble()

    def _current_task_title() -> str:
        for item in reversed(chat.router.get_history(limit=6)):
            if item.get("role") == "user":
                return item.get("content", "Heko çalışıyor")
        return "Heko çalışıyor"

    def _handle_status(text: str):
        button.set_pet_state("busy")
        if not chat.isVisible():
            bubble.show_status(button, text, _current_task_title())

    def _handle_final(response: str):
        button.start_flash()
        button.set_pet_state("alert", reset_after_ms=3500)
        if not chat.isVisible():
            bubble.show_final(button, response, _current_task_title())

    chat._on_status_callback = _handle_status
    chat._on_response_callback = _handle_final
    button._on_chat_opened = bubble.hide

    def _check_due_reminders():
        for reminder in chat.router.reminders.pop_due():
            message = f"⏰ Hatırlatma: {reminder['text']}"
            chat.router.context.add_message("assistant", message)
            chat._add_message(message, is_user=False)
            button.start_flash()
            button.set_pet_state("alert", reset_after_ms=5000)
            QApplication.beep()
            if not chat.isVisible():
                bubble.show_final(button, message, "Hatırlatıcı")

    reminder_timer = QTimer()
    reminder_timer.setInterval(1000)
    reminder_timer.timeout.connect(_check_due_reminders)
    reminder_timer.start()

    button.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
