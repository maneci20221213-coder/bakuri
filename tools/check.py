"""Run a focused regression group; full discovery remains the CI requirement."""

import argparse
import os
from pathlib import Path
import subprocess
import sys

GROUPS = {
    "core": ["test_application", "test_architecture", "test_fill_down"],
    "convert": [
        "test_engine",
        "test_images",
        "test_conversion_fixes",
        "test_pdf_pages",
        "test_recent_engine",
        "test_merge_documents",
        "test_spreadsheets",
        "test_word_slides",
    ],
    "compress": ["test_compression", "test_ratios"],
    "rename": ["test_rename", "test_development2", "test_development4", "test_fill_down"],
    "window": [
        "test_ui",
        "test_development6",
        "test_user_help",
        "test_refactor",
        "test_completion_ui",
        "test_file_reorder",
    ],
    "popup": ["test_hotkey", "test_popup_motion", "test_ui"],
    "update": ["test_updater", "test_update_source"],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=[*GROUPS, "all"])
    args = parser.parse_args()
    tests = ["discover", "-v"] if args.group == "all" else ["-v", *GROUPS[args.group]]
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", BAKURI_DISABLE_SHELL_INTEGRATION="1")
    return subprocess.call(
        [sys.executable, "-m", "unittest", *tests], cwd=Path(__file__).resolve().parents[1], env=env
    )


if __name__ == "__main__":
    sys.exit(main())
