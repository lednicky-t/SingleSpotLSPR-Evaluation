from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QSettings, Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QDoubleSpinBox,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from lspr_ui import app_icon, get_active_theme
from lspr_ui.theme import standard_push_button_stylesheet

from ..analysis import METRIC_COLUMNS, METRIC_LABELS, build_metrics_rows
from ..io import LoadedExperimentPlan, LoadedSpectra, load_experiment_plan, load_spectra_file
from ..processing import ProcessingSettings, apply_processing_to_spectrum, load_processing_settings
from .experiment_plan_table import ExperimentPlanTableView
from .hdf5_browser import HDF5BrowserWidget
from .logging_utils import GuiLogBridge
from .main_window_logging import append_log_record, clear_log_terminal, copy_log_terminal, set_log_following
from .processing_panel import (
    apply_processing_settings_to_widgets,
    build_processing_group,
    current_processing_settings,
    load_processing_settings_dialog,
    persist_processing_settings,
    save_processing_settings_dialog,
)
from .widgets import CollapsibleSection, CompactSplitter


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None, *, log_bridge: GuiLogBridge | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("singleLSPR Evaluation")
        self.setMinimumSize(1280, 840)
        self.setWindowIcon(app_icon())
        self.settings = QSettings("LSPR", "singleLSPREvaluation")
        self._logger = logging.getLogger("lspr_single_evaluation.gui.main_window")
        self._log_bridge = log_bridge or GuiLogBridge()
        self._log_bridge.record_received.connect(self._append_log_record)
        self._log_follow_enabled = True
        self._suspend_processing_autosave = False

        self.spectra: LoadedSpectra | None = None
        self.experiment_plan: LoadedExperimentPlan | None = None
        self.metrics_rows: list[dict[str, float]] = []
        self.metrics_columns = ["index", "time_s", *METRIC_COLUMNS, "peak_value"]
        self.selected_metric = "peak_nm"
        self.selected_spectrum_index = 0
        self._processing_settings = None

        theme = get_active_theme()
        pg.setConfigOptions(antialias=True)
        pg.setConfigOption("background", theme.window_bg)
        pg.setConfigOption("foreground", theme.text_primary)

        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(10)

        root_layout.addWidget(self._build_splitter(), 1)
        self.setCentralWidget(root)
        self._apply_stylesheet(theme)
        self.statusBar().showMessage("Load a spectra HDF5 file to begin.")
        self._refresh_views()
        QTimer.singleShot(0, self._restore_workspace_state)

    def _build_splitter(self) -> QSplitter:
        splitter = CompactSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self._main_splitter = splitter

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        left_content = QWidget()
        left_content_layout = QVBoxLayout(left_content)
        left_content_layout.setContentsMargins(0, 0, 0, 0)
        left_content_layout.setSpacing(10)

        self.open_spectra_button = QPushButton("Open HDF5")
        self.open_spectra_button.clicked.connect(self.open_spectra_file)
        self.import_spectra_button = QPushButton("Import HDF5")
        self.import_spectra_button.clicked.connect(self.import_spectra_file)
        self.open_plan_button = QPushButton("Open experiment plan")
        self.open_plan_button.clicked.connect(self.open_experiment_plan_file)
        self.recompute_button = QPushButton("Recompute metrics")
        self.recompute_button.clicked.connect(self.recompute_metrics)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_all)

        self.metric_combo = QComboBox()
        self.metric_combo.addItems(METRIC_COLUMNS)
        self.metric_combo.currentTextChanged.connect(self._on_metric_changed)

        load_section = CollapsibleSection("Load / Import", self._build_load_section_content(), expanded=True)

        self._processing_settings = load_processing_settings()
        self._build_processing_controls()
        apply_processing_settings_to_widgets(self, self._processing_settings)
        self._connect_processing_controls()
        processing_section = CollapsibleSection("Processing", build_processing_group(self), expanded=False)

        self.browser = HDF5BrowserWidget(show_toolbar=False)
        self.browser.pathActivated.connect(self._on_browser_path_activated)
        self.browser.setMinimumWidth(360)
        browser_section = CollapsibleSection("HDF5 Browser", self._build_browser_section_content(), expanded=True)

        self.left_summary = QTextEdit()
        self.left_summary.setReadOnly(True)
        self.left_summary.setMinimumHeight(120)
        summary_section = CollapsibleSection("Summary", self._build_summary_section_content(), expanded=True)

        self.log_terminal = QTextEdit()
        self.log_terminal.setObjectName("logTerminal")
        self.log_terminal.setReadOnly(True)
        self.log_terminal.setAcceptRichText(True)
        self.log_terminal.setUndoRedoEnabled(False)
        self.log_terminal.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_terminal.document().setMaximumBlockCount(300)
        self.log_terminal.setMinimumHeight(160)
        self.log_terminal.setToolTip("Live event log for evaluation, plotting, and file loading activity.")
        self.log_clear_button = QToolButton()
        self.log_clear_button.setText("Clear")
        self.log_clear_button.clicked.connect(self._clear_log_terminal)
        self.log_copy_button = QToolButton()
        self.log_copy_button.setText("Copy")
        self.log_copy_button.clicked.connect(self._copy_log_terminal)
        self.log_follow_button = QToolButton()
        self.log_follow_button.setText("Follow")
        self.log_follow_button.setCheckable(True)
        self.log_follow_button.setChecked(True)
        self.log_follow_button.toggled.connect(self._toggle_log_follow)
        log_section = CollapsibleSection("Log", self._build_log_section_content(), expanded=True)

        self._load_section = load_section
        self._processing_section = processing_section
        self._browser_section = browser_section
        self._summary_section = summary_section
        self._log_section = log_section

        left_content_layout.addWidget(load_section)
        left_content_layout.addWidget(processing_section)
        left_content_layout.addWidget(browser_section, 1)
        left_content_layout.addWidget(summary_section)
        left_content_layout.addWidget(log_section)
        left_content_layout.addStretch(1)

        scroll.setWidget(left_content)
        left_layout.addWidget(scroll, 1)

        plots_splitter = CompactSplitter(Qt.Orientation.Vertical)
        plots_splitter.setChildrenCollapsible(False)
        self._plot_splitter = plots_splitter

        top_analysis_splitter = CompactSplitter(Qt.Orientation.Horizontal)
        top_analysis_splitter.setChildrenCollapsible(False)
        self._top_analysis_splitter = top_analysis_splitter

        self.experiment_plan_table = ExperimentPlanTableView()
        self.experiment_plan_table.setMinimumWidth(260)
        self.experiment_plan_table.setMaximumWidth(460)

        self.spectrum_plot = pg.PlotWidget()
        self.spectrum_plot.setMinimumHeight(280)
        self.spectrum_plot.showGrid(x=True, y=True, alpha=0.25)
        self.spectrum_plot.addLegend(offset=(8, 8))
        self.spectrum_plot.setLabel("bottom", "Wavelength", units="nm")
        self.spectrum_plot.setLabel("left", "Signal")

        self.sensorgram_plot = pg.PlotWidget()
        self.sensorgram_plot.setMinimumHeight(280)
        self.sensorgram_plot.showGrid(x=True, y=True, alpha=0.25)
        self.sensorgram_plot.addLegend(offset=(8, 8))
        self.sensorgram_plot.setLabel("bottom", "Time", units="s")
        self.sensorgram_plot.setLabel("left", "Peak position", units="nm")

        top_analysis_splitter.addWidget(self.experiment_plan_table)
        top_analysis_splitter.addWidget(self.spectrum_plot)
        top_analysis_splitter.setStretchFactor(0, 0)
        top_analysis_splitter.setStretchFactor(1, 1)

        plots_splitter.addWidget(top_analysis_splitter)
        plots_splitter.addWidget(self.sensorgram_plot)
        plots_splitter.setStretchFactor(0, 1)
        plots_splitter.setStretchFactor(1, 1)

        splitter.addWidget(left_panel)
        splitter.addWidget(plots_splitter)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        return splitter

    def _build_load_section_content(self) -> QWidget:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        button_row = QWidget()
        button_row_layout = QVBoxLayout(button_row)
        button_row_layout.setContentsMargins(0, 0, 0, 0)
        button_row_layout.setSpacing(6)

        for button in (
            self.open_spectra_button,
            self.import_spectra_button,
            self.open_plan_button,
            self.recompute_button,
            self.clear_button,
        ):
            button.setStyleSheet(standard_push_button_stylesheet())
            button_row_layout.addWidget(button)

        metric_row = QWidget()
        metric_row_layout = QVBoxLayout(metric_row)
        metric_row_layout.setContentsMargins(0, 0, 0, 0)
        metric_row_layout.setSpacing(6)

        metric_label = QLabel("Sensorgram metric")
        metric_label.setObjectName("toolbarSectionTitle")
        metric_label.setStyleSheet("color: inherit; font-weight: 700;")

        self.metric_combo.setMinimumHeight(28)
        metric_row_layout.addWidget(metric_label)
        metric_row_layout.addWidget(self.metric_combo)

        layout.addWidget(button_row)
        layout.addWidget(metric_row)
        return frame

    def _build_browser_section_content(self) -> QWidget:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(self.browser, 1)
        return frame

    def _build_summary_section_content(self) -> QWidget:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(self.left_summary, 1)
        return frame

    def _build_processing_controls(self) -> None:
        self.range_min_spin = QDoubleSpinBox()
        self.range_min_spin.setRange(0.0, 5000.0)
        self.range_min_spin.setDecimals(2)
        self.range_min_spin.setSingleStep(1.0)

        self.range_max_spin = QDoubleSpinBox()
        self.range_max_spin.setRange(0.0, 5000.0)
        self.range_max_spin.setDecimals(2)
        self.range_max_spin.setSingleStep(1.0)

        self.baseline_method_combo = QComboBox()
        self.baseline_method_combo.addItems(["none", "minimum", "median"])

        self.smoothing_method_combo = QComboBox()
        self.smoothing_method_combo.addItems(["none", "boxcar", "gaussian"])

        self.smoothing_window_spin = QSpinBox()
        self.smoothing_window_spin.setRange(1, 101)
        self.smoothing_window_spin.setSingleStep(2)

        self.temporal_smoothing_spin = QSpinBox()
        self.temporal_smoothing_spin.setRange(1, 31)
        self.temporal_smoothing_spin.setSingleStep(1)

        self.crop_method_combo = QComboBox()
        self.crop_method_combo.addItems(["fixed_width", "threshold"])

        self.crop_fraction_spin = QDoubleSpinBox()
        self.crop_fraction_spin.setRange(0.05, 0.95)
        self.crop_fraction_spin.setSingleStep(0.05)
        self.crop_fraction_spin.setDecimals(2)

        self.fit_method_combo = QComboBox()
        self.fit_method_combo.addItems(["none", "poly", "gaussian"])

        self.poly_order_spin = QSpinBox()
        self.poly_order_spin.setRange(1, 10)
        self.poly_order_spin.setSingleStep(1)

        self.fit_window_spin = QDoubleSpinBox()
        self.fit_window_spin.setRange(5.0, 500.0)
        self.fit_window_spin.setDecimals(1)
        self.fit_window_spin.setSingleStep(5.0)

        self.analysis_resolution_spin = QDoubleSpinBox()
        self.analysis_resolution_spin.setRange(0.0001, 1.0)
        self.analysis_resolution_spin.setDecimals(4)
        self.analysis_resolution_spin.setSingleStep(0.001)

        self.peak_metric_combo = QComboBox()
        self.peak_metric_combo.addItems(["peak_nm", "centroid_nm", "fwhm_nm"])

        self.trace_noise_window_spin = QDoubleSpinBox()
        self.trace_noise_window_spin.setRange(0.5, 600.0)
        self.trace_noise_window_spin.setDecimals(1)
        self.trace_noise_window_spin.setSingleStep(1.0)

        self.trace_peak_check = QCheckBox("Peak position")
        self.trace_centroid_check = QCheckBox("Centroid")
        self.trace_fwhm_check = QCheckBox("FWHM")

        self.poly_warning_label = QLabel(" ")
        self.poly_warning_label.setObjectName("PolyWarning")

        self.save_processing_button = QPushButton("Save settings")
        self.save_processing_button.clicked.connect(self._save_processing_settings_dialog)
        self.load_processing_button = QPushButton("Load settings")
        self.load_processing_button.clicked.connect(self._load_processing_settings_dialog)

    def _connect_processing_controls(self) -> None:
        controls = [
            self.range_min_spin,
            self.range_max_spin,
            self.baseline_method_combo,
            self.smoothing_method_combo,
            self.smoothing_window_spin,
            self.temporal_smoothing_spin,
            self.crop_method_combo,
            self.crop_fraction_spin,
            self.fit_method_combo,
            self.poly_order_spin,
            self.fit_window_spin,
            self.analysis_resolution_spin,
            self.peak_metric_combo,
            self.trace_noise_window_spin,
            self.trace_peak_check,
            self.trace_centroid_check,
            self.trace_fwhm_check,
        ]
        for control in controls:
            if isinstance(control, QComboBox):
                control.currentTextChanged.connect(self._on_processing_changed)
            elif isinstance(control, QCheckBox):
                control.toggled.connect(self._on_processing_changed)
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                control.valueChanged.connect(self._on_processing_changed)

    def _on_processing_changed(self, *_args) -> None:
        if self._suspend_processing_autosave:
            return
        self._processing_settings = current_processing_settings(self)
        persist_processing_settings(self)
        if self.spectra is not None:
            self.recompute_metrics()

    def _build_log_section_content(self) -> QWidget:
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(6)
        self.log_clear_button.setStyleSheet(standard_push_button_stylesheet(padding="4px 8px", font_size=10))
        self.log_copy_button.setStyleSheet(standard_push_button_stylesheet(padding="4px 8px", font_size=10))
        self.log_follow_button.setStyleSheet(standard_push_button_stylesheet(padding="4px 8px", font_size=10))
        button_layout.addWidget(self.log_clear_button)
        button_layout.addWidget(self.log_copy_button)
        button_layout.addWidget(self.log_follow_button)
        button_layout.addStretch(1)

        layout.addWidget(button_row)
        layout.addWidget(self.log_terminal, 1)
        return frame

    def _apply_stylesheet(self, theme) -> None:
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background: {theme.window_bg};
            }}
            QFrame {{
                background: transparent;
                border: none;
            }}
            QToolButton#collapseToggle {{
                background: transparent;
                border: none;
                color: {theme.text_secondary};
                font-size: 12px;
                font-weight: 700;
                padding: 4px 0;
                text-align: left;
            }}
            QToolButton#collapseToggle:hover {{
                color: {theme.text_primary};
            }}
            QToolButton#collapseToggle:pressed {{
                color: {theme.text_primary};
            }}
            QPushButton {{
                background: {theme.control_bg};
                color: {theme.text_primary};
                border: 1px solid {theme.control_border};
                border-radius: 10px;
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {theme.control_bg_hover};
                border-color: {theme.control_border_hover};
            }}
            QPushButton:pressed {{
                background: {theme.control_bg_pressed};
                border-color: {theme.primary_action_border};
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
            QTextEdit {{
                background: {theme.window_bg};
                color: {theme.text_primary};
                border: 1px solid {theme.toolbar_border};
                border-radius: 8px;
            }}
            QTextEdit#logTerminal {{
                font-family: Consolas, "Cascadia Mono", monospace;
                font-size: 9pt;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            """
        )

    def _looks_current_spectra_format(self, spectra: LoadedSpectra) -> bool:
        metadata = spectra.root_metadata or {}
        version_keys = {"format_version", "schema_version", "app_version", "version"}
        return any(key in metadata for key in version_keys)

    def _load_spectra_file(self, file_path: str, *, import_mode: bool = False) -> None:
        self.spectra = load_spectra_file(file_path)
        self.browser.set_file(file_path)
        if self.spectra.embedded_experiment_plan is not None and self.experiment_plan is None:
            self.experiment_plan = self.spectra.embedded_experiment_plan
        self.selected_spectrum_index = 0
        self.settings.setValue("ui/last_spectra_path", file_path)
        if import_mode and not self._looks_current_spectra_format(self.spectra):
            self.spectra.notes.append("Imported from a legacy HDF5 format.")
            self._logger.info("Imported legacy spectra file: %s", file_path)
        else:
            self._logger.info("Loaded spectra file: %s", file_path)
        self._after_data_change()

    def open_spectra_file(self) -> None:
        start_dir = str(self.settings.value("ui/last_dir", "", type=str) or "")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open spectra HDF5 file",
            start_dir,
            "HDF5 files (*.h5 *.hdf5);;All files (*.*)",
        )
        if not file_path:
            return
        self.settings.setValue("ui/last_dir", str(Path(file_path).parent))
        try:
            self._load_spectra_file(file_path, import_mode=False)
        except Exception as exc:
            self._logger.exception("Failed to load spectra file: %s", file_path)
            QMessageBox.critical(self, "Open spectra failed", f"Could not load spectra file:\n{exc}")

    def import_spectra_file(self) -> None:
        start_dir = str(self.settings.value("ui/last_dir", "", type=str) or "")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import legacy spectra HDF5 file",
            start_dir,
            "HDF5 files (*.h5 *.hdf5);;All files (*.*)",
        )
        if not file_path:
            return
        self.settings.setValue("ui/last_dir", str(Path(file_path).parent))
        try:
            self._load_spectra_file(file_path, import_mode=True)
            self.statusBar().showMessage(f"Imported spectra from {Path(file_path).name}")
        except Exception as exc:
            self._logger.exception("Failed to import spectra file: %s", file_path)
            QMessageBox.critical(self, "Import spectra failed", f"Could not import spectra file:\n{exc}")

    def open_experiment_plan_file(self) -> None:
        start_dir = str(self.settings.value("ui/last_dir", "", type=str) or "")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open experiment plan",
            start_dir,
            "Experiment plans (*.flow.yaml *.yaml *.yml *.csv *.txt *.h5 *.hdf5);;All files (*.*)",
        )
        if not file_path:
            return
        self.settings.setValue("ui/last_dir", str(Path(file_path).parent))
        try:
            self.experiment_plan = load_experiment_plan(file_path)
            self.settings.setValue("ui/last_experiment_plan_path", file_path)
            self._logger.info("Loaded experiment plan: %s", file_path)
            self._refresh_views()
        except Exception as exc:
            self._logger.exception("Failed to load experiment plan: %s", file_path)
            QMessageBox.critical(self, "Open experiment plan failed", f"Could not load experiment plan:\n{exc}")

    def clear_all(self) -> None:
        self.spectra = None
        self.experiment_plan = None
        self.metrics_rows = []
        self.selected_spectrum_index = 0
        self.browser.set_file(None)
        self.experiment_plan_table.set_rows([])
        self._logger.info("Cleared spectra, experiment plan, and metrics.")
        self._refresh_views()

    def recompute_metrics(self) -> None:
        if self.spectra is None:
            self._logger.warning("Recompute requested without spectra loaded.")
            return
        self._logger.info("Recomputing metrics.")
        self._compute_metrics()
        self._refresh_views()

    def _on_metric_changed(self, metric: str) -> None:
        self.selected_metric = metric
        self._logger.debug("Selected metric changed to %s.", metric)
        self._refresh_sensorgram_plot()

    def _on_browser_path_activated(self, path: str) -> None:
        if not path or self.spectra is None:
            return
        normalized = path.strip()
        if normalized in {self.spectra.spectra_path, f"/{self.spectra.spectra_path}", self.spectra.wavelength_path, self.spectra.time_path}:
            self.statusBar().showMessage(f"Selected {normalized}")
            self._logger.debug("Activated HDF5 path %s", normalized)
            return

    def _after_data_change(self) -> None:
        self._compute_metrics()
        self._refresh_views()

    def _compute_metrics(self) -> None:
        if self.spectra is None:
            self.metrics_rows = []
            return
        self.metrics_rows = build_metrics_rows(
            self.spectra.wavelengths_nm,
            self.spectra.spectra,
            self.spectra.time_s,
        )
        if self.metrics_rows:
            self.selected_spectrum_index = min(self.selected_spectrum_index, len(self.metrics_rows) - 1)
            if self.selected_metric not in self.metrics_columns:
                self.selected_metric = "peak_nm"

    def _refresh_views(self) -> None:
        self._refresh_summary()
        self._refresh_experiment_plan_table()
        self._refresh_spectrum_plot()
        self._refresh_sensorgram_plot()

    def _refresh_experiment_plan_table(self) -> None:
        if self.experiment_plan is None:
            self.experiment_plan_table.set_rows([])
            return
        self.experiment_plan_table.set_rows(self.experiment_plan.rows, self.experiment_plan.columns)

    def _refresh_summary(self) -> None:
        lines: list[str] = []
        if self.spectra is None:
            lines.append("Spectra: not loaded")
        else:
            lines.extend(self.spectra.summary_lines())
        if self.experiment_plan is None:
            lines.append("Experiment plan: not loaded")
        else:
            lines.extend(self.experiment_plan.summary_lines())
        if not self.metrics_rows:
            lines.append("Metrics: not computed")
        else:
            lines.append(f"Metrics rows: {len(self.metrics_rows)}")
            lines.append(f"Selected metric: {self.selected_metric}")
        self.left_summary.setPlainText("\n".join(lines))
        self.statusBar().showMessage(lines[0] if lines else "Ready")

    def _refresh_spectrum_plot(self) -> None:
        plot = self.spectrum_plot.getPlotItem()
        plot.clear()
        if self.spectra is None or not self.metrics_rows:
            plot.setLabel("bottom", "Wavelength", units="nm")
            plot.setLabel("left", "Signal")
            plot.addItem(pg.TextItem("Load a spectra file to preview the current spectrum.", anchor=(0.5, 0.5)))
            return
        index = int(np.clip(self.selected_spectrum_index, 0, len(self.metrics_rows) - 1))
        settings = current_processing_settings(self)
        wavelengths, spectrum = apply_processing_to_spectrum(
            np.asarray(self.spectra.wavelengths_nm, dtype=float),
            np.asarray(self.spectra.spectra[index], dtype=float),
            settings,
        )
        plot.plot(wavelengths, spectrum, pen=pg.mkPen(QColor("#60a5fa"), width=2), name="Spectrum")
        peak_nm = float(self.metrics_rows[index].get("peak_nm", float("nan")))
        if np.isfinite(peak_nm):
            peak_y = float(np.nanmax(spectrum))
            plot.plot(
                [peak_nm],
                [peak_y],
                pen=None,
                symbol="o",
                symbolSize=9,
                symbolBrush=QColor("#f59e0b"),
                name="Peak",
            )
        plot.setLabel("bottom", "Wavelength", units="nm")
        plot.setLabel("left", "Signal")
        plot.enableAutoRange(axis="y", enable=True)
        plot.enableAutoRange(axis="x", enable=True)

    def _append_log_record(self, levelno: int, source: str, text: str) -> None:
        append_log_record(self, levelno, source, text)

    def _clear_log_terminal(self) -> None:
        clear_log_terminal(self)
        self.statusBar().showMessage("Log terminal cleared.")

    def _copy_log_terminal(self) -> None:
        copy_log_terminal(self)
        self.statusBar().showMessage("Log terminal copied to clipboard.")

    def _toggle_log_follow(self, enabled: bool) -> None:
        set_log_following(self, enabled)
        self._logger.debug("Log follow %s.", "enabled" if enabled else "disabled")

    def _save_processing_settings_dialog(self) -> None:
        save_processing_settings_dialog(self)

    def _load_processing_settings_dialog(self) -> None:
        load_processing_settings_dialog(self)

    def _refresh_sensorgram_plot(self) -> None:
        plot = self.sensorgram_plot.getPlotItem()
        plot.clear()
        if not self.metrics_rows:
            plot.setLabel("bottom", "Time", units="s")
            plot.setLabel("left", "Peak position", units="nm")
            plot.addItem(pg.TextItem("Load a spectra file to plot the sensorgram.", anchor=(0.5, 0.5)))
            return
        metric = self.selected_metric if self.selected_metric in self.metrics_columns else "peak_nm"
        metric_label = METRIC_LABELS.get(metric, metric)
        time_s = np.asarray([float(row.get("time_s", float("nan"))) for row in self.metrics_rows], dtype=float)
        values = np.asarray([float(row.get(metric, float("nan"))) for row in self.metrics_rows], dtype=float)
        finite = np.isfinite(time_s) & np.isfinite(values)
        plot.plot(time_s, values, pen=pg.mkPen(QColor("#22c55e"), width=2), name=metric_label)
        if np.any(finite):
            plot.plot(
                time_s[finite],
                values[finite],
                pen=None,
                symbol="o",
                symbolSize=6,
                symbolBrush=QColor("#38bdf8"),
                name="Samples",
            )
        if self.experiment_plan is not None and self.experiment_plan.rows:
            for row in self.experiment_plan.rows:
                start_s = float(row.get("start_s", float("nan")))
                end_s = float(row.get("end_s", float("nan")))
                if not np.isfinite(start_s) or not np.isfinite(end_s) or end_s <= start_s:
                    continue
                color_value = str(row.get("color", "") or "")
                brush_color = QColor(color_value) if color_value else QColor("#4b5563")
                brush_color.setAlpha(40)
                region = pg.LinearRegionItem(
                    values=[start_s, end_s],
                    orientation="vertical",
                    brush=pg.mkBrush(brush_color),
                    movable=False,
                )
                region.setZValue(-10)
                plot.addItem(region)
        plot.setLabel("bottom", "Time", units="s")
        plot.setLabel("left", metric_label, units="nm" if metric.endswith("_nm") else "")
        plot.enableAutoRange(axis="y", enable=True)
        plot.enableAutoRange(axis="x", enable=True)

    def _restore_workspace_state(self) -> None:
        self._restore_session_state()
        self._restore_last_files()

    def _restore_session_state(self) -> None:
        geometry = self.settings.value("ui/main_window_geometry")
        if isinstance(geometry, bytes):
            self.restoreGeometry(geometry)
        elif hasattr(geometry, "data"):
            self.restoreGeometry(bytes(geometry))

        splitter_sizes = self.settings.value("ui/main_splitter_sizes")
        if isinstance(splitter_sizes, list) and len(splitter_sizes) == 2:
            sizes = [int(size) for size in splitter_sizes]
            if all(size > 0 for size in sizes):
                self._main_splitter.setSizes(sizes)

        top_analysis_splitter_sizes = self.settings.value("ui/top_analysis_splitter_sizes")
        if isinstance(top_analysis_splitter_sizes, list) and len(top_analysis_splitter_sizes) == 2:
            sizes = [int(size) for size in top_analysis_splitter_sizes]
            if all(size > 0 for size in sizes):
                self._top_analysis_splitter.setSizes(sizes)

        plot_splitter_sizes = self.settings.value("ui/plot_splitter_sizes")
        if isinstance(plot_splitter_sizes, list) and len(plot_splitter_sizes) == 2:
            sizes = [int(size) for size in plot_splitter_sizes]
            if all(size > 0 for size in sizes):
                self._plot_splitter.setSizes(sizes)

        load_expanded = self.settings.value("ui/load_section_expanded")
        if isinstance(load_expanded, bool):
            self._load_section.set_expanded(load_expanded)
        browser_expanded = self.settings.value("ui/browser_section_expanded")
        if isinstance(browser_expanded, bool):
            self._browser_section.set_expanded(browser_expanded)
        summary_expanded = self.settings.value("ui/summary_section_expanded")
        if isinstance(summary_expanded, bool):
            self._summary_section.set_expanded(summary_expanded)
        processing_expanded = self.settings.value("ui/processing_section_expanded")
        if isinstance(processing_expanded, bool):
            self._processing_section.set_expanded(processing_expanded)
        log_expanded = self.settings.value("ui/log_section_expanded")
        if isinstance(log_expanded, bool):
            self._log_section.set_expanded(log_expanded)

        selected_metric = self.settings.value("ui/selected_metric", "", type=str) or ""
        if selected_metric and selected_metric in METRIC_COLUMNS:
            self.metric_combo.blockSignals(True)
            self.metric_combo.setCurrentText(selected_metric)
            self.metric_combo.blockSignals(False)
            self.selected_metric = selected_metric

        log_follow = self.settings.value("ui/log_follow", True, type=bool)
        self.log_follow_button.blockSignals(True)
        self.log_follow_button.setChecked(bool(log_follow))
        self.log_follow_button.blockSignals(False)
        set_log_following(self, bool(log_follow))

        processing_state = self.settings.value("ui/processing_settings", None)
        if isinstance(processing_state, dict):
            try:
                self._processing_settings = ProcessingSettings(
                    **{key: value for key, value in processing_state.items() if key in ProcessingSettings.__dataclass_fields__}
                )
                apply_processing_settings_to_widgets(self, self._processing_settings)
            except Exception:
                pass

    def _restore_last_files(self) -> None:
        last_spectra = str(self.settings.value("ui/last_spectra_path", "", type=str) or "").strip()
        last_experiment_plan = str(
            self.settings.value(
                "ui/last_experiment_plan_path",
                self.settings.value("ui/last_experiment_plan_path", "", type=str),
                type=str,
            )
            or ""
        ).strip()

        if last_spectra:
            spectra_path = Path(last_spectra)
            if spectra_path.exists():
                try:
                    self.spectra = load_spectra_file(str(spectra_path))
                    self.browser.set_file(str(spectra_path))
                    if self.spectra.embedded_experiment_plan is not None:
                        self.experiment_plan = self.spectra.embedded_experiment_plan
                    self.selected_spectrum_index = 0
                    self._logger.info("Restored last spectra file: %s", spectra_path)
                except Exception as exc:
                    self._logger.exception("Failed to restore spectra file: %s", spectra_path)
                    self.statusBar().showMessage(f"Could not restore spectra file: {exc}")
            else:
                self._logger.warning("Last spectra file not found: %s", spectra_path)

        if last_experiment_plan:
            experiment_plan_path = Path(last_experiment_plan)
            if experiment_plan_path.exists():
                try:
                    self.experiment_plan = load_experiment_plan(str(experiment_plan_path))
                    self._logger.info("Restored last experiment plan: %s", experiment_plan_path)
                except Exception as exc:
                    self._logger.exception("Failed to restore experiment plan: %s", experiment_plan_path)
                    self.statusBar().showMessage(f"Could not restore experiment plan: {exc}")
            else:
                self._logger.warning("Last experiment plan file not found: %s", experiment_plan_path)

        if self.spectra is not None or self.experiment_plan is not None:
            self._after_data_change() if self.spectra is not None else self._refresh_views()

    def _save_session_state(self) -> None:
        self.settings.setValue("ui/main_window_geometry", self.saveGeometry())
        self.settings.setValue("ui/main_splitter_sizes", [int(size) for size in self._main_splitter.sizes()])
        self.settings.setValue("ui/top_analysis_splitter_sizes", [int(size) for size in self._top_analysis_splitter.sizes()])
        self.settings.setValue("ui/plot_splitter_sizes", [int(size) for size in self._plot_splitter.sizes()])
        self.settings.setValue("ui/load_section_expanded", bool(self._load_section.is_expanded()))
        self.settings.setValue("ui/browser_section_expanded", bool(self._browser_section.is_expanded()))
        self.settings.setValue("ui/summary_section_expanded", bool(self._summary_section.is_expanded()))
        self.settings.setValue("ui/processing_section_expanded", bool(self._processing_section.is_expanded()))
        self.settings.setValue("ui/log_section_expanded", bool(self._log_section.is_expanded()))
        self.settings.setValue("ui/selected_metric", self.selected_metric)
        self.settings.setValue("ui/log_follow", bool(self._log_follow_enabled))
        processing_settings = current_processing_settings(self)
        self.settings.setValue("ui/processing_settings", asdict(processing_settings))
        self.settings.setValue("ui/last_spectra_path", str(self.spectra.path) if self.spectra is not None else "")
        self.settings.setValue("ui/last_experiment_plan_path", str(self.experiment_plan.path) if self.experiment_plan is not None else "")
        self.settings.sync()

    def closeEvent(self, event) -> None:  # pragma: no cover - GUI runtime path
        self._save_session_state()
        super().closeEvent(event)

