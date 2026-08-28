import sys
import os
import math
import random

if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

import keyboard
from PySide6.QtWidgets import (
    QApplication, QWidget, QMenu, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PySide6.QtCore import QTimer, Qt, Signal, QObject, QPoint, QRect
from PySide6.QtGui import QPainter, QColor, QFont, QPixmap, QPen
from ui.chat_window import ChatWindow
from services.error_logger import configure_logging
from core.shared_state import SharedAssistantState
from ui.session_manager_window import SessionManagerWindow
from services.session_registry import SessionRegistry
from services.speech_output import SpeechOutputManager
from ui.pet_state import normalize_pet_state, pet_sprite_frame, resting_state
import utils.config as config
from utils.app_info import APP_DISPLAY_NAME, APP_VERSION, ORGANIZATION_NAME


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
        self._state_started_frame = 0
        self._state_reset_target = "idle"
        self._state_timer = QTimer()
        self._state_timer.setSingleShot(True)
        self._state_timer.timeout.connect(self._restore_timed_state)
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

    def set_pet_state(
        self, state: str, reset_after_ms: int = 0, reset_state: str = "idle"
    ):
        """Karakter durumunu değiştirir ve istenirse güvenli duruma geri döner."""
        self._pet_state = normalize_pet_state(state)
        self._state_started_frame = self._anim_frame
        self._state_reset_target = normalize_pet_state(reset_state)
        self._state_timer.stop()
        if reset_after_ms:
            self._state_timer.start(reset_after_ms)
        state_labels = {
            "idle": "Heko hazır",
            "busy": "Heko çalışıyor",
            "success": "İşlem tamamlandı",
            "alert": "Heko dikkatini istiyor",
            "listening": "Heko dinliyor",
            "speaking": "Heko konuşuyor",
            "sleeping": "Heko çevrimdışı",
        }
        self.setToolTip(state_labels[self._pet_state] + " — Sağ tık: Kapat")
        self.update()

    def _restore_timed_state(self):
        self.set_pet_state(self._state_reset_target)

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
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)

        if self._sprite.isNull():
            painter.setPen(QColor("#f0c995"))
            painter.drawText(self.rect(), Qt.AlignCenter, "AI")
            return

        # Durum efekti sprite'ın arkasında kalır; karakterin piksel dili bozulmaz.
        phase = max(0, self._anim_frame - self._state_started_frame)
        center_x = self.width() // 2
        center_y = self.height() // 2
        if self._pet_state == "busy":
            arc_rect = QRect(10, 5, self.width() - 20, self.height() - 14)
            painter.setPen(QPen(QColor(144, 91, 255, 155), 2))
            painter.drawArc(arc_rect, int((-phase * 7) % 360) * 16, 105 * 16)
            for offset in (0, 120, 240):
                angle = math.radians((phase * 4 + offset) % 360)
                x = center_x + int(math.cos(angle) * 51)
                y = center_y + int(math.sin(angle) * 43)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(63, 210, 255, 190))
                painter.drawEllipse(x - 2, y - 2, 4, 4)
        elif self._pet_state == "listening":
            for index in range(3):
                progress = ((phase * 0.035) + index / 3) % 1.0
                radius_x = 24 + int(progress * 34)
                radius_y = 19 + int(progress * 27)
                alpha = max(0, int(135 * (1.0 - progress)))
                painter.setPen(QPen(QColor(45, 214, 255, alpha), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(
                    center_x - radius_x,
                    center_y - radius_y,
                    radius_x * 2,
                    radius_y * 2,
                )
        elif self._pet_state == "speaking":
            for index in range(3):
                progress = ((phase * 0.045) + index / 3) % 1.0
                width = 12 + int(progress * 30)
                height = 18 + int(progress * 24)
                alpha = max(0, int(175 * (1.0 - progress)))
                painter.setPen(QPen(QColor(197, 103, 255, alpha), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawArc(
                    QRect(center_x + 4, center_y - height // 2, width, height),
                    -70 * 16,
                    140 * 16,
                )
        elif self._pet_state == "success":
            glow = 80 + int(35 * (1 + math.sin(phase * 0.24)))
            painter.setPen(QPen(QColor(83, 230, 164, glow), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(12, 7, self.width() - 24, self.height() - 18)
            for x, y in ((19, 20), (106, 25), (24, 89), (102, 85)):
                size = 2 + ((phase // 4 + x) % 3)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(106, 255, 204, 190))
                painter.drawEllipse(x - size, y - size, size * 2, size * 2)
        elif self._pet_state == "alert":
            pulse = 55 + int(60 * (1 + math.sin(phase * 0.32)) / 2)
            painter.setPen(QPen(QColor(255, 58, 149, pulse), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(9, 4, self.width() - 18, self.height() - 12)
        elif self._pet_state == "sleeping":
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            for index, (x, y) in enumerate(((91, 28), (102, 18), (112, 8))):
                alpha = 80 + ((phase * 3 + index * 45) % 120)
                painter.setPen(QColor(172, 137, 255, alpha))
                painter.drawText(x, y, "z")

        # Yatay sprite şeridi: idle, blink, busy, alert.
        frame_w = self._sprite.width() // 4
        frame_h = self._sprite.height()
        frame_index = pet_sprite_frame(
            self._pet_state,
            blinking=self._blinking,
        )
        source = QRect(frame_index * frame_w, 0, frame_w, frame_h)

        speeds = {
            "busy": 0.22,
            "listening": 0.17,
            "speaking": 0.19,
            "sleeping": 0.06,
        }
        bounce = int(2 * math.sin(self._anim_frame * speeds.get(self._pet_state, 0.12)))
        inset = 5 if self._pet_state == "success" else 3
        target = QRect(inset, 2 + bounce, self.width() - inset * 2, self.height() - 6)

        painter.save()
        if self._pet_state == "sleeping":
            painter.setOpacity(0.62)
        if self._facing_left:
            painter.translate(self.width(), 0)
            painter.scale(-1, 1)
        painter.drawPixmap(target, self._sprite, source)
        painter.restore()
        if self._pet_state == "speaking":
            # Konuşma göstergesi sprite'ın sağında önde kalır; koyu arka planda
            # kaybolmaması için yalnızca bu küçük dalga üst katmanda çizilir.
            painter.setPen(QPen(QColor(221, 109, 255, 225), 3))
            for index, x in enumerate((101, 109, 117)):
                amplitude = 5 + int(
                    5 * abs(math.sin((phase + index * 4) * 0.22))
                )
                painter.drawLine(x, center_y - amplitude, x, center_y + amplitude)

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
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORGANIZATION_NAME)
    app.setQuitOnLastWindowClosed(False)

    shared_state = SharedAssistantState()
    speech = SpeechOutputManager(
        auto_speak=getattr(config, "TTS_AUTO_SPEAK", False),
        voice_id=getattr(config, "TTS_VOICE_ID", ""),
        rate=getattr(config, "TTS_RATE", 0.0),
        volume=getattr(config, "TTS_VOLUME", 0.85),
    )
    session_registry = SessionRegistry()
    windows = {}
    pet_feedback = {"wire": None}

    def _session_index(session_id):
        try:
            return int(session_id.split("-")[-1])
        except (TypeError, ValueError):
            return 9999

    def _known_session_ids():
        ids = set(windows)
        session_dir = os.path.join(config.MEMORY_DIR, "sessions")
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
            speech_manager=speech,
        )
        windows[session_id] = chat_window
        chat_window.new_window_requested.connect(_show_new_chat)
        chat_window.sessions_requested.connect(_show_session_manager)
        if pet_feedback["wire"]:
            pet_feedback["wire"](chat_window)
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

    active_sessions = set()

    def _current_task_title(target_chat: ChatWindow) -> str:
        for item in reversed(target_chat.router.get_history(limit=6)):
            if item.get("role") == "user":
                return item.get("content", "Heko çalışıyor")
        return "Heko çalışıyor"

    def _rest_state() -> str:
        return resting_state(bool(active_sessions))

    def _handle_activity(target_chat: ChatWindow, active: bool):
        if active:
            active_sessions.add(target_chat.session_id)
            button.set_pet_state("busy")
        else:
            active_sessions.discard(target_chat.session_id)
            if button._pet_state == "busy":
                button.set_pet_state(_rest_state())

    def _handle_status(target_chat: ChatWindow, text: str):
        active_sessions.add(target_chat.session_id)
        button.set_pet_state("busy")
        if not target_chat.isVisible():
            bubble.show_status(button, text, _current_task_title(target_chat))

    def _handle_final(target_chat: ChatWindow, response: str):
        button.start_flash()
        button.set_pet_state(
            "success", reset_after_ms=2600, reset_state=_rest_state()
        )
        if not target_chat.isVisible():
            bubble.show_final(
                button, response, _current_task_title(target_chat)
            )

    def _handle_error(target_chat: ChatWindow, error: str):
        button.set_pet_state(
            "alert", reset_after_ms=4200, reset_state=_rest_state()
        )
        if not target_chat.isVisible():
            bubble.show_final(button, f"İşlem tamamlanamadı: {error}", "Hata")

    def _handle_presence(state: str):
        if active_sessions and state in {"idle", "sleeping"}:
            button.set_pet_state("busy")
            return
        reset_ms = 2200 if state == "alert" else 0
        button.set_pet_state(state, reset_ms, _rest_state())

    def _handle_speech_state(state: str):
        if state == "speaking":
            button.set_pet_state("speaking")
        elif state == "error":
            button.set_pet_state(
                "alert", reset_after_ms=2600, reset_state=_rest_state()
            )
        elif state == "ready" and button._pet_state == "speaking":
            button.set_pet_state(_rest_state())

    def _wire_chat_feedback(target_chat: ChatWindow):
        target_chat._on_activity_callback = (
            lambda active, window=target_chat: _handle_activity(window, active)
        )
        target_chat._on_status_callback = (
            lambda text, window=target_chat: _handle_status(window, text)
        )
        target_chat._on_response_callback = (
            lambda response, window=target_chat: _handle_final(window, response)
        )
        target_chat._on_error_callback = (
            lambda error, window=target_chat: _handle_error(window, error)
        )
        target_chat._on_presence_callback = _handle_presence

    pet_feedback["wire"] = _wire_chat_feedback
    for open_chat in windows.values():
        _wire_chat_feedback(open_chat)
    speech.state_changed.connect(_handle_speech_state)
    button._on_chat_opened = bubble.hide

    def _check_due_reminders():
        for reminder in chat.router.reminders.pop_due():
            message = f"⏰ Hatırlatma: {reminder['text']}"
            chat.router.context.add_message("assistant", message)
            chat._add_message(message, is_user=False)
            button.start_flash()
            button.set_pet_state(
                "alert", reset_after_ms=5000, reset_state=_rest_state()
            )
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
