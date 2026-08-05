"""Validated import of simple delimited spectral tables."""
from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import numpy as np

from .models import LoadedSpectra


def load_delimited_spectra(path: str | Path) -> LoadedSpectra:
    """Load an explicit CSV/TSV matrix without silently reordering data.

    Supported layouts: ``wavelength_nm, signal`` or a time-series matrix with
    ``time_s`` as the first header and wavelength values in remaining headers.
    """
    source = Path(path)
    rows, delimiter = _read_rows(source)
    if len(rows) < 2:
        raise ValueError("A spectral table needs a header and at least one data row.")
    header = [cell.strip() for cell in rows[0]]
    normalized = [cell.lower().replace(" ", "_") for cell in header]
    data = np.asarray([_numbers(row, index + 2) for index, row in enumerate(rows[1:])], dtype=float)
    if len(header) == 2 and normalized[0] in {"wavelength", "wavelength_nm", "nm"}:
        wavelengths = data[:, 0]
        _validate_wavelengths(wavelengths)
        return LoadedSpectra(source, wavelengths, np.asarray([0.0]), data[:, 1].reshape(1, -1), spectra_path="delimited:single", wavelength_path="column:1", time_path="generated:0_s", notes=[f"Imported one spectrum from a {delimiter!r}-delimited table."])
    if len(header) < 4 or normalized[0] not in {"time", "time_s", "seconds", "elapsed_s"}:
        raise ValueError("Use 'wavelength_nm, signal' or a matrix headed 'time_s' followed by wavelength values in nm.")
    wavelengths = _numbers(header[1:], 1)
    _validate_wavelengths(wavelengths)
    if data.shape[1] != wavelengths.size + 1:
        raise ValueError("Each row must contain a time value and one signal value per wavelength.")
    time_s, spectra = data[:, 0], data[:, 1:]
    if not np.all(np.diff(time_s) >= 0):
        raise ValueError("Time values must be non-decreasing; spectra will not be reordered silently.")
    notes = [f"Imported {len(time_s)} spectra from a {delimiter!r}-delimited table."]
    if time_s[0] != 0.0:
        time_s = time_s - time_s[0]
        notes.append("Time values were rebased to the first spectrum (t = 0 s).")
    return LoadedSpectra(source, wavelengths, time_s, spectra, spectra_path="delimited:time_series", wavelength_path="header:columns_2+", time_path="column:1", notes=notes)


def _read_rows(path: Path) -> tuple[list[list[str]], str]:
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
        except (OSError, UnicodeDecodeError):
            continue
        try:
            delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\\t").delimiter
        except csv.Error:
            delimiter = "\\t" if path.suffix.lower() == ".tsv" else ","
        rows = [row for row in csv.reader(StringIO(text), delimiter=delimiter) if any(cell.strip() for cell in row)]
        if rows:
            return rows, delimiter
    raise ValueError(f"Could not read {path.name} as a delimited text table.")


def _numbers(values: list[str], row_number: int) -> np.ndarray:
    parsed = []
    for column, value in enumerate(values, 1):
        try:
            number = float(value.strip().replace(",", "."))
        except ValueError as exc:
            raise ValueError(f"Invalid number at row {row_number}, column {column}: {value!r}.") from exc
        if not np.isfinite(number):
            raise ValueError(f"Non-finite number at row {row_number}, column {column}: {value!r}.")
        parsed.append(number)
    return np.asarray(parsed, dtype=float)


def _validate_wavelengths(wavelengths: np.ndarray) -> None:
    if wavelengths.size < 3:
        raise ValueError("At least three wavelengths are required for analysis.")
    if not np.all(np.diff(wavelengths) > 0):
        raise ValueError("Wavelengths must be strictly increasing; values will not be reordered silently.")
