"""Proje dosyası değişikliklerini güvenli onaydan önce gösteren pencere."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

import utils.config as config


def diff_line_kind(line: str) -> str:
    if line.startswith("@@"):
        return "hunk"
    if line.startswith("+++") or line.startswith("---"):
        return "header"
    if line.startswith("+"):
        return "addition"
    if line.startswith("-"):
        return "deletion"
    return "context"


def diff_stats(diff: str) -> tuple[int, int]:
    additions = deletions = 0
    for line in (diff or "").splitlines():
        kind = diff_line_kind(line)
        additions += kind == "addition"
        deletions += kind == "deletion"
    return additions, deletions


class DiffView(QPlainTextEdit):
    _COLORS = {
        "addition": (QColor("#173b2a"), QColor("#7ee787")),
        "deletion": (QColor("#482329"), QColor("#ff7b72")),
        "hunk": (QColor("#172f4a"), QColor("#79c0ff")),
        "header": (QColor("#252b36"), QColor("#d2a8ff")),
    }

    def __init__(self, diff: str, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setFont(QFont("Cascadia Mono", 10))
        self.setStyleSheet(
            "QPlainTextEdit{background:#0d1117;color:#c9d1d9;"
            "border:1px solid #30363d;border-radius:10px;padding:8px;}"
        )
        self.setPlainText(diff or "(İçerik değişikliği yok.)")
        self._apply_line_formats()

    def _apply_line_formats(self):
        block = self.document().firstBlock()
        while block.isValid():
            colors = self._COLORS.get(diff_line_kind(block.text()))
            if colors:
                cursor = QTextCursor(block)
                cursor.select(QTextCursor.BlockUnderCursor)
                char_format = QTextCharFormat()
                char_format.setBackground(colors[0])
                char_format.setForeground(colors[1])
                cursor.mergeCharFormat(char_format)
            block = block.next()


class ProjectDiffWindow(QDialog):
    approve_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, preview: dict, info_provider, parent=None):
        super().__init__(parent)
        self._preview = dict(preview)
        self._info_provider = info_provider
        self.setWindowTitle(f"Kod değişikliğini incele — {preview['path']}")
        self.setWindowFlags(Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumSize(680, 460)
        self.resize(940, 650)
        self.setStyleSheet("QDialog{background:#11161e;color:#e6edf3;}")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        title = QLabel("Kod değişikliğini incele")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        path = QLabel(preview["path"])
        path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path.setStyleSheet("color:#79c0ff;")
        additions, deletions = diff_stats(preview.get("diff", ""))
        state = "Yeni dosya" if preview.get("is_new") else "Mevcut dosya"
        stats = QLabel(f"{state}   •   +{additions} ekleme   •   -{deletions} silme")
        stats.setStyleSheet("color:#8b949e;")

        self._diff_view = DiffView(preview.get("diff", ""))
        self._countdown = QLabel()
        self._countdown.setStyleSheet("color:#d29922;font-weight:600;")

        buttons = QHBoxLayout()
        copy_button = QPushButton("Diff'i kopyala")
        close_button = QPushButton("Pencereyi kapat")
        self._cancel_button = QPushButton("Reddet")
        self._approve_button = QPushButton("Değişikliği uygula")
        for button in (copy_button, close_button, self._cancel_button):
            button.setStyleSheet(
                "QPushButton{background:#21262d;color:#c9d1d9;border:1px solid "
                "#30363d;border-radius:8px;padding:8px 13px;}"
                "QPushButton:hover{background:#30363d;}"
            )
        self._approve_button.setStyleSheet(
            f"QPushButton{{background:{config.ACCENT_COLOR};color:white;border:none;"
            "border-radius:8px;padding:8px 15px;font-weight:600;}"
        )
        copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(preview.get("diff", ""))
        )
        close_button.clicked.connect(self.close)
        self._cancel_button.clicked.connect(self._cancel)
        self._approve_button.clicked.connect(self._approve)
        buttons.addWidget(copy_button)
        buttons.addWidget(close_button)
        buttons.addStretch()
        buttons.addWidget(self._cancel_button)
        buttons.addWidget(self._approve_button)

        root.addWidget(title)
        root.addWidget(path)
        root.addWidget(stats)
        root.addWidget(self._diff_view, 1)
        root.addWidget(self._countdown)
        root.addLayout(buttons)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh_countdown)
        self._refresh_countdown()
        self._timer.start()

    def _approve(self):
        self._set_decision_enabled(False)
        self.approve_requested.emit()
        self.close()

    def _cancel(self):
        self._set_decision_enabled(False)
        self.cancel_requested.emit()
        self.close()

    def _set_decision_enabled(self, enabled: bool):
        self._approve_button.setEnabled(enabled)
        self._cancel_button.setEnabled(enabled)

    def _refresh_countdown(self):
        info = self._info_provider() if self._info_provider else None
        if not info or info.get("tool_name") != "update_project_file":
            self._timer.stop() if hasattr(self, "_timer") else None
            self._countdown.setText("Bu onay artık geçerli değil.")
            self._set_decision_enabled(False)
            return
        remaining = max(0, int(info.get("seconds_remaining", 0)))
        minutes, seconds = divmod(remaining, 60)
        self._countdown.setText(
            f"Güvenlik onayı için kalan süre: {minutes:02d}:{seconds:02d}"
        )
        if remaining <= 0:
            self._set_decision_enabled(False)
