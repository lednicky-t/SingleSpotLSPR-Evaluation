from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from platformdirs import user_config_dir


DEFAULT_PROCESSING_PATH = Path(user_config_dir("lspr-suite", appauthor=False)) / "lspr_evaluation_settings.json"


@dataclass(slots=True)
class ProcessingSettings:
    wavelength_min_nm: float = 400.0
    wavelength_max_nm: float = 900.0
    baseline_method: str = "none"
    smoothing_method: str = "none"
    smoothing_window: int = 5
    temporal_smoothing: int = 1
    crop_method: str = "fixed_width"
    crop_fraction: float = 0.7
    fit_method: str = "none"
    polynomial_order: int = 2
    fit_window_width_nm: float = 120.0
    analysis_resolution_nm: float = 0.001
    peak_tracking_mode: str = "peak_nm"
    trace_noise_window_s: float = 10.0
    trace_metrics: list[str] = field(default_factory=lambda: ["peak_nm", "centroid_nm"])


def _payload() -> dict[str, Any]:
    return {"processing": asdict(ProcessingSettings())}


def _read_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _payload()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else _payload()


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def save_processing_settings(settings: ProcessingSettings, path: Path = DEFAULT_PROCESSING_PATH) -> None:
    payload = _read_payload(path)
    payload["processing"] = asdict(settings)
    _write_payload(path, payload)


def load_processing_settings(path: Path = DEFAULT_PROCESSING_PATH) -> ProcessingSettings:
    payload = _read_payload(path)
    raw = payload.get("processing", {})
    defaults = asdict(ProcessingSettings())
    if isinstance(raw, dict):
        for key, value in raw.items():
            if key in defaults:
                defaults[key] = value
    defaults["baseline_method"] = str(defaults.get("baseline_method", "none") or "none")
    defaults["smoothing_method"] = str(defaults.get("smoothing_method", "none") or "none")
    defaults["crop_method"] = str(defaults.get("crop_method", "fixed_width") or "fixed_width")
    defaults["fit_method"] = str(defaults.get("fit_method", "none") or "none")
    defaults["peak_tracking_mode"] = str(defaults.get("peak_tracking_mode", "peak_nm") or "peak_nm")
    defaults["smoothing_window"] = max(1, int(defaults.get("smoothing_window", 5) or 5))
    defaults["temporal_smoothing"] = max(1, int(defaults.get("temporal_smoothing", 1) or 1))
    defaults["polynomial_order"] = max(1, int(defaults.get("polynomial_order", 2) or 2))
    defaults["analysis_resolution_nm"] = float(defaults.get("analysis_resolution_nm", 0.001) or 0.001)
    defaults["crop_fraction"] = float(np.clip(float(defaults.get("crop_fraction", 0.7) or 0.7), 0.05, 0.95))
    defaults["trace_noise_window_s"] = float(max(float(defaults.get("trace_noise_window_s", 10.0) or 10.0), 0.5))
    trace_metrics = defaults.get("trace_metrics")
    allowed = {"peak_nm", "centroid_nm", "fwhm_nm"}
    if isinstance(trace_metrics, list):
        filtered = [str(item) for item in trace_metrics if str(item) in allowed]
        defaults["trace_metrics"] = filtered or ["peak_nm", "centroid_nm"]
    else:
        defaults["trace_metrics"] = ["peak_nm", "centroid_nm"]
    return ProcessingSettings(**defaults)


def _finite_xy(wavelengths_nm: np.ndarray, spectrum: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(wavelengths_nm, dtype=float)
    y = np.asarray(spectrum, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask]


def _boxcar_smooth(values: np.ndarray, window: int) -> np.ndarray:
    window = max(1, int(window))
    if window <= 1 or values.size < 3:
        return values
    kernel = np.ones(window, dtype=float) / float(window)
    return np.convolve(values, kernel, mode="same")


def _gaussian_smooth(values: np.ndarray, window: int) -> np.ndarray:
    window = max(1, int(window))
    if window <= 1 or values.size < 3:
        return values
    radius = max(1, window // 2)
    x = np.arange(-radius, radius + 1, dtype=float)
    sigma = max(1.0, float(window) / 3.0)
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    kernel /= float(np.sum(kernel))
    return np.convolve(values, kernel, mode="same")


def apply_processing_to_spectrum(
    wavelengths_nm: np.ndarray,
    spectrum: np.ndarray,
    settings: ProcessingSettings,
) -> tuple[np.ndarray, np.ndarray]:
    x, y = _finite_xy(wavelengths_nm, spectrum)
    if x.size == 0:
        return x, y

    minimum = min(float(settings.wavelength_min_nm), float(settings.wavelength_max_nm))
    maximum = max(float(settings.wavelength_min_nm), float(settings.wavelength_max_nm))
    mask = (x >= minimum) & (x <= maximum)
    if np.any(mask):
        x = x[mask]
        y = y[mask]

    if y.size == 0:
        return x, y

    baseline_method = str(settings.baseline_method or "none").lower()
    if baseline_method == "minimum":
        y = y - float(np.nanmin(y))
    elif baseline_method == "median":
        y = y - float(np.nanmedian(y))

    smoothing_method = str(settings.smoothing_method or "none").lower()
    if smoothing_method == "boxcar":
        y = _boxcar_smooth(y, settings.smoothing_window)
    elif smoothing_method == "gaussian":
        y = _gaussian_smooth(y, settings.smoothing_window)

    crop_method = str(settings.crop_method or "fixed_width").lower()
    if crop_method == "threshold" and y.size:
        threshold = float(np.nanmax(y)) * float(settings.crop_fraction)
        mask = y >= threshold
        if np.count_nonzero(mask) >= 3:
            x = x[mask]
            y = y[mask]
    elif crop_method == "fixed_width" and y.size:
        target = float(settings.fit_window_width_nm)
        if target > 0 and np.isfinite(target):
            peak_index = int(np.nanargmax(y))
            peak_center = float(x[peak_index])
            half_width = target / 2.0
            mask = (x >= peak_center - half_width) & (x <= peak_center + half_width)
            if np.count_nonzero(mask) >= 3:
                x = x[mask]
                y = y[mask]

    return x, y


def apply_temporal_smoothing(values: np.ndarray, window: int) -> np.ndarray:
    window = max(1, int(window))
    values = np.asarray(values, dtype=float)
    if window <= 1 or values.size < 3:
        return values
    kernel = np.ones(window, dtype=float) / float(window)
    smoothed = np.convolve(np.nan_to_num(values, nan=np.nanmedian(values)), kernel, mode="same")
    return smoothed
