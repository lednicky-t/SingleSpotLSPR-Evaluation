from __future__ import annotations

import logging
from datetime import datetime

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication


def set_log_following(window, enabled: bool) -> None:
    window._log_follow_enabled = bool(enabled)


def clear_log_terminal(window) -> None:
    if hasattr(window, "log_terminal"):
        window.log_terminal.clear()


def copy_log_terminal(window) -> None:
    if not hasattr(window, "log_terminal"):
        return
    QApplication.clipboard().setText(window.log_terminal.toPlainText())


def append_log_record(window, levelno: int, source: str, text: str) -> None:
    if not hasattr(window, "log_terminal"):
        return
    line = str(text).strip()
    if not line:
        return
    cursor = window.log_terminal.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.beginEditBlock()
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_map = {
            logging.DEBUG: "#7dd3fc",
            logging.INFO: "#cbd5e1",
            logging.WARNING: "#fbbf24",
            logging.ERROR: "#f87171",
            logging.CRITICAL: "#fb7185",
        }
        level_label_map = {
            logging.DEBUG: "DEBUG",
            logging.INFO: "INFO",
            logging.WARNING: "WARN",
            logging.ERROR: "ERROR",
            logging.CRITICAL: "CRIT",
        }
        level_color = color_map.get(int(levelno), "#cbd5e1")
        level_label = level_label_map.get(int(levelno), "INFO")
        source_label = str(source).split(".")[-1] or "app"
        escaped = line.replace("\n", "<br>")
        html = (
            f"<div style='white-space:pre-wrap; margin:0;'>"
            f"<span style='color:#738193;'>{timestamp}</span> "
            f"<span style='color:{level_color}; font-weight:600;'>[{level_label}]</span> "
            f"<span style='color:#94a3b8;'>{source_label}</span> "
            f"<span style='color:#e5edf7;'>{escaped}</span>"
            f"</div>"
        )
        cursor.insertHtml(html)
        cursor.insertHtml("<br>")
    finally:
        cursor.endEditBlock()
        window.log_terminal.setTextCursor(cursor)
    if getattr(window, "_log_follow_enabled", True):
        scrollbar = window.log_terminal.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
