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

MIT License, Copyright (c) 2026 Tomáš Lednický — see [`LICENSE`](LICENSE). Free to use, also commercially. If you use this app to produce results in a
publication, thesis or report, please cite it and name it in the acknowledgements. It is provided "as is" and is not validated for diagnostic or
clinical use; the full disclaimer and the third-party licences are in the Suite's [`NOTICE.md`](https://github.com/lednicky-t/LSPR-Suite/blob/main/NOTICE.md).

Citing: this app is part of [LSPR Suite](https://github.com/lednicky-t/LSPR-Suite) — see that repo's `CITATION.cff` for how to cite it.
