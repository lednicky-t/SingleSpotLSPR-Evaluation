from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHeaderView, QTableView

from .table_model import TableModel


DEFAULT_EXPERIMENT_PLAN_COLUMNS = [
    "step",
    "start_s",
    "end_s",
    "duration_s",
    "color",
    "description",
    "valve",
    "switch_position",
]


class ExperimentPlanTableView(QTableView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._model = TableModel([], DEFAULT_EXPERIMENT_PLAN_COLUMNS)
        self.setModel(self._model)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)

    def set_rows(self, rows: list[dict[str, object]], columns: list[str] | None = None) -> None:
        filtered_columns = list(columns or DEFAULT_EXPERIMENT_PLAN_COLUMNS)
        self._model.set_rows(rows, filtered_columns)
        for index, column in enumerate(filtered_columns):
            if column == "description":
                self.horizontalHeader().setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
                break
