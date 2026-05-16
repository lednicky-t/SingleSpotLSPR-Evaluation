from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .processing import ProcessingSettings, apply_processing_to_spectrum, apply_temporal_smoothing


METRIC_COLUMNS = ["peak_nm", "centroid_nm", "fwhm_nm"]
METRIC_LABELS = {
    "peak_nm": "Peak position",
    "centroid_nm": "Centroid",
    "fwhm_nm": "FWHM",
}


@dataclass(slots=True)
class SpectrumMetrics:
    peak_nm: float
    centroid_nm: float
    fwhm_nm: float
    peak_value: float


def _finite_xy(wavelengths_nm: np.ndarray, spectrum: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(wavelengths_nm, dtype=float)
    y = np.asarray(spectrum, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask]


def compute_peak_nm(wavelengths_nm: np.ndarray, spectrum: np.ndarray) -> tuple[float, float]:
    x, y = _finite_xy(wavelengths_nm, spectrum)
    if x.size == 0:
        return float("nan"), float("nan")
    index = int(np.nanargmax(y))
    return float(x[index]), float(y[index])


def compute_centroid_nm(wavelengths_nm: np.ndarray, spectrum: np.ndarray) -> float:
    x, y = _finite_xy(wavelengths_nm, spectrum)
    if x.size == 0:
        return float("nan")
    shifted = y - np.nanmin(y)
    weights = np.clip(shifted, 0.0, None)
    total = float(np.nansum(weights))
    if total <= 0.0:
        return float("nan")
    return float(np.nansum(x * weights) / total)


def compute_fwhm_nm(wavelengths_nm: np.ndarray, spectrum: np.ndarray) -> float:
    x, y = _finite_xy(wavelengths_nm, spectrum)
    if x.size < 3:
        return float("nan")
    shifted = y - np.nanmin(y)
    peak_index = int(np.nanargmax(shifted))
    peak_value = float(shifted[peak_index])
    if peak_value <= 0.0:
        return float("nan")
    half_height = peak_value / 2.0

    left = None
    for index in range(peak_index, 0, -1):
        y0 = shifted[index - 1]
        y1 = shifted[index]
        if (y0 <= half_height <= y1) or (y1 <= half_height <= y0):
            if y1 == y0:
                left = float(x[index])
            else:
                fraction = (half_height - y0) / (y1 - y0)
                left = float(x[index - 1] + fraction * (x[index] - x[index - 1]))
            break

    right = None
    for index in range(peak_index, x.size - 1):
        y0 = shifted[index]
        y1 = shifted[index + 1]
        if (y0 >= half_height >= y1) or (y1 >= half_height >= y0):
            if y1 == y0:
                right = float(x[index])
            else:
                fraction = (half_height - y0) / (y1 - y0)
                right = float(x[index] + fraction * (x[index + 1] - x[index]))
            break

    if left is None or right is None or right <= left:
        return float("nan")
    return float(right - left)


def compute_spectrum_metrics(wavelengths_nm: np.ndarray, spectrum: np.ndarray) -> SpectrumMetrics:
    peak_nm, peak_value = compute_peak_nm(wavelengths_nm, spectrum)
    centroid_nm = compute_centroid_nm(wavelengths_nm, spectrum)
    fwhm_nm = compute_fwhm_nm(wavelengths_nm, spectrum)
    return SpectrumMetrics(
        peak_nm=peak_nm,
        centroid_nm=centroid_nm,
        fwhm_nm=fwhm_nm,
        peak_value=peak_value,
    )


def build_metrics_rows(
    wavelengths_nm: np.ndarray,
    spectra: np.ndarray,
    time_s: np.ndarray,
    processing: ProcessingSettings | None = None,
) -> list[dict[str, float]]:
    wavelengths_nm = np.asarray(wavelengths_nm, dtype=float)
    spectra = np.asarray(spectra, dtype=float)
    time_s = np.asarray(time_s, dtype=float)
    settings = processing or ProcessingSettings()

    rows: list[dict[str, float]] = []
    for index in range(min(len(spectra), len(time_s))):
        processed_wavelengths, processed_spectrum = apply_processing_to_spectrum(wavelengths_nm, spectra[index], settings)
        metrics = compute_spectrum_metrics(processed_wavelengths, processed_spectrum)
        rows.append(
            {
                "index": int(index),
                "time_s": float(time_s[index]),
                "peak_nm": float(metrics.peak_nm),
                "centroid_nm": float(metrics.centroid_nm),
                "fwhm_nm": float(metrics.fwhm_nm),
                "peak_value": float(metrics.peak_value),
            }
        )
    if rows and settings.temporal_smoothing > 1:
        peak_values = np.asarray([row["peak_nm"] for row in rows], dtype=float)
        centroid_values = np.asarray([row["centroid_nm"] for row in rows], dtype=float)
        fwhm_values = np.asarray([row["fwhm_nm"] for row in rows], dtype=float)
        rows_peak = apply_temporal_smoothing(peak_values, settings.temporal_smoothing)
        rows_centroid = apply_temporal_smoothing(centroid_values, settings.temporal_smoothing)
        rows_fwhm = apply_temporal_smoothing(fwhm_values, settings.temporal_smoothing)
        for index, row in enumerate(rows):
            row["peak_nm"] = float(rows_peak[index])
            row["centroid_nm"] = float(rows_centroid[index])
            row["fwhm_nm"] = float(rows_fwhm[index])
    return rows
