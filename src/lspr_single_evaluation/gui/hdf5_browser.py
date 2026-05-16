from __future__ import annotations

import os
import posixpath as pp
from pathlib import Path
from typing import Any

import h5py
import numpy as np
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSplitter,
    QTableView,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QVBoxLayout,
    QWidget,
)

from .table_model import TableModel


class _AttributeTableModel(QAbstractTableModel):
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._rows = list(rows or [])
        self._columns = ["name", "value"]

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: N802
        if not index.isValid() or not self._rows:
            return None
        row = self._rows[index.row()]
        key = self._columns[index.column()]
        value = row.get(key, "")
        if role == Qt.ItemDataRole.DisplayRole:
            if key == "value" and value is None:
                return ""
            return "" if value is None else str(value)
        if role == Qt.ItemDataRole.EditRole and key == "value":
            return "" if value is None else str(value)
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:  # noqa: N802
        if not index.isValid():
            return Qt.ItemFlag.ItemIsEnabled
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self._columns[index.column()] == "value":
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:  # noqa: N802
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        if self._columns[index.column()] != "value":
            return False
        self._rows[index.row()]["value"] = value
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        return True

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: N802
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self._columns):
            return self._columns[section].title()
        return str(section + 1) if orientation == Qt.Orientation.Vertical else ""

    def row_payload(self, row: int) -> dict[str, Any] | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None


