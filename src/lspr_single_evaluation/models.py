from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from lspr_core import ExperimentPlan


@dataclass(slots=True)
class LoadedSpectra:
    path: Path
    wavelengths_nm: np.ndarray
    time_s: np.ndarray
    spectra: np.ndarray
    root_metadata: dict[str, Any] = field(default_factory=dict)
    spectra_path: str = ""
    wavelength_path: str = ""
    time_path: str = ""
    peak_nm: np.ndarray | None = None
    embedded_experiment_plan: "LoadedExperimentPlan | None" = None
    notes: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines = [
            f"File: {self.path}",
            f"Spectra dataset: {self.spectra_path or 'n/a'}",
            f"Axis dataset: {self.wavelength_path or 'n/a'}",
            f"Time dataset: {self.time_path or 'n/a'}",
            f"Spectra shape: {tuple(self.spectra.shape)}",
        ]
        if len(self.time_s):
            lines.append(f"Time range: {float(self.time_s[0]):.3g} s to {float(self.time_s[-1]):.3g} s")
        if len(self.wavelengths_nm):
            lines.append(
                f"Wavelength range: {float(self.wavelengths_nm[0]):.3g} nm to {float(self.wavelengths_nm[-1]):.3g} nm"
            )
        if self.notes:
            lines.extend(f"Note: {note}" for note in self.notes)
        return lines

@dataclass(slots=True)
class LoadedExperimentPlan:
    path: Path
    source_format: str
    columns: list[str]
    rows: list[dict[str, Any]]
    core_plan: ExperimentPlan | None = None
    notes: list[str] = field(default_factory=list)

    def summary_lines(self) -> list[str]:
        lines = [
            f"File: {self.path}",
            f"Format: {self.source_format}",
            f"Steps: {len(self.rows)}",
        ]
        if self.rows:
            duration = 0.0
            for row in self.rows:
                value = row.get("duration_s", 0.0)
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    continue
                if np.isfinite(numeric):
                    duration += numeric
            lines.append(f"Total duration: {duration:.3g} s")
        if self.notes:
            lines.extend(f"Note: {note}" for note in self.notes)
        return lines
