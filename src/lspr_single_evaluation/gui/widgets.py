from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QLabel,
    QSplitter,
    QSplitterHandle,
    QToolButton,
    QVBoxLayout,
    QSizePolicy,
    QWidget,
)


class CollapsibleSection(QWidget):
    def __init__(self, title: str, content: QWidget, expanded: bool = True) -> None:
        super().__init__()
        self._content = content
        self._toggle = QToolButton()
        self._toggle.setObjectName("collapseToggle")
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(expanded)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setIcon(self._make_chevron_icon(expanded))
        self._toggle.setIconSize(QSize(10, 10))
        self._toggle.clicked.connect(self._set_expanded)
        self._toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._toggle)
        layout.addWidget(self._content)
        self.setLayout(layout)
        self._content.setVisible(expanded)

    def is_expanded(self) -> bool:
        return bool(self._toggle.isChecked())

    def set_expanded(self, expanded: bool) -> None:
        self._toggle.blockSignals(True)
        self._toggle.setChecked(expanded)
        self._toggle.blockSignals(False)
        self._set_expanded(expanded)

    def _set_expanded(self, expanded: bool) -> None:
        self._toggle.setIcon(self._make_chevron_icon(expanded))
        self._content.setVisible(expanded)

    def _make_chevron_icon(self, expanded: bool) -> QIcon:
        pixmap = QPixmap(12, 12)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#5a6b7c"))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if expanded:
            painter.drawLine(3, 4, 6, 7)
            painter.drawLine(9, 4, 6, 7)
        else:
            painter.drawLine(4, 3, 7, 6)
            painter.drawLine(4, 9, 7, 6)
        painter.end()
        return QIcon(pixmap)


class CompactSplitterHandle(QSplitterHandle):
    def paintEvent(self, event) -> None:  # pragma: no cover - Qt painting
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = self.palette().color(self.foregroundRole())
        color.setAlpha(90)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)

        rect = self.rect()
        if self.orientation() == Qt.Orientation.Horizontal:
            center_y = rect.center().y()
            dash_w = max(8, rect.width() // 4)
            dash_h = 2
            gap = 4
            start_x = rect.center().x() - dash_w // 2
            for offset in (-dash_h - gap, 0, dash_h + gap):
                painter.drawRoundedRect(start_x, center_y + offset, dash_w, dash_h, 1, 1)
        else:
            center_x = rect.center().x()
            dash_w = 2
            dash_h = max(8, rect.height() // 4)
            gap = 4
            start_y = rect.center().y() - dash_h // 2
            for offset in (-dash_w - gap, 0, dash_w + gap):
                painter.drawRoundedRect(center_x + offset, start_y, dash_w, dash_h, 1, 1)
        painter.end()


class CompactSplitter(QSplitter):
    def createHandle(self) -> QSplitterHandle:
        return CompactSplitterHandle(self.orientation(), self)

