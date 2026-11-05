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

Full unittest discovery is required on Windows CI, native popup timer/focus checks, then PyInstaller developer build and native packaged-window startup. Source ZIPs include `bakuri/`, tools, guides and developer requirements; no caches/build products. Real Office/Hancom automation still needs a PC with those applications. This change does not promise fewer V3 alerts or faster conversion: the engines and packaging method are unchanged.

PDF page splitting uses `domain/pdf_selection.py` for pure 1-based input validation, `PdfPagesRequest` for the immutable worker boundary, `conversion/pdf_split.py` for native PDF page copying, and the shared `ui/pdf_split.py` dialog. It reuses JobControl, cancellation, collision-safe publication and completion reports. No raster rendering is used for splitting.

Multi-photo handling uses `ui/multi_image.py` for batch-local preflight choices, immutable `MultiImageSelection` values on requests, and `conversion/multi_image.py` for metadata classification and raw JPEG frame staging. Workers recheck file fingerprints and route independent frames through the existing converters/compressor with original-folder publication. Frame-size baselines prevent duplicate MPO savings, and JobReport notes retain the selection in completion notifications. Unknown frames never auto-classify from dimensions or camera brand.

## Sequential work queue

`ui/main_window.py` owns a FIFO of immutable requests and starts one worker at a time. New submissions capture paths/options immediately; editing or clearing the visible list does not change active or queued requests. Completion, cancellation and failures all advance the queue after the result presenter finishes. Current-job cancellation and clearing pending requests are separate actions. Rename is disabled while conversion runs to keep queued paths valid. The queue is in-memory and is not restored after exit.

`application/progress.py` estimates remaining time from monotonic elapsed time and measured backend progress; the one-second UI timer refreshes elapsed time, never fabricates percentages. External COM/CAD stages may not report finer progress. A completed estimate is shown only when the backend reports 100; successful completion also leaves the tray progress bar at 100.

CAD rendering decodes `\U+XXXX` text content at the text/MTEXT frontend boundary, including virtual block attributes, and uses the decoded characters for font fallback. MTEXT layout commands and escaped literal backslashes stay intact; source entities/files are not edited. `file_list.Files` restores manual column widths through a main-thread settings provider, with independent conversion/rename keys; automatic fitting fills available width only until a manual layout is saved. `merged_names.merged_path` uses the original first source folder when names have no common substring; temporary image staging passes its source-folder mapping through the converter.

CAD font fallback validates the effective font of each parsed MTEXT word, including nested font scopes, before measuring and drawing it; inter-word spacing uses the same face. The final text pipeline also validates glyph coverage. Missing Windows font-cache paths trigger one system-font rescan; absent Korean fonts cause an actionable failure instead of publishing missing-glyph squares. CAD progress reports expanded block entities and recorded PDF replay items through `JobControl.measure_units` and the Qt measurement signal. `ProgressEstimate` computes a rolling per-stage work estimate, marks unknown stages explicitly, and suppresses stale predictions; fixed phase weights are not elapsed-time percentages. Homogeneous CAD batches weight files by byte size.

Update UI retries on direct/tray/manual entry. Rejected offers are deduplicated only within a request, not for the entire process lifetime. Checks requested while busy are deferred; successful results received while hidden/busy remain pending until the visible window is idle. Automatic network errors stay silent, while an explicit manual check reports failure in the status line. The installed EXE is exercised twice by verify_update_ui.py (after Later/reopen) against the real public feed with an isolated, temporarily lowered SDK manifest, restored in finally.
