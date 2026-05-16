from __future__ import annotations

from typing import Any

import numpy as np
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt


class TableModel(QAbstractTableModel):
    def __init__(self, rows: list[dict[str, Any]] | None = None, columns: list[str] | None = None) -> None:
        super().__init__()
        self._rows: list[dict[str, Any]] = list(rows or [])
        self._columns: list[str] = list(columns or self._infer_columns(self._rows))

    def set_rows(self, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self._columns = list(columns or self._infer_columns(self._rows))
        self.endResetModel()

    @staticmethod
    def _infer_columns(rows: list[dict[str, Any]]) -> list[str]:
        columns: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in columns:
                    columns.append(key)
        return columns

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: N802
        if not index.isValid() or not self._rows:
            return None
        row = self._rows[index.row()]
        column = self._columns[index.column()]
        value = row.get(column, "")
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if isinstance(value, (int, float, np.integer, np.floating)):
                return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
            return Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if value is None:
            return ""
        if isinstance(value, float):
            if np.isnan(value):
                return ""
            return f"{value:.6g}"
        if isinstance(value, (int, np.integer)):
            return str(int(value))
        return str(value)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._columns):
                return self._columns[section]
            return ""
        if 0 <= section < len(self._rows):
            return str(section)
        return ""
