from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import yaml

from lspr_core import ExperimentPlan, ExperimentPlanStep, SuiteIdentity, retime_steps

from .models import LoadedExperimentPlan, LoadedSpectra


def _decode_scalar(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.generic):
        return value.item()
    return value


def _decode_array(values: np.ndarray) -> np.ndarray:
    if values.dtype.kind in {"S", "O", "U"}:
        return np.asarray([_decode_scalar(value) for value in values], dtype=object)
    return np.asarray(values)


def _attrs_dict(handle: h5py.Group | h5py.Dataset) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in handle.attrs.items():
        if isinstance(value, np.ndarray):
            result[key] = [_decode_scalar(item) for item in value.tolist()]
        else:
            result[key] = _decode_scalar(value)
    return result


def _collect_datasets(handle: h5py.Group | h5py.File) -> list[tuple[str, h5py.Dataset]]:
    datasets: list[tuple[str, h5py.Dataset]] = []

    def _visitor(name: str, obj: Any) -> None:
        if isinstance(obj, h5py.Dataset):
            datasets.append((name, obj))

    handle.visititems(_visitor)
    return datasets


def _dataset_array(dataset: h5py.Dataset) -> np.ndarray:
    data = dataset[...]
    if isinstance(data, np.ndarray):
        return _decode_array(data)
    return np.asarray(data)


def _read_dataset_table(dataset: h5py.Dataset) -> list[dict[str, Any]]:
    data = _dataset_array(dataset)
    columns_attr = dataset.attrs.get("columns")
    columns: list[str] | None = None
    if isinstance(columns_attr, np.ndarray):
        columns = [str(_decode_scalar(value)) for value in columns_attr.tolist()]
    elif isinstance(columns_attr, (list, tuple)):
        columns = [str(_decode_scalar(value)) for value in columns_attr]
    if data.ndim == 1:
        data = data.reshape((-1, 1))
    if data.ndim != 2:
        raise ValueError("Expected a 2D table dataset.")
    if columns is None:
        columns = [f"col_{index + 1}" for index in range(data.shape[1])]
    rows: list[dict[str, Any]] = []
    for row_values in data.tolist():
        row = {}
        for column, value in zip(columns, row_values, strict=False):
            row[column] = _decode_scalar(value)
        rows.append(row)
    return rows


def _normalize_column_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def _safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _try_read_csv_rows(path: Path) -> list[dict[str, Any]]:
    attempts = (
        ("utf-8", ";"),
        ("utf-8", ","),
        ("utf-8", "\t"),
        ("utf-16", ";"),
        ("utf-16", ","),
        ("utf-16", "\t"),
    )
    last_error: Exception | None = None
    for encoding, delimiter in attempts:
        try:
            text = path.read_text(encoding=encoding)
            reader = csv.DictReader(StringIO(text), delimiter=delimiter)
            if not reader.fieldnames or len(reader.fieldnames) < 2:
                continue
            rows = []
            for row in reader:
                if not any((value or "").strip() for value in row.values() if isinstance(value, str)):
                    continue
                rows.append({str(key): _decode_scalar(value).strip() if isinstance(_decode_scalar(value), str) else _decode_scalar(value) for key, value in row.items()})
            if rows:
                return rows
        except Exception as exc:  # pragma: no cover - fallback path
            last_error = exc
    if last_error is not None:
        raise last_error
    raise ValueError(f"Could not read CSV file: {path}")