class HDF5BrowserWidget(QWidget):
    pathActivated = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None, *, show_toolbar: bool = True) -> None:
        super().__init__(parent)
        self._file_path: Path | None = None
        self._selected_path: str = "/"
        self._selected_kind: str = ""

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(8)

        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(8)
        title = QLabel("HDF5 Structure")
        title.setObjectName("BrowserTitle")
        self.path_label = QLabel("No file loaded")
        self.path_label.setObjectName("BrowserPath")
        self.reload_button = QPushButton("Reload")
        self.reload_button.clicked.connect(self.reload_file)
        self.copy_button = QPushButton("Copy Path")
        self.copy_button.clicked.connect(self.copy_selected_path)
        self.expand_button = QPushButton("Expand")
        self.expand_button.clicked.connect(self.expand_all)
        self.collapse_button = QPushButton("Collapse")
        self.collapse_button.clicked.connect(self.collapse_all)
        header_layout.addWidget(title)
        header_layout.addWidget(self.path_label, 1)
        header_layout.addWidget(self.reload_button)
        header_layout.addWidget(self.copy_button)
        header_layout.addWidget(self.expand_button)
        header_layout.addWidget(self.collapse_button)
        root_layout.addWidget(header)
        if not show_toolbar:
            header.setVisible(False)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Path", "Type"])
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setRootIsDecorated(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        details = QFrame()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(10, 10, 10, 10)
        details_layout.setSpacing(8)

        self.preview_label = QLabel("Select a node to inspect it.")
        self.preview_label.setObjectName("BrowserPreviewTitle")
        self.preview_label.setWordWrap(True)
        self.preview_text = QLabel("")
        self.preview_text.setObjectName("BrowserPreviewText")
        self.preview_text.setWordWrap(True)
        self.preview_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.attr_model = _AttributeTableModel([])
        self.attr_table = QTableView()
        self.attr_table.setModel(self.attr_model)
        self.attr_table.setAlternatingRowColors(True)
        self.attr_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.attr_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.attr_table.setEditTriggers(QTableView.EditTrigger.DoubleClicked | QTableView.EditTrigger.EditKeyPressed)
        self.attr_model.dataChanged.connect(self._commit_attribute_edit)

        self.data_model = TableModel([], [])
        self.data_table = QTableView()
        self.data_table.setModel(self.data_model)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.data_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)

        self.data_path_text = QLabel("")
        self.data_path_text.setWordWrap(True)
        self.data_path_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        details_layout.addWidget(self.preview_label)
        details_layout.addWidget(self.preview_text)
        details_layout.addWidget(QLabel("Attributes"))
        details_layout.addWidget(self.attr_table, 1)
        details_layout.addWidget(QLabel("Preview"))
        details_layout.addWidget(self.data_path_text)
        details_layout.addWidget(self.data_table, 2)

        splitter.addWidget(self.tree)
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        root_layout.addWidget(splitter, 1)

    def set_file(self, file_path: str | Path | None) -> None:
        self._file_path = Path(file_path) if file_path else None
        self._selected_path = "/"
        self._selected_kind = ""
        self._load_tree()

    def reload_file(self) -> None:
        self._load_tree()

    def expand_all(self) -> None:
        self.tree.expandAll()

    def collapse_all(self) -> None:
        self.tree.collapseAll()

    def copy_selected_path(self) -> None:
        if not self._selected_path:
            return
        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText(self._selected_path)

    def _on_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self.tree)
        act_copy = menu.addAction("Copy path")
        act_expand = menu.addAction("Expand all")
        act_collapse = menu.addAction("Collapse all")
        action = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if action == act_copy:
            self._selected_path = str(item.data(0, Qt.ItemDataRole.UserRole) or "/")
            self.copy_selected_path()
        elif action == act_expand:
            self.expand_all()
        elif action == act_collapse:
            self.collapse_all()

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:  # noqa: ARG002
        self._selected_path = str(item.data(0, Qt.ItemDataRole.UserRole) or "/")
        self._selected_kind = str(item.data(1, Qt.ItemDataRole.UserRole) or "")
        self._refresh_preview()
        self.pathActivated.emit(self._selected_path)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:  # noqa: ARG002
        self._selected_path = str(item.data(0, Qt.ItemDataRole.UserRole) or "/")
        self.pathActivated.emit(self._selected_path)

    def _commit_attribute_edit(self, top_left: QModelIndex, bottom_right: QModelIndex, roles=None) -> None:  # noqa: ARG002
        if self._file_path is None or not top_left.isValid():
            return
        if top_left.column() != 1:
            return
        row = self.attr_model.row_payload(top_left.row())
        if row is None or row.get("name") is None:
            return
        try:
            with h5py.File(self._file_path, "a") as handle:
                obj = handle[self._selected_path]
                attr_name = str(row["name"])
                current = obj.attrs.get(attr_name)
                new_value = row.get("value")
                obj.attrs[attr_name] = self._coerce_attribute_value(current, new_value)
        except Exception:
            return

    def _coerce_attribute_value(self, current: Any, text_value: Any) -> Any:
        text = "" if text_value is None else str(text_value)
        if isinstance(current, (np.bool_, bool)):
            return text.strip().lower() in {"1", "true", "yes", "on"}
        if isinstance(current, (np.integer, int)):
            try:
                return int(float(text))
            except ValueError:
                return int(current)
        if isinstance(current, (np.floating, float)):
            try:
                return float(text)
            except ValueError:
                return float(current)
        return text

    def _load_tree(self) -> None:
        self.tree.clear()
        if self._file_path is None or not self._file_path.exists():
            self.path_label.setText("No file loaded")
            self._refresh_empty_preview()
            return

        self.path_label.setText(str(self._file_path))
        try:
            with h5py.File(self._file_path, "r") as handle:
                root_item = QTreeWidgetItem([self._file_path.name, "File"])
                root_item.setData(0, Qt.ItemDataRole.UserRole, "/")
                root_item.setData(1, Qt.ItemDataRole.UserRole, "file")
                self.tree.addTopLevelItem(root_item)
                self._add_children(handle, "/", root_item)
                self.tree.expandToDepth(1)
                self.tree.setCurrentItem(root_item)
                self._selected_path = "/"
                self._selected_kind = "file"
                self._refresh_preview()
        except Exception as exc:
            self.preview_label.setText("Failed to load HDF5 file")
            self.preview_text.setText(str(exc))

    def _add_children(self, handle: h5py.Group | h5py.File, path: str, parent_item: QTreeWidgetItem) -> None:
        obj = handle[path]
        if isinstance(obj, h5py.Group):
            for name, child in obj.items():
                child_path = pp.join(path, name) if path != "/" else f"/{name}"
                kind = "Group" if isinstance(child, h5py.Group) else f"Dataset {tuple(child.shape)}"
                item = QTreeWidgetItem([name, kind])
                item.setData(0, Qt.ItemDataRole.UserRole, child_path)
                item.setData(1, Qt.ItemDataRole.UserRole, "group" if isinstance(child, h5py.Group) else "dataset")
                parent_item.addChild(item)
                if isinstance(child, h5py.Group):
                    self._add_children(handle, child_path, item)

    def _refresh_preview(self) -> None:
        if self._file_path is None or not self._file_path.exists():
            self._refresh_empty_preview()
            return
        try:
            with h5py.File(self._file_path, "r") as handle:
                obj = handle[self._selected_path]
                if isinstance(obj, h5py.Group):
                    self._preview_group(obj)
                else:
                    self._preview_dataset(obj)
        except Exception as exc:
            self.preview_label.setText("Preview unavailable")
            self.preview_text.setText(str(exc))
            self.attr_model.set_rows([])
            self.data_model.set_rows([], [])
            self.data_path_text.setText("")

    def _refresh_empty_preview(self) -> None:
        self.preview_label.setText("Select a node to inspect it.")
        self.preview_text.setText("")
        self.attr_model.set_rows([])
        self.data_model.set_rows([], [])
        self.data_path_text.setText("")

    def _preview_group(self, group: h5py.Group) -> None:
        children = list(group.keys())
        summary = [
            f"Path: {self._selected_path}",
            "Type: Group",
            f"Children: {len(children)}",
        ]
        if children:
            summary.append("Members: " + ", ".join(children[:12]) + (" ..." if len(children) > 12 else ""))
        self.preview_label.setText(os.path.basename(self._selected_path.rstrip("/")) or "/")
        self.preview_text.setText("\n".join(summary))
        self.data_path_text.setText("")
        self.attr_model.set_rows(self._attribute_rows(group.attrs))
        self.data_model.set_rows([], [])

    def _preview_dataset(self, dataset: h5py.Dataset) -> None:
        array = dataset[...]
        info = [
            f"Path: {self._selected_path}",
            "Type: Dataset",
            f"Shape: {tuple(dataset.shape)}",
            f"Dtype: {dataset.dtype}",
        ]
        if dataset.compression:
            info.append(f"Compression: {dataset.compression}")
        if dataset.chunks:
            info.append(f"Chunks: {dataset.chunks}")
        self.preview_label.setText(os.path.basename(self._selected_path) or self._selected_path)
        self.preview_text.setText("\n".join(info))
        self.data_path_text.setText(f"Preview of {self._selected_path}")
        self.attr_model.set_rows(self._attribute_rows(dataset.attrs))
        self.data_model.set_rows(self._dataset_preview_rows(array), self._dataset_preview_columns(array))

    def _attribute_rows(self, attrs) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key, value in attrs.items():
            if isinstance(value, np.ndarray):
                display = ", ".join(str(item) for item in value.tolist())
            else:
                display = "" if value is None else str(_decode(value))
            rows.append({"name": str(key), "value": display})
        return rows

    def _dataset_preview_rows(self, array: np.ndarray) -> list[dict[str, Any]]:
        if array.ndim == 0:
            return [{"value": _decode(array.item())}]
        if array.ndim == 1:
            limit = min(len(array), 200)
            return [{"index": i, "value": _decode(array[i])} for i in range(limit)]
        if array.ndim >= 2:
            rows: list[dict[str, Any]] = []
            row_limit = min(array.shape[0], 100)
            col_limit = min(array.shape[1], 16)
            for row_index in range(row_limit):
                row = {"index": row_index}
                for col_index in range(col_limit):
                    row[f"c{col_index + 1}"] = _decode(array[row_index, col_index])
                rows.append(row)
            return rows
        return []

    def _dataset_preview_columns(self, array: np.ndarray) -> list[str]:
        if array.ndim == 0:
            return ["value"]
        if array.ndim == 1:
            return ["index", "value"]
        if array.ndim >= 2:
            cols = ["index"]
            cols.extend(f"c{i + 1}" for i in range(min(array.shape[1], 16)))
            return cols
        return []


def _decode(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.generic):
        return value.item()
    return value
