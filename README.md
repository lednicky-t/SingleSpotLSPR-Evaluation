# singleLSPR Evaluation

This app is the suite-local starting point for offline single-spot LSPR evaluation.

## Current scope

- Load HDF5 spectra files from the acquisition app or older project variants.
- Load pump plans from `.flow.yaml`, `.yaml`, `.yml`, `.csv`, `.txt`, and embedded HDF5 tables.
- Compute peak position, centroid, and FWHM metrics.
- Plot the spectrum and the resulting sensorgram.

## Launch

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
lspr-single-evaluation
```

For VS Code "Run Python File", use [`run.py`](./run.py).
