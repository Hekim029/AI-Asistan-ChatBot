from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QApplication, QTabWidget, QCheckBox, QMessageBox,
    QComboBox, QSlider,
)
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QFont, QPainter, QColor, QPainterPath
import utils.config as config
from utils.startup import enable_startup, disable_startup, is_startup_enabled
from ui.memory_window import MemoryWindow
from ui.diagnostics_window import DiagnosticsWindow
from ui.organizer_window import OrganizerWindow
from ui.daily_settings_window import DailySettingsWindow
from ui.local_model_settings_window import LocalModelSettingsWindow
from services.app_settings import save_app_settings
from utils.app_info import APP_VERSION

COLOR_PAIRS = [
    ("#4a9eff", "#1e242c", "Okyanus"),
    ("#9b59b6", "#2d1b4e", "Gece"),
    ("#3fb950", "#1a3d20", "Orman"),
    ("#f0883e", "#4a2a0e", "Gün Batimi"),
    ("#e74c3c", "#4a1010", "Kirmizi"),
    ("#ff6eb4", "#4a1a35", "Pembe"),
    ("#00d4ff", "#003a4a", "Buz"),
]

class SplitColorButton(QWidget):
    pair_selected = Signal(str, str)

    def __init__(self, user_color: str, ai_color: str, name: str):
        super().__init__()
        self.user_color = user_color
        self.ai_color = ai_color
        self.name = name
        self.is_selected = False
        self.setFixedSize(38, 38)
        self.setToolTip(name)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        left_path = QPainterPath()
        left_path.moveTo(19, 3)
        left_path.arcTo(3, 3, 32, 32, 90, 180)
        left_path.closeSubpath()
        painter.fillPath(left_path, QColor(self.user_color))
        right_path = QPainterPath()
        right_path.moveTo(19, 3)
        right_path.arcTo(3, 3, 32, 32, 90, -180)
        right_path.closeSubpath()
        painter.fillPath(right_path, QColor(self.ai_color))
        painter.setPen(QColor("#161b22"))
        painter.drawLine(19, 3, 19, 35)
        if self.is_selected:
            painter.setPen(QColor("#ffffff"))
        else:
            painter.setPen(QColor("#30363d"))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QRectF(2, 2, 34, 34))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pair_selected.emit(self.user_color, self.ai_color)

