from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..processing import DEFAULT_PROCESSING_PATH, ProcessingSettings, load_processing_settings, save_processing_settings


def current_processing_settings(window) -> ProcessingSettings:
    low = min(window.range_min_spin.value(), window.range_max_spin.value())
    high = max(window.range_min_spin.value(), window.range_max_spin.value())
    trace_metrics: list[str] = []
    if window.trace_peak_check.isChecked():
        trace_metrics.append("peak_nm")
    if window.trace_centroid_check.isChecked():
        trace_metrics.append("centroid_nm")
    if window.trace_fwhm_check.isChecked():
        trace_metrics.append("fwhm_nm")
    return ProcessingSettings(
        wavelength_min_nm=low,
        wavelength_max_nm=high,
        baseline_method=window.baseline_method_combo.currentText(),
        smoothing_method=window.smoothing_method_combo.currentText(),
        smoothing_window=window.smoothing_window_spin.value(),
        temporal_smoothing=window.temporal_smoothing_spin.value(),
        crop_method=window.crop_method_combo.currentText(),
        crop_fraction=window.crop_fraction_spin.value(),
        fit_method=window.fit_method_combo.currentText(),
        polynomial_order=window.poly_order_spin.value(),
        fit_window_width_nm=window.fit_window_spin.value(),
        analysis_resolution_nm=window.analysis_resolution_spin.value(),
        peak_tracking_mode=window.peak_metric_combo.currentText(),
        trace_noise_window_s=window.trace_noise_window_spin.value(),
        trace_metrics=trace_metrics or ["peak_nm", "centroid_nm"],
    )


def apply_processing_settings_to_widgets(window, settings: ProcessingSettings) -> None:
    window._suspend_processing_autosave = True
    window.range_min_spin.setValue(float(settings.wavelength_min_nm))
    window.range_max_spin.setValue(float(settings.wavelength_max_nm))
    window.baseline_method_combo.setCurrentText(settings.baseline_method)
    window.smoothing_method_combo.setCurrentText(settings.smoothing_method)
    window.smoothing_window_spin.setValue(int(settings.smoothing_window))
    window.temporal_smoothing_spin.setValue(int(settings.temporal_smoothing))
    window.crop_method_combo.setCurrentText(settings.crop_method)
    window.crop_fraction_spin.setValue(float(settings.crop_fraction))
    window.fit_method_combo.setCurrentText(settings.fit_method)
    window.poly_order_spin.setValue(int(settings.polynomial_order))
    window.fit_window_spin.setValue(float(settings.fit_window_width_nm))
    window.analysis_resolution_spin.setValue(float(settings.analysis_resolution_nm))
    window.peak_metric_combo.setCurrentText(settings.peak_tracking_mode)
    window.trace_noise_window_spin.setValue(float(settings.trace_noise_window_s))
    trace_metrics = set(settings.trace_metrics)
    window.trace_peak_check.setChecked("peak_nm" in trace_metrics)
    window.trace_centroid_check.setChecked("centroid_nm" in trace_metrics)
    window.trace_fwhm_check.setChecked("fwhm_nm" in trace_metrics)
    window._suspend_processing_autosave = False


def persist_processing_settings(window) -> None:
    window._processing_settings = current_processing_settings(window)
    save_processing_settings(window._processing_settings)


def save_processing_settings_dialog(window) -> None:
    path_str, _ = QFileDialog.getSaveFileName(
        window,
        "Save processing settings",
        str(DEFAULT_PROCESSING_PATH),
        "JSON files (*.json)",
    )
    if not path_str:
        return
    settings = current_processing_settings(window)
    save_processing_settings(settings, Path(path_str))
    save_processing_settings(settings)
    window.statusBar().showMessage(f"Saved processing settings to {path_str}")
    window._logger.info("Processing settings saved to %s", Path(path_str).name)


