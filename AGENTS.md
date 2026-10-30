# Bakuri development map

Windows file converter. Python 3.12, PySide6, Pillow, PyMuPDF; Office/Hancom COM on Windows.
`develop` is an isolated developer edition (F9); stable release is `main`. Keep settings/IPC/update channels isolated.

## Start small

- Read this file, then `python tools/context.py <feature>`; open only the owner and relevant tests.
- To read one method: `python tools/context.py window --symbol Window.begin_job`.
- Features: convert, pdf, office, compress, rename, window, popup, jobs, settings, release, update.
- `docs/ARCHITECTURE.md` explains boundaries; read it for structural changes, not every UI edit.
- Do not dump all source/tests or build outputs into context. Use `rg -n` and bounded line ranges.

## Owners

| Change | Owner |
|---|---|
| Supported formats | `bakuri/domain/formats.py` |
| Requests/results/options | `bakuri/domain/models.py` |
| Worker execution/cancellation/publication | `bakuri/application/` |
| Conversion routing / COM / PNG→PDF | `bakuri/conversion/service.py` / `office.py` / `pdf.py` |
| Compression routing / image / PDF | `bakuri/compression/` |
| Rename text rules / preview / filesystem transaction | `bakuri/domain/rename_rules.py` / `bakuri/renaming/` |
| Main layout / actions / quick menu / notifications | `bakuri/ui/main_view.py` / `main_window.py` / `quick_popup.py` / `results.py` |
| File list / rename panel / OS hooks / updater | `file_list.py` / `rename_ui.py` / `windows.py` / `updater.py` |

`app.py` is the entrypoint. `engine.py`, `compression.py`, `jobs.py`, `rename_engine.py` are import-only compatibility facades. New logic belongs in the owner, not the facade. Patch the implementation module in tests.

## Contracts

- Domain imports no Qt, Pillow, fitz or platform adapters. Workers never read widgets/QSettings.
- Freeze input IDs, ordered paths and options before starting a job; return `JobReport` through Qt signals.
- Preserve originals, avoid overwrites, retain completed outputs on cancellation; rename uses journal/rollback.
- Preserve PNG pixels/alpha, JPEG stream reuse and PDF paper geometry. Do not silently lower image quality.
- Show completion toast only; update checks stay disabled in developer builds.
- Existing root adapters are intentional; do not create one-line modules or general plugin frameworks.

## Validation

`python tools/check.py <core|convert|compress|rename|window|popup|update|all>`.
Run the relevant group while editing, full suite before pushing. Windows CI also checks the frozen executable.
`python -m black --check bakuri tools app.py engine.py compression.py jobs.py rename_engine.py file_list.py rename_ui.py work_ui.py prepare_source.py test_application.py test_architecture.py`.
Dev tools are in `requirements-dev.txt`, never runtime dependencies. Include packages in `prepare_source.py` when adding directories. Do not publish stable/tag/release for a developer-only request.