class SettingsWindow(QWidget):

    saved = Signal()

    def __init__(
        self,
        user_memory=None,
        task_manager=None,
        reminder_manager=None,
        daily_briefing_service=None,
        shared_workspace=None,
        llm_client=None,
        speech_manager=None,
    ):
        super().__init__()
        self._drag_pos = None
        self._memory_window = (
            MemoryWindow(user_memory) if user_memory is not None else None
        )
        self._diagnostics_window = DiagnosticsWindow()
        self._organizer_window = (
            OrganizerWindow(task_manager, reminder_manager, shared_workspace)
            if task_manager is not None and reminder_manager is not None
            else None
        )
        self._daily_settings_window = (
            DailySettingsWindow(daily_briefing_service)
            if daily_briefing_service is not None else None
        )
        self._local_model_window = LocalModelSettingsWindow(llm_client)
        self._speech = speech_manager
        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        self.setFixedSize(560, 620)
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
        layout.addLayout(self._build_content())

    def _build_header(self):
        header = QWidget()
        header.setFixedHeight(54)
        header.setStyleSheet("background-color: #0d1117; border-radius: 12px;")
        h = QHBoxLayout(header)
        h.setContentsMargins(16, 0, 16, 0)
        title = QLabel(f"⚙  Heko Ayarları  ·  v{APP_VERSION}")
        title.setFont(QFont("Segoe UI", 11, QFont.Bold))
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

    def _select_mode(self, mode_name: str):
        for name, btn in self._mode_buttons.items():
            btn.setChecked(name == mode_name)
        self._prompt_edit.setPlainText(config.MODES[mode_name])

    def _build_content(self):
        content = QVBoxLayout()
        content.setContentsMargins(18, 14, 18, 18)
        content.setSpacing(12)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.tabBar().setExpanding(True)
        tabs.tabBar().setUsesScrollButtons(False)
        tabs.setStyleSheet("""
            QTabWidget::pane {
                background:#161b22; border:1px solid #30363d;
                border-radius:10px; top:-1px;
            }
            QTabBar::tab {
                background:#0d1117; color:#8b949e; border:none;
                border-bottom:2px solid transparent; padding:10px 22px;
            }
            QTabBar::tab:selected { color:#e6edf3; border-bottom-color:#4a9eff; }
            QTabBar::tab:hover { color:#c9d1d9; }
        """)

        assistant_page = QWidget()
        assistant_layout = QVBoxLayout(assistant_page)
        assistant_layout.setContentsMargins(18, 18, 18, 18)
        assistant_layout.setSpacing(12)

        mode_label = QLabel("Konuşma modu")
        mode_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        mode_label.setStyleSheet("color:#c9d1d9;")
        mode_help = QLabel("Hazır bir kişilik seç veya aşağıdaki metni kendine göre düzenle.")
        mode_help.setStyleSheet("color:#6e7681;font-size:9px;")

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(8)
        self._mode_buttons = {}

        for mode_name in config.MODES.keys():
            btn = QPushButton(mode_name.capitalize())
            btn.setCheckable(True)
            btn.setFixedHeight(34)
            btn.setFont(QFont("Segoe UI", 8, QFont.Bold))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0d1117; color: #8b949e;
                    border: 1px solid #30363d; border-radius: 8px; padding: 0px 10px;
                }
                QPushButton:checked { background-color: #1f4f8f; color: #e6edf3; border: 1px solid #4a9eff; }
                QPushButton:hover { border: 1px solid #4a9eff; }
            """)
            btn.clicked.connect(lambda checked, m=mode_name: self._select_mode(m))
            mode_layout.addWidget(btn)
            self._mode_buttons[mode_name] = btn

        active_mode = getattr(config, "CURRENT_MODE", "normal")
        self._mode_buttons.get(active_mode, self._mode_buttons["normal"]).setChecked(True)

        prompt_label = QLabel("Asistan kişiliği")
        prompt_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        prompt_label.setStyleSheet("color:#c9d1d9;")

        self._prompt_edit = QTextEdit()
        self._prompt_edit.setPlainText(config.SYSTEM_PROMPT)
        self._prompt_edit.setFont(QFont("Segoe UI", 9))
        self._prompt_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117; color: #e6edf3;
                border: 1px solid #30363d; border-radius: 8px; padding: 8px;
            }
            QTextEdit:focus { border: 1px solid #4a9eff; }
        """)
        self._prompt_edit.setMinimumHeight(245)

        assistant_layout.addWidget(mode_label)
        assistant_layout.addWidget(mode_help)
        assistant_layout.addLayout(mode_layout)
        assistant_layout.addSpacing(4)
        assistant_layout.addWidget(prompt_label)
        assistant_layout.addWidget(self._prompt_edit, 1)

        appearance_page = QWidget()
        appearance_layout = QVBoxLayout(appearance_page)
        appearance_layout.setContentsMargins(18, 18, 18, 18)
        appearance_layout.setSpacing(14)
        color_label = QLabel("Mesaj renkleri")
        color_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        color_label.setStyleSheet("color:#c9d1d9;")
        color_help = QLabel(
            "Her dairenin sol yarısı senin, sağ yarısı Heko'nun mesaj rengini gösterir."
        )
        color_help.setWordWrap(True)
        color_help.setStyleSheet("color:#6e7681;font-size:9px;")

        color_layout = QHBoxLayout()
        color_layout.setSpacing(14)
        self._split_buttons = []
        for user_color, ai_color, name in COLOR_PAIRS:
            btn = SplitColorButton(user_color, ai_color, name)
            btn.pair_selected.connect(self._select_pair)
            color_layout.addWidget(btn)
            self._split_buttons.append(btn)
        color_layout.addStretch()

        preview = QLabel(
            "Tema değişikliği kaydedildiğinde açık sohbet penceresine hemen uygulanır."
        )
        preview.setWordWrap(True)
        preview.setStyleSheet(
            "background:#0d1117;color:#8b949e;border:1px solid #30363d;"
            "border-radius:9px;padding:14px;"
        )
        appearance_layout.addWidget(color_label)
        appearance_layout.addWidget(color_help)
        appearance_layout.addLayout(color_layout)
        appearance_layout.addWidget(preview)
        appearance_layout.addStretch()

        voice_page = QWidget()
        voice_layout = QVBoxLayout(voice_page)
        voice_layout.setContentsMargins(18, 18, 18, 18)
        voice_layout.setSpacing(12)

        voice_title = QLabel("Sesli yanıt")
        voice_title.setFont(QFont("Segoe UI", 10, QFont.Bold))
        voice_title.setStyleSheet("color:#e6edf3;")
        voice_intro = QLabel(
            "Heko, Windows'un yerel konuşma motorunu kullanır; metin bir ses "
            "API'sine gönderilmez. Yeni okuma önceki sesi keser."
        )
        voice_intro.setWordWrap(True)
        voice_intro.setStyleSheet("color:#8b949e;font-size:9px;")

        voice_status = self._speech.status() if self._speech else {
            "available": False,
            "message": "Ses yöneticisi bağlı değil.",
        }
        self._voice_status_label = QLabel(voice_status["message"])
        self._voice_status_label.setWordWrap(True)
        self._voice_status_label.setStyleSheet(
            "background:#0d1117;color:"
            + (
                "#3fb950"
                if voice_status.get("turkish_available") else "#e3b341"
            )
            + ";border:1px solid #30363d;border-radius:8px;padding:10px;"
        )

        self._tts_auto_checkbox = QCheckBox("Heko yanıtlarını otomatik seslendir")
        self._tts_auto_checkbox.setChecked(
            bool(getattr(config, "TTS_AUTO_SPEAK", False))
        )
        if not voice_status["available"]:
            self._tts_auto_checkbox.setChecked(False)
            self._tts_auto_checkbox.setEnabled(False)
        self._tts_auto_checkbox.setStyleSheet(
            self._screen_vision_checkbox.styleSheet()
            if hasattr(self, "_screen_vision_checkbox") else
            "QCheckBox{color:#e6edf3;}"
        )

        voice_select_label = QLabel("Windows sesi")
        voice_select_label.setStyleSheet("color:#c9d1d9;font-weight:600;")
        self._voice_combo = QComboBox()
        self._voice_combo.setFixedHeight(36)
        self._voice_combo.setStyleSheet("""
            QComboBox {
                background:#0d1117;color:#e6edf3;border:1px solid #30363d;
                border-radius:8px;padding:0 10px;
            }
            QComboBox:focus { border-color:#4a9eff; }
            QComboBox QAbstractItemView {
                background:#161b22;color:#e6edf3;selection-background-color:#1f4f8f;
            }
        """)
        voice_options = self._speech.voice_options() if self._speech else []
        selected_voice = getattr(config, "TTS_VOICE_ID", "")
        for row in voice_options:
            label = f"{row['name']} — {row['locale']} ({row['gender']})"
            self._voice_combo.addItem(label, row["id"])
        if not voice_options:
            self._voice_combo.addItem("Windows konuşma sesi bulunamadı", "")
            self._voice_combo.setEnabled(False)
        else:
            index = self._voice_combo.findData(selected_voice)
            self._voice_combo.setCurrentIndex(index if index >= 0 else 0)

        self._rate_value = QLabel()
        self._rate_value.setStyleSheet("color:#8b949e;")
        rate_row = QHBoxLayout()
        rate_label = QLabel("Konuşma hızı")
        rate_label.setStyleSheet("color:#c9d1d9;")
        self._rate_slider = QSlider(Qt.Horizontal)
        self._rate_slider.setRange(-10, 10)
        self._rate_slider.setValue(round(getattr(config, "TTS_RATE", 0.0) * 10))
        self._rate_slider.valueChanged.connect(self._update_voice_value_labels)
        rate_row.addWidget(rate_label)
        rate_row.addWidget(self._rate_slider, 1)
        rate_row.addWidget(self._rate_value)

        self._volume_value = QLabel()
        self._volume_value.setStyleSheet("color:#8b949e;")
        volume_row = QHBoxLayout()
        volume_label = QLabel("Ses seviyesi")
        volume_label.setStyleSheet("color:#c9d1d9;")
        self._volume_slider = QSlider(Qt.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(round(getattr(config, "TTS_VOLUME", 0.85) * 100))
        self._volume_slider.valueChanged.connect(self._update_voice_value_labels)
        volume_row.addWidget(volume_label)
        volume_row.addWidget(self._volume_slider, 1)
        volume_row.addWidget(self._volume_value)
        self._update_voice_value_labels()

        voice_buttons = QHBoxLayout()
        test_voice_btn = QPushButton("▶  Sesi dene")
        stop_voice_btn = QPushButton("■  Durdur")
        for button in (test_voice_btn, stop_voice_btn):
            button.setFixedHeight(36)
            button.setStyleSheet("""
                QPushButton {
                    background:#0d1117;color:#c9d1d9;border:1px solid #30363d;
                    border-radius:8px;
                }
                QPushButton:hover { border-color:#4a9eff;color:white; }
            """)
        test_voice_btn.setEnabled(bool(self._speech and voice_options))
        stop_voice_btn.setEnabled(bool(self._speech))
        test_voice_btn.clicked.connect(self._test_voice)
        stop_voice_btn.clicked.connect(
            lambda: self._speech.stop() if self._speech else None
        )
        voice_buttons.addWidget(test_voice_btn)
        voice_buttons.addWidget(stop_voice_btn)

        install_help = QLabel(
            "Ses bulunamazsa Windows Ayarları > Saat ve dil > Konuşma bölümünden "
            "Türkçe bir ses paketi ekleyip Heko'yu yeniden başlat."
        )
        install_help.setWordWrap(True)
        install_help.setStyleSheet("color:#6e7681;font-size:8px;")

        voice_layout.addWidget(voice_title)
        voice_layout.addWidget(voice_intro)
        voice_layout.addWidget(self._voice_status_label)
        voice_layout.addWidget(self._tts_auto_checkbox)
        voice_layout.addWidget(voice_select_label)
        voice_layout.addWidget(self._voice_combo)
        voice_layout.addLayout(rate_row)
        voice_layout.addLayout(volume_row)
        voice_layout.addLayout(voice_buttons)
        voice_layout.addWidget(install_help)
        voice_layout.addStretch()

        system_page = QWidget()
        system_layout = QVBoxLayout(system_page)
        system_layout.setContentsMargins(18, 18, 18, 18)
        system_layout.setSpacing(12)

        startup_label = QLabel("Windows başlangıcı")
        startup_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        startup_label.setStyleSheet("color:#c9d1d9;")

        startup_row = QHBoxLayout()
        startup_desc = QLabel("Bilgisayar açıldığında Heko'yu otomatik çalıştır")
        startup_desc.setFont(QFont("Segoe UI", 8))
        startup_desc.setStyleSheet("color: #8b949e;")

        self._startup_btn = QPushButton()
        self._startup_btn.setFixedSize(80, 28)
        self._startup_btn.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self._startup_enabled = is_startup_enabled()
        self._update_startup_btn()
        self._startup_btn.clicked.connect(self._toggle_startup)

        startup_row.addWidget(startup_desc)
        startup_row.addStretch()
        startup_row.addWidget(self._startup_btn)

        privacy_label = QLabel("Gizlilik ve deneysel özellikler")
        privacy_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        privacy_label.setStyleSheet("color:#c9d1d9;")

        vision_card = QWidget()
        vision_card.setStyleSheet(
            "background:#0d1117;border:1px solid #30363d;border-radius:8px;"
        )
        vision_layout = QVBoxLayout(vision_card)
        vision_layout.setContentsMargins(12, 9, 12, 9)
        vision_layout.setSpacing(3)
        self._screen_vision_checkbox = QCheckBox("Deneysel ekran farkındalığı")
        self._screen_vision_checkbox.setChecked(
            bool(getattr(config, "SCREEN_VISION_ENABLED", False))
        )
        self._screen_vision_checkbox.setStyleSheet("""
            QCheckBox { color:#e6edf3;border:none;font-weight:600; }
            QCheckBox::indicator {
                width:16px;height:16px;border:1px solid #484f58;
                border-radius:4px;background:#161b22;
            }
            QCheckBox::indicator:checked {
                background:#1f6feb;border-color:#4a9eff;
            }
        """)
        vision_help = QLabel(
            "Varsayılan olarak kapalıdır. Açık olsa bile yalnızca komutundan "
            "ve ayrıca verdiğin onaydan sonra tek kare Groq'a gönderilir."
        )
        vision_help.setWordWrap(True)
        vision_help.setStyleSheet("color:#8b949e;border:none;font-size:8px;")
        vision_layout.addWidget(self._screen_vision_checkbox)
        vision_layout.addWidget(vision_help)

        memory_btn = QPushButton("Hafıza")
        memory_btn.setFixedHeight(42)
        memory_btn.setEnabled(self._memory_window is not None)
        memory_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d1117; color: #c9d1d9;
                border: 1px solid #30363d; border-radius: 8px;
            }
            QPushButton:hover { border-color: #4a9eff; color: #ffffff; }
        """)
        if self._memory_window is not None:
            memory_btn.clicked.connect(self._open_memory)

        diagnostics_btn = QPushButton("Sistem Kontrolü")
        diagnostics_btn.setFixedHeight(42)
        diagnostics_btn.setStyleSheet(memory_btn.styleSheet())
        diagnostics_btn.clicked.connect(self._open_diagnostics)

        organizer_btn = QPushButton("Kontrol Merkezi")
        organizer_btn.setFixedHeight(42)
        organizer_btn.setEnabled(self._organizer_window is not None)
        organizer_btn.setStyleSheet(memory_btn.styleSheet())
        if self._organizer_window is not None:
            organizer_btn.clicked.connect(self._open_organizer)

        daily_btn = QPushButton("Günlük Özet")
        daily_btn.setFixedHeight(42)
        daily_btn.setEnabled(self._daily_settings_window is not None)
        daily_btn.setStyleSheet(memory_btn.styleSheet())
        if self._daily_settings_window is not None:
            daily_btn.clicked.connect(self._open_daily_settings)

        local_model_btn = QPushButton("Yerel Model (Ollama)")
        local_model_btn.setFixedHeight(42)
        local_model_btn.setStyleSheet(memory_btn.styleSheet())
        local_model_btn.clicked.connect(self._open_local_model_settings)

        save_btn = QPushButton("💾  Kaydet")
        save_btn.setFixedHeight(42)
        save_btn.setFont(QFont("Segoe UI", 9, QFont.Bold))
        save_btn.setStyleSheet("""
            QPushButton { background-color: #1f4f8f; color: #e6edf3; border: none; border-radius: 8px; }
            QPushButton:hover { background-color: #4a9eff; }
        """)
        save_btn.clicked.connect(self._save)

        system_layout.addWidget(startup_label)
        system_layout.addLayout(startup_row)
        system_layout.addSpacing(8)
        system_layout.addWidget(privacy_label)
        system_layout.addWidget(vision_card)
        system_layout.addSpacing(4)
        tools_label = QLabel("Heko araçları")
        tools_label.setFont(QFont("Segoe UI", 9, QFont.Bold))
        tools_label.setStyleSheet("color:#c9d1d9;")
        system_layout.addWidget(tools_label)
        utility_row = QHBoxLayout()
        utility_row.setSpacing(8)
        utility_row.addWidget(memory_btn)
        utility_row.addWidget(diagnostics_btn)
        organizer_row = QHBoxLayout()
        organizer_row.setSpacing(8)
        organizer_row.addWidget(organizer_btn)
        organizer_row.addWidget(daily_btn)
        system_layout.addLayout(utility_row)
        system_layout.addLayout(organizer_row)
        system_layout.addWidget(local_model_btn)
        system_layout.addStretch()

        tabs.addTab(assistant_page, "Asistan")
        tabs.addTab(appearance_page, "Görünüm")
        tabs.addTab(voice_page, "Ses")
        tabs.addTab(system_page, "Sistem")
        content.addWidget(tabs, 1)
        content.addWidget(save_btn)

        return content

    def _open_memory(self):
        screen = QApplication.screenAt(self.frameGeometry().center())
        screen = screen or QApplication.primaryScreen()
        available = screen.availableGeometry()

        # Önce Ayarlar'ın sağına açmayı dene. Ekrana sığmıyorsa sola al.
        target_x = self.x() + self.width() + 12
        if target_x + self._memory_window.width() > available.right() + 1:
            target_x = self.x() - self._memory_window.width() - 12

        # Her iki taraf da dar kalırsa pencereyi ekran sınırları içinde tut.
        target_x = max(
            available.left(),
            min(target_x, available.right() - self._memory_window.width() + 1),
        )
        target_y = max(
            available.top(),
            min(self.y(), available.bottom() - self._memory_window.height() + 1),
        )

        self._memory_window.move(target_x, target_y)
        self._memory_window.show()
        self._memory_window.raise_()
        self._memory_window.activateWindow()

    def _open_diagnostics(self):
        self._diagnostics_window.refresh()
        self._diagnostics_window.show()
        self._diagnostics_window.raise_()
        self._diagnostics_window.activateWindow()

    def _open_organizer(self):
        screen = QApplication.screenAt(self.frameGeometry().center())
        screen = screen or QApplication.primaryScreen()
        available = screen.availableGeometry()
        x = max(available.left(), min(
            self.x() - self._organizer_window.width() - 12,
            available.right() - self._organizer_window.width() + 1,
        ))
        y = max(available.top(), min(
            self.y(), available.bottom() - self._organizer_window.height() + 1,
        ))
        self._organizer_window.move(x, y)
        self._organizer_window.show()
        self._organizer_window.activateWindow()

    def _open_daily_settings(self):
        self._daily_settings_window.move(self.x(), self.y() + 80)
        self._daily_settings_window.show()
        self._daily_settings_window.activateWindow()

    def _open_local_model_settings(self):
        self._local_model_window.move(self.x() - 24, self.y() + 70)
        self._local_model_window.show()
        self._local_model_window.raise_()
        self._local_model_window.activateWindow()

    def _update_startup_btn(self):
        if self._startup_enabled:
            self._startup_btn.setText("✅ Açık")
            self._startup_btn.setStyleSheet("""
                QPushButton { background-color: #1a3d20; color: #3fb950; border: 1px solid #3fb950; border-radius: 8px; }
                QPushButton:hover { background-color: #2d5a35; }
            """)
        else:
            self._startup_btn.setText("⭕ Kapalı")
            self._startup_btn.setStyleSheet("""
                QPushButton { background-color: #0d1117; color: #8b949e; border: 1px solid #30363d; border-radius: 8px; }
                QPushButton:hover { border: 1px solid #4a9eff; }
            """)

    def _toggle_startup(self):
        if self._startup_enabled:
            disable_startup()
            self._startup_enabled = False
        else:
            enable_startup()
            self._startup_enabled = True
        self._update_startup_btn()

    def _select_pair(self, user_color: str, ai_color: str):
        config.ACCENT_COLOR = user_color
        config.AI_COLOR = ai_color
        for btn in self._split_buttons:
            btn.is_selected = (btn.user_color == user_color and btn.ai_color == ai_color)
            btn.update()

    def _update_voice_value_labels(self):
        if hasattr(self, "_rate_value"):
            self._rate_value.setText(f"{self._rate_slider.value() / 10:+.1f}")
        if hasattr(self, "_volume_value"):
            self._volume_value.setText(f"%{self._volume_slider.value()}")

    def _current_voice_settings(self) -> dict:
        return {
            "auto_speak": self._tts_auto_checkbox.isChecked(),
            "voice_id": self._voice_combo.currentData() or "",
            "rate": self._rate_slider.value() / 10,
            "volume": self._volume_slider.value() / 100,
        }

    def _test_voice(self):
        if not self._speech:
            return
        values = self._current_voice_settings()
        self._speech.configure(**values)
        ok, message = self._speech.speak(
            "Merhaba, ben Heko. Sesli yanıt özelliğim hazır."
        )
        if not ok:
            QMessageBox.information(self, "Ses kullanılamıyor", message)

    def _save(self):
        selected_mode = next(
            (
                name for name, button in self._mode_buttons.items()
                if button.isChecked()
            ),
            "normal",
        )
        assistant_prompt = self._prompt_edit.toPlainText().strip()
        if not assistant_prompt:
            assistant_prompt = config.MODES[selected_mode]
        try:
            saved_settings = save_app_settings(
                config.APP_SETTINGS_PATH,
                screen_vision_enabled=self._screen_vision_checkbox.isChecked(),
                tts_auto_speak=self._tts_auto_checkbox.isChecked(),
                tts_voice_id=self._voice_combo.currentData() or "",
                tts_rate=self._rate_slider.value() / 10,
                tts_volume=self._volume_slider.value() / 100,
                assistant_mode=selected_mode,
                assistant_prompt=assistant_prompt,
                accent_color=config.ACCENT_COLOR,
                ai_color=config.AI_COLOR,
            )
        except (OSError, TypeError, ValueError) as exc:
            QMessageBox.warning(
                self,
                "Ayar kaydedilemedi",
                f"Ayar tercihleri kaydedilemedi: {exc}",
            )
            return
        config.SCREEN_VISION_ENABLED = saved_settings["screen_vision_enabled"]
        config.TTS_AUTO_SPEAK = saved_settings["tts_auto_speak"]
        config.TTS_VOICE_ID = saved_settings["tts_voice_id"]
        config.TTS_RATE = saved_settings["tts_rate"]
        config.TTS_VOLUME = saved_settings["tts_volume"]
        config.CURRENT_MODE = saved_settings["assistant_mode"]
        config.SYSTEM_PROMPT = saved_settings["assistant_prompt"]
        config.ACCENT_COLOR = saved_settings["accent_color"]
        config.AI_COLOR = saved_settings["ai_color"]
        if self._speech:
            self._speech.configure(
                auto_speak=config.TTS_AUTO_SPEAK,
                voice_id=config.TTS_VOICE_ID,
                rate=config.TTS_RATE,
                volume=config.TTS_VOLUME,
            )
        self.saved.emit()
        self.hide()
