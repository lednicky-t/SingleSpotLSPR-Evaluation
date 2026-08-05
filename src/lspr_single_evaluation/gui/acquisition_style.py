"""Shared visual language for the offline evaluation workspace.

This module intentionally mirrors the calm, compact presentation used by the
acquisition application without importing any acquisition or hardware code.
Keeping the stylesheet local lets the evaluation app evolve independently
until the common UI primitives are ready to move into ``lspr_ui``.
"""

from __future__ import annotations

import pyqtgraph as pg


def apply_acquisition_visual_style(window, theme) -> None:
    """Apply the acquisition-style Qt and plot presentation to *window*."""
    window.setStyleSheet(
        f"""
        QMainWindow, QWidget {{
            background: {theme.window_bg};
            color: {theme.text_primary};
            font-size: 12px;
        }}
        QLabel {{ color: {theme.text_secondary}; }}
        QLabel#toolPanelTitleLabel {{
            color: #e0a84a;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 0.8px;
        }}
        QLabel#topContentHeaderLabel {{
            color: #5b6775;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 0.8px;
        }}
        QLabel#sensorgramHeaderLabel {{
            color: #8fe3a1;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 0.8px;
        }}
        QLabel#panelHintLabel {{
            color: {theme.text_secondary};
            font-size: 11px;
        }}
        QToolButton {{
            background: {theme.control_bg};
            border: 1px solid {theme.control_border};
            border-radius: 8px;
            padding: 3px 6px;
        }}
        QToolButton:hover, QPushButton:hover {{
            background: {theme.control_bg_hover};
            border-color: {theme.control_border_hover};
        }}
        QToolButton:checked, QPushButton:pressed {{
            background: {theme.control_bg_pressed};
            border-color: {theme.primary_action_border};
        }}
        QToolButton#collapseToggle {{
            background: transparent;
            border: none;
            border-radius: 0px;
            color: {theme.text_secondary};
            font-weight: 600;
            padding: 2px 0px 4px 0px;
            text-align: left;
        }}
        QPushButton, QComboBox, QSpinBox, QDoubleSpinBox {{
            background: {theme.control_bg};
            color: {theme.text_primary};
            border: 1px solid {theme.control_border};
            border-radius: 8px;
            padding: 3px 6px;
        }}
        QSpinBox, QDoubleSpinBox {{
            border-radius: 3px;
            padding: 2px 5px;
        }}
        QLineEdit, QTextEdit {{
            background: {theme.window_bg};
            color: {theme.text_primary};
            border: 1px solid {theme.toolbar_border};
            border-radius: 10px;
            padding: 6px;
        }}
        QTextEdit#logTerminal {{
            font-family: Consolas, "Cascadia Mono", monospace;
            font-size: 9pt;
            padding: 4px;
        }}
        QTableView {{
            background: {theme.window_bg};
            color: {theme.text_primary};
            gridline-color: {theme.control_border};
            alternate-background-color: {theme.toolbar_section_bg};
            selection-background-color: {theme.primary_action_bg};
            selection-color: {theme.text_primary};
            border: 1px solid {theme.toolbar_border};
            border-radius: 10px;
        }}
        QHeaderView::section {{
            background: {theme.toolbar_section_bg};
            color: {theme.text_secondary};
            border: none;
            border-bottom: 1px solid {theme.control_border};
            padding: 4px;
            font-weight: 600;
        }}
        QScrollArea, QFrame {{
            background: transparent;
            border: none;
        }}
        QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px 0; }}
        QScrollBar::handle:vertical {{ background: {theme.control_border}; border-radius: 4px; min-height: 28px; }}
        QScrollBar::handle:vertical:hover {{ background: {theme.control_border_hover}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        QSplitter::handle {{ background: transparent; }}
        """
    )

    for plot in (window.spectrum_plot, window.sensorgram_plot):
        plot.setBackground(theme.window_bg)
        item = plot.getPlotItem()
        item.getViewBox().setBackgroundColor(theme.toolbar_section_bg)
        item.getViewBox().setBorder(pg.mkPen(theme.toolbar_border))
        item.showGrid(x=True, y=True, alpha=0.16)
        for axis_name in ("bottom", "left"):
            axis = item.getAxis(axis_name)
            axis.enableAutoSIPrefix(False)
            axis.setStyle(tickTextOffset=2)
            axis.setTextPen(pg.mkPen(theme.text_secondary))
            axis.setPen(pg.mkPen(theme.toolbar_border))