def _standardize_plan_rows(rows: list[dict[str, Any]], *, source_format: str, path: Path) -> LoadedExperimentPlan:
    alias_map = {
        "id": "step",
        "step": "step",
        "time": "duration_s",
        "time_s": "duration_s",
        "duration": "duration_s",
        "duration_s": "duration_s",
        "start": "start_s",
        "start_s": "start_s",
        "end": "end_s",
        "end_s": "end_s",
        "description": "description",
        "descritption": "description",
        "comment": "description",
        "color": "color",
        "valve": "valve",
        "switch_position": "switch_position",
    }

    normalized_rows: list[dict[str, Any]] = []
    steps: list[ExperimentPlanStep] = []
    explicit_timing_flags: list[bool] = []
    notes: list[str] = []

    for index, raw_row in enumerate(rows, start=1):
        cleaned = {_normalize_column_name(str(key)): value for key, value in raw_row.items()}
        standardized = {alias_map.get(key, key): value for key, value in cleaned.items()}

        step_id = _safe_int(standardized.get("step"), index)
        start_s = _safe_float(standardized.get("start_s"))
        end_s = _safe_float(standardized.get("end_s"))
        duration_s = _safe_float(standardized.get("duration_s"))
        has_explicit_timing = np.isfinite(start_s) and np.isfinite(end_s)
        explicit_timing_flags.append(has_explicit_timing)
        if not np.isfinite(duration_s):
            duration_s = max(0.0, end_s - start_s) if has_explicit_timing else 0.0

        devices: dict[str, Any] = {}
        devices_value = standardized.get("devices")
        if isinstance(devices_value, dict):
            devices = dict(devices_value)
        elif isinstance(devices_value, str) and devices_value.strip():
            try:
                loaded = json.loads(devices_value)
                if isinstance(loaded, dict):
                    devices = loaded
            except Exception:
                devices = {"raw": devices_value}
        if "valve" in standardized and standardized.get("valve") not in (None, ""):
            devices["valve"] = str(standardized.get("valve", "") or "")
        if "switch_position" in standardized and standardized.get("switch_position") not in (None, ""):
            devices["switch_position"] = _safe_int(standardized.get("switch_position"), 1)

        comment = str(standardized.get("description", "") or "")
        color = str(standardized.get("color", "") or "")

        standardized_row = {
            "step": step_id,
            "start_s": start_s if has_explicit_timing else 0.0,
            "end_s": end_s if has_explicit_timing else duration_s,
            "duration_s": duration_s,
            "color": color,
            "description": comment,
            "valve": str(standardized.get("valve", "") or ""),
            "switch_position": _safe_int(standardized.get("switch_position"), 1) if standardized.get("switch_position") not in (None, "") else "",
            "devices_json": json.dumps(devices, sort_keys=True, default=str) if devices else "",
        }
        normalized_rows.append(standardized_row)
        steps.append(
            ExperimentPlanStep(
                id=step_id,
                label=f"Step {step_id}",
                start_s=standardized_row["start_s"],
                end_s=standardized_row["end_s"],
                color=color,
                comment=comment,
                devices=devices,
            )
        )

    if steps and not all(explicit_timing_flags):
        steps = retime_steps(steps)
        notes.append("Missing explicit timing was normalized from step durations.")
    elif steps and not all(step.end_s >= step.start_s for step in steps):
        steps = retime_steps(steps)
        notes.append("Non-monotonic timing was normalized from step durations.")

    core_plan = ExperimentPlan(
        identity=SuiteIdentity(
            app_name="singleLSPR Evaluation",
            app_version="0.1.0",
            format_name="LSPR Flow Plan",
            format_version=1,
        ),
        steps=steps,
    )

    ordered_rows: list[dict[str, Any]] = []
    for step in core_plan.ordered():
        match = next((row for row in normalized_rows if int(row["step"]) == int(step.id)), None)
        base = {
            "step": int(step.id),
            "start_s": float(step.start_s),
            "end_s": float(step.end_s),
            "duration_s": float(step.duration_s),
            "color": str(step.color or ""),
            "description": str(step.comment or ""),
            "valve": "",
            "switch_position": "",
            "devices_json": json.dumps(step.devices, sort_keys=True, default=str) if step.devices else "",
        }
        if match is not None:
            base["valve"] = match.get("valve", "")
            base["switch_position"] = match.get("switch_position", "")
            if not base["devices_json"]:
                base["devices_json"] = match.get("devices_json", "")
        ordered_rows.append(base)

    columns = [
        "step",
        "start_s",
        "end_s",
        "duration_s",
        "color",
        "description",
        "valve",
        "switch_position",
        "devices_json",
    ]
    return LoadedExperimentPlan(path=path, source_format=source_format, columns=columns, rows=ordered_rows, core_plan=core_plan, notes=notes)


def load_experiment_plan(path: str | Path) -> LoadedExperimentPlan:
    return _load_experiment_plan_impl(path)


def _parse_native_yaml_plan(path: Path) -> LoadedExperimentPlan:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        raise ValueError(f"Experiment plan file is empty: {path}")
    if isinstance(raw, list):
        rows = [dict(item) for item in raw if isinstance(item, dict)]
    elif isinstance(raw, dict):
        steps = raw.get("steps", [])
        if not isinstance(steps, list):
            raise ValueError(f"Invalid experiment plan steps payload: {path}")
        rows = [dict(item) for item in steps if isinstance(item, dict)]
    else:
        raise ValueError(f"Unsupported YAML experiment plan structure: {path}")

    for index, row in enumerate(rows, start=1):
        row.setdefault("step", row.get("id", index))
    return _standardize_plan_rows(rows, source_format="yaml", path=path)


