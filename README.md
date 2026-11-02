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

## License, citation and disclaimer

**Status: not started.** This repository is a placeholder. There is no usable app yet, so there is nothing to cite or to rely on.

MIT License, Copyright (c) 2026 Tomáš Lednický — see [`LICENSE`](LICENSE). Free to use, also commercially, provided "as is", without warranty.
Once the app exists it is part of [LSPR Suite](https://github.com/lednicky-t/LSPR-Suite): that repo's `CITATION.cff` says how to cite the Suite,
and its [`NOTICE.md`](https://github.com/lednicky-t/LSPR-Suite/blob/main/NOTICE.md) has the full disclaimer and the third-party licences.
