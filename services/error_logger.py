"""Uygulama hata günlüğü."""

from __future__ import annotations

import logging
import os
import sys

import utils.config as config
from services.security import redact_sensitive_data


LOG_PATH = os.path.join(config.MEMORY_DIR, "heko.log")


class _RedactingFormatter(logging.Formatter):
    def format(self, record):
        return redact_sensitive_data(super().format(record))


def configure_logging():
    os.makedirs(config.MEMORY_DIR, exist_ok=True)
    formatter = _RedactingFormatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handlers = [
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ]
    for handler in handlers:
        handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(logging.INFO)

    def handle_exception(exc_type, exc_value, traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            return sys.__excepthook__(exc_type, exc_value, traceback)
        logging.getLogger("heko").critical(
            "Yakalanmamış hata",
            exc_info=(exc_type, exc_value, traceback),
        )

    sys.excepthook = handle_exception


def log_exception(area: str, error: Exception):
    logging.getLogger(f"heko.{area}").exception("%s", error)