def load_processing_settings_dialog(window) -> None:
    path_str, _ = QFileDialog.getOpenFileName(
        window,
        "Load processing settings",
        str(DEFAULT_PROCESSING_PATH),
        "JSON files (*.json)",
    )
    if not path_str:
        return
    settings = load_processing_settings(Path(path_str))
    window._processing_settings = settings
    apply_processing_settings_to_widgets(window, settings)
    save_processing_settings(settings)
    window.recompute_metrics()
    window.statusBar().showMessage(f"Loaded processing settings from {path_str}")
    window._logger.info("Processing settings loaded from %s", Path(path_str).name)


def build_processing_group(window) -> QFrame:
    processing_group = QFrame()
    processing_layout = QFormLayout(processing_group)
    processing_layout.setHorizontalSpacing(12)
    processing_layout.setVerticalSpacing(8)

    range_row = QHBoxLayout()
    range_row.addWidget(QLabel("Min"))
    range_row.addWidget(window.range_min_spin)
    range_row.addSpacing(10)
    range_row.addWidget(QLabel("Max"))
    range_row.addWidget(window.range_max_spin)
    range_row.addStretch(1)
    range_label = QLabel("Range")
    processing_layout.addRow(range_label, range_row)

    processing_layout.addRow(QLabel("Baseline"), window.baseline_method_combo)

    smoothing_row = QHBoxLayout()
    smoothing_row.setContentsMargins(0, 0, 0, 0)
    smoothing_row.setSpacing(6)
    smoothing_row.addWidget(window.smoothing_method_combo, 1)
    smoothing_row.addWidget(window.smoothing_window_spin)
    processing_layout.addRow(QLabel("Spectral smoothing"), smoothing_row)

    temporal_row = QHBoxLayout()
    temporal_row.setContentsMargins(0, 0, 0, 0)
    temporal_row.setSpacing(6)
    temporal_row.addWidget(window.temporal_smoothing_spin)
    temporal_row.addStretch(1)
    processing_layout.addRow(QLabel("Temporal smoothing"), temporal_row)

    crop_row = QHBoxLayout()
    crop_row.setContentsMargins(0, 0, 0, 0)
    crop_row.setSpacing(6)
    crop_row.addWidget(window.crop_method_combo, 1)
    crop_row.addWidget(window.crop_fraction_spin)
    processing_layout.addRow(QLabel("Crop"), crop_row)

    fit_row = QHBoxLayout()
    fit_row.setContentsMargins(0, 0, 0, 0)
    fit_row.setSpacing(6)
    fit_row.addWidget(window.fit_method_combo, 1)
    fit_row.addWidget(window.fit_window_spin)
    processing_layout.addRow(QLabel("Fitting"), fit_row)

    poly_row = QHBoxLayout()
    poly_row.addWidget(window.poly_order_spin)
    poly_row.addWidget(window.poly_warning_label)
    poly_row.addStretch(1)
    processing_layout.addRow(QLabel("Poly order"), poly_row)

    analysis_row = QHBoxLayout()
    analysis_row.setContentsMargins(0, 0, 0, 0)
    analysis_row.setSpacing(6)
    analysis_row.addWidget(window.analysis_resolution_spin)
    analysis_row.addStretch(1)
    processing_layout.addRow(QLabel("Analysis resolution"), analysis_row)

    processing_layout.addRow(QLabel("Peak method"), window.peak_metric_combo)

    trace_box = QWidget()
    trace_layout = QVBoxLayout(trace_box)
    trace_layout.setContentsMargins(0, 0, 0, 0)
    trace_layout.setSpacing(2)
    trace_layout.addWidget(window.trace_peak_check)
    trace_layout.addWidget(window.trace_centroid_check)
    trace_layout.addWidget(window.trace_fwhm_check)
    trace_layout.addStretch(1)
    processing_layout.addRow(QLabel("Trace metrics"), trace_box)

    buttons = QWidget()
    buttons_layout = QHBoxLayout(buttons)
    buttons_layout.setContentsMargins(0, 0, 0, 0)
    buttons_layout.setSpacing(6)
    buttons_layout.addWidget(window.save_processing_button)
    buttons_layout.addWidget(window.load_processing_button)
    buttons_layout.addStretch(1)
    processing_layout.addRow(buttons)

    return processing_group