def _parse_legacy_csv_plan(path: Path) -> LoadedExperimentPlan:
    rows = _try_read_csv_rows(path)
    return _standardize_plan_rows(rows, source_format="csv", path=path)


def _parse_experiment_plan_from_hdf5(path: Path) -> LoadedExperimentPlan:
    with h5py.File(path, "r") as handle:
        candidates = [
            "plans/experiment_plan",
            "metadata/experiment_plan",
            "metadata/experiment_plan_tmp",
            "flow/experiment_plan",
        ]
        for candidate in candidates:
            if candidate in handle:
                dataset = handle[candidate]
                rows = _read_dataset_table(dataset)
                return _standardize_plan_rows(rows, source_format="hdf5", path=path)
    raise FileNotFoundError("No embedded experiment plan table was found in the HDF5 file.")


def _load_experiment_plan_impl(path: str | Path) -> LoadedExperimentPlan:
    path = Path(path)
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix in {".h5", ".hdf5"}:
        return _parse_experiment_plan_from_hdf5(path)
    if name.endswith(".flow.yaml") or suffix in {".yaml", ".yml"}:
        return _parse_native_yaml_plan(path)
    if suffix in {".csv", ".txt"}:
        return _parse_legacy_csv_plan(path)
    raise ValueError(f"Unsupported experiment plan file type: {path.suffix}")


def _score_wavelength_candidate(name: str, dataset: h5py.Dataset, *, expected_len: int | None = None) -> float:
    if dataset.ndim != 1 or dataset.dtype.kind not in "biufc":
        return float("-inf")
    score = 0.0
    lower = name.lower()
    if "wavelength" in lower:
        score += 100.0
    if "wl" == lower or lower.endswith("_wl"):
        score += 20.0
    if "nm" in lower:
        score += 10.0
    units = _decode_scalar(dataset.attrs.get("units", ""))
    if isinstance(units, str) and "nm" in units.lower():
        score += 80.0
    if expected_len is not None and dataset.shape[0] == expected_len:
        score += 40.0
    return score


def _score_spectra_candidate(name: str, dataset: h5py.Dataset, *, wavelength_len: int | None = None) -> float:
    if dataset.ndim != 2 or dataset.dtype.kind not in "biufc":
        return float("-inf")
    score = 0.0
    lower = name.lower()
    if "raw_spectra" in lower:
        score += 100.0
    if "intensity" in lower:
        score += 90.0
    if "spectra" in lower:
        score += 60.0
    if "extinction" in lower:
        score += 40.0
    if "processed" in lower:
        score -= 10.0
    if wavelength_len is not None:
        if dataset.shape[1] == wavelength_len:
            score += 50.0
        if dataset.shape[0] == wavelength_len:
            score += 45.0
    return score


def _score_time_candidate(name: str, dataset: h5py.Dataset, *, sample_count: int | None = None) -> float:
    if dataset.ndim != 1 or dataset.dtype.kind not in "biufc":
        return float("-inf")
    score = 0.0
    lower = name.lower()
    if "time_series" in lower:
        score += 100.0
    if lower.endswith("t_ms") or lower.endswith("_ms"):
        score += 70.0
    if "time" in lower:
        score += 40.0
    if sample_count is not None and dataset.shape[0] == sample_count:
        score += 40.0
    return score


def _orient_spectra_matrix(matrix: np.ndarray, wavelength_len: int | None, time_len: int | None) -> np.ndarray:
    if matrix.ndim != 2:
        raise ValueError("Spectrum matrix must be 2D.")
    if wavelength_len is not None:
        if matrix.shape[1] == wavelength_len:
            return matrix
        if matrix.shape[0] == wavelength_len:
            return matrix.T
    if time_len is not None:
        if matrix.shape[0] == time_len:
            return matrix
        if matrix.shape[1] == time_len:
            return matrix.T
    if matrix.shape[0] <= matrix.shape[1]:
        return matrix
    return matrix.T


def _decode_time_axis(time_values: np.ndarray, *, dataset_name: str, attrs: dict[str, Any]) -> np.ndarray:
    values = np.asarray(time_values, dtype=float)
    units = str(attrs.get("units", "")).lower()
    name = dataset_name.lower()
    if "ms" in name or "millisecond" in units or units == "ms":
        return values / 1000.0
    return values


def _load_embedded_experiment_plan(handle: h5py.File) -> LoadedExperimentPlan | None:
    candidates = [
        "plans/experiment_plan",
        "metadata/experiment_plan",
        "metadata/experiment_plan_tmp",
        "flow/experiment_plan",
    ]
    for candidate in candidates:
        if candidate in handle:
            try:
                rows = _read_dataset_table(handle[candidate])
                return _standardize_plan_rows(rows, source_format="hdf5", path=Path(handle.filename or ""))
            except Exception:
                continue
    return None


