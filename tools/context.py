"""Bounded feature map or one AST symbol, without reading the whole repository."""

import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = {
    "convert": (
        "bakuri/domain/formats.py",
        "bakuri/domain/models.py",
        "bakuri/application/runner.py",
        "bakuri/conversion/service.py",
    ),
    "pdf": (
        "bakuri/conversion/pdf.py",
        "image_inputs.py",
        "pdf_pages.py",
        "test_pdf_pages.py",
        "test_conversion_fixes.py",
    ),
    "office": (
        "bakuri/conversion/office.py",
        "hancom_images.py",
        "hancom_merge.py",
        "test_spreadsheets.py",
        "test_word_slides.py",
    ),
    "compress": (
        "bakuri/compression/profiles.py",
        "bakuri/compression/service.py",
        "bakuri/compression/images.py",
        "bakuri/compression/pdf.py",
        "test_compression.py",
    ),
    "rename": (
        "bakuri/domain/rename_rules.py",
        "bakuri/domain/models.py",
        "bakuri/renaming/planner.py",
        "bakuri/renaming/transaction.py",
        "rename_ui.py",
        "test_rename.py",
    ),
    "window": (
        "bakuri/ui/main_view.py",
        "bakuri/ui/main_window.py",
        "file_list.py",
        "bakuri/ui/file_reorder.py",
        "test_file_reorder.py",
        "file_names.py",
        "test_ui.py",
        "test_development6.py",
    ),
    "popup": (
        "bakuri/ui/quick_popup.py",
        "popup_motion.py",
        "windows.py",
        "test_hotkey.py",
        "test_popup_motion.py",
    ),
    "jobs": (
        "bakuri/domain/models.py",
        "bakuri/application/runner.py",
        "bakuri/application/control.py",
        "bakuri/ui/results.py",
        "bakuri/ui/completion_toast.py",
        "test_application.py",
    ),
    "settings": (
        "bakuri/application/settings.py",
        "bakuri/ui/settings_store.py",
        "settings_ui.py",
        "build_channel.py",
    ),
    "release": (
        "build_dev.ps1",
        ".github/workflows/development.yml",
        "prepare_source.py",
        "verify_development.py",
        "build_channel.py",
    ),
    "update": ("updater.py", "update_source.py", "update_transport.py", "test_updater.py"),
}


def symbols(source):
    for node in ast.parse(source).body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        yield node.name + "." + child.name, child


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature", choices=ROUTES)
    parser.add_argument("--symbol", help="Exact function/class name, e.g. Window.begin_job")
    args = parser.parse_args()
    found = False
    for name in ROUTES[args.feature]:
        path = ROOT / name
        source = path.read_text(encoding="utf-8")
        entries = list(symbols(source)) if path.suffix == ".py" else []
        if args.symbol:
            for symbol, node in entries:
                if symbol == args.symbol:
                    # Avoid accidental full-module/class dumps: explicitly select a method.
                    lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
                    if len(lines) > 200:
                        parser.error(
                            "Symbol exceeds 200 lines; select a method or inspect a line range."
                        )
                    print(f"{name}:{node.lineno}\n" + "\n".join(lines))
                    found = True
        else:
            top = ", ".join(f"{key}:{node.lineno}" for key, node in entries if "." not in key)
            print(f"{name} ({len(source.splitlines())} lines) {top}")
    if args.symbol and not found:
        parser.error("Symbol not found in feature files; run without --symbol to see the map.")


if __name__ == "__main__":
    main()
