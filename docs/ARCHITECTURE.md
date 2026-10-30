# Python developer architecture (0.15.0-dev.8)

The conversion algorithms and runtime dependencies stay the same. This is a structural change, not a language or PDF-engine migration.

## Flow

`app.py` → `ui/startup.py` → main view/window → immutable request → `application/runner.py` → conversion/compression adapter → `JobReport` → result presenter.

`InputFile.file_id` survives sorting, rename and undo. The GUI captures paths/options before starting a worker; clearing the window cannot change an active request. Backend filesystems still validate sources at execution time; IDs do not replace file identity checks in rename transactions.

| Area | Responsibility | May depend on |
|---|---|---|
| domain | Formats, names, immutable records | Python standard library |
| application | Execute requests, cancel/progress, settings snapshots | domain; lazy conversion/compression adapters |
| conversion | Batch routing, PDF pixels, COM sessions | domain, JobControl, existing image/Hancom adapters |
| compression | Profiles, image/PDF optimization, per-file rows | domain, JobControl, diagnostics |
| renaming | Read-only preview, durable two-phase rename/undo | domain, filesystem storage |
| ui | Widgets, settings lifecycle, view composition, notifications | domain/application, existing UI/platform adapters |

`JobControl` owns publication and partial-result tracking. `run_job` converts control state to immutable reports even after an exception or cancellation. Legacy list/dict return values remain at adapter boundaries and compatibility APIs; compression dialogs still receive display dictionaries. Rename journal dictionaries stay JSON-compatible; `RenameOptions` defensively copies per-file mappings.

## Focused changes

- New output: support matrix + conversion owner + regression tests; no need to read popup animation or updater.
- Compression heuristic: `compression/images.py` or `pdf.py`; batch coordinator need not change.
- Popup: `ui/quick_popup.py`, `popup_motion.py`, relevant native-hook tests.
- Rename rule: pure `domain/rename_rules.py`; preview/storage/transaction have separate owners.
- UI placement: `ui/main_view.py`; no conversion code is embedded in layout.

`tools/context.py` prints file names, line counts and top-level symbols; `--symbol` limits source output to one function/method (maximum 200 lines). `tools/check.py` selects regression groups. These reduce unnecessary source/log context; they do not promise a fixed token-saving percentage. Keep this map current when ownership changes.

## Compatibility and remaining adapters

Root `engine.py`, `compression.py`, `jobs.py`, `rename_engine.py` only reexport historical APIs. Existing tests and external scripts can keep importing them. New code imports owners directly. `app.py` keeps executable/bootstrap behavior and UI reexports for existing verification scripts.

Existing `image_inputs.py`, `hancom_images.py`, `pdf_pages.py`, `hancom_merge.py`, `windows.py`, updater modules and small UI modules remain cohesive adapters at the root. Moving every file would create import churn without further separation of responsibilities. No second implementation, plugin container or runtime reflection registry was introduced.

## Validation and limits

Full unittest discovery is required on Windows CI, then PyInstaller developer build and native packaged-window startup. Source ZIPs include `bakuri/`, tools, guides and developer requirements; no caches/build products. Real Office/Hancom automation still needs a PC with those applications. This change does not promise fewer V3 alerts or faster conversion: the engines and packaging method are unchanged.