def load_spectra_file(path: str | Path) -> LoadedSpectra:
    path = Path(path)
    with h5py.File(path, "r") as handle:
        datasets = _collect_datasets(handle)
        dataset_map = {name: dataset for name, dataset in datasets}

        spectra_name = ""
        wavelength_name = ""
        time_name = ""
        time_dataset: h5py.Dataset | None = None

        scores: list[tuple[float, str, h5py.Dataset]] = []
        for name, dataset in datasets:
            scores.append((_score_spectra_candidate(name, dataset), name, dataset))
        scores.sort(key=lambda item: item[0], reverse=True)
        if not scores or scores[0][0] == float("-inf"):
            raise ValueError(f"No numeric spectrum matrix found in {path}")
        _, spectra_name, spectra_dataset = scores[0]
        raw_matrix = np.asarray(spectra_dataset[...], dtype=float)
        if raw_matrix.ndim == 1:
            raw_matrix = raw_matrix.reshape((1, -1))
        if raw_matrix.ndim != 2:
            raise ValueError(f"Unsupported spectrum matrix shape in {path}: {raw_matrix.shape}")

        wavelength_scores: list[tuple[float, str, h5py.Dataset]] = []
        for name, dataset in datasets:
            wavelength_scores.append((_score_wavelength_candidate(name, dataset, expected_len=raw_matrix.shape[1]), name, dataset))
        wavelength_scores.sort(key=lambda item: item[0], reverse=True)
        if wavelength_scores and wavelength_scores[0][0] > float("-inf"):
            _, wavelength_name, wavelength_dataset = wavelength_scores[0]
            wavelengths_nm = np.asarray(wavelength_dataset[...], dtype=float)
        else:
            wavelengths_nm = np.arange(raw_matrix.shape[1], dtype=float)

        time_scores: list[tuple[float, str, h5py.Dataset]] = []
        for name, dataset in datasets:
            time_scores.append((_score_time_candidate(name, dataset, sample_count=raw_matrix.shape[0]), name, dataset))
        time_scores.sort(key=lambda item: item[0], reverse=True)
        if time_scores and time_scores[0][0] > float("-inf"):
            _, time_name, time_dataset = time_scores[0]
            raw_time = np.asarray(time_dataset[...], dtype=float)
        else:
            raw_time = np.arange(raw_matrix.shape[0], dtype=float)

        spectra = _orient_spectra_matrix(raw_matrix, len(wavelengths_nm) if len(wavelengths_nm) else None, len(raw_time))
        if spectra.shape[1] != len(wavelengths_nm):
            if spectra.shape[0] == len(wavelengths_nm):
                spectra = spectra.T
            else:
                wavelengths_nm = np.arange(spectra.shape[1], dtype=float)

        if raw_time.shape[0] == spectra.shape[0]:
            time_s = _decode_time_axis(raw_time, dataset_name=time_name, attrs=_attrs_dict(time_dataset) if time_dataset is not None else {})
        elif raw_time.shape[0] == spectra.shape[1]:
            time_s = _decode_time_axis(raw_time, dataset_name=time_name, attrs=_attrs_dict(time_dataset) if time_dataset is not None else {})
            spectra = spectra.T
        else:
            time_s = np.arange(spectra.shape[0], dtype=float)

        peak_nm: np.ndarray | None = None
        for candidate in ("data/peak_position_nm", "processed/metrics/peak_nm", "peak_nm"):
            if candidate in dataset_map:
                candidate_values = np.asarray(dataset_map[candidate][...], dtype=float)
                if candidate_values.shape[0] == spectra.shape[0]:
                    peak_nm = candidate_values
                    break

        embedded_plan = _load_embedded_experiment_plan(handle)
        notes: list[str] = []
        if embedded_plan is not None:
            notes.append("Embedded experiment plan loaded from HDF5 metadata.")

        return LoadedSpectra(
            path=path,
            wavelengths_nm=np.asarray(wavelengths_nm, dtype=float),
            time_s=np.asarray(time_s, dtype=float),
            spectra=np.asarray(spectra, dtype=float),
            root_metadata=_attrs_dict(handle),
            spectra_path=spectra_name,
            wavelength_path=wavelength_name,
            time_path=time_name,
            peak_nm=peak_nm,
            embedded_experiment_plan=embedded_plan,
            notes=notes,
        )



