from __future__ import annotations

import logging
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from lspr_ui import app_icon, apply_base_app_theme, get_active_theme

from .gui import MainWindow
from .gui.logging_utils import GuiLogBridge, GuiLogHandler
from .processing import get_and_clear_settings_corruption_notice
from .version import APP_NAME, APP_VERSION, version_string


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(version_string())
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("LSPR")
    app.setOrganizationDomain("lspr.local")
    app.setStyle("Fusion")
    apply_base_app_theme(app, get_active_theme())
    app.setWindowIcon(app_icon())

    logging.captureWarnings(True)
    bridge = GuiLogBridge()
    handler = GuiLogHandler(bridge)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.setLevel(logging.DEBUG)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)

    window = MainWindow(log_bridge=bridge)

    corruption_notice = get_and_clear_settings_corruption_notice()
    if corruption_notice:
        QMessageBox.warning(window, "Settings reset", corruption_notice)

    window.show()
    window.raise_()
    window.activateWindow()
    root_logger.info("singleLSPR Evaluation starting.")
    sys.exit(app.exec())
