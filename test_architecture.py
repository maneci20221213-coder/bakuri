"""Prevent dependency regressions and incomplete source packages."""

import ast
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from prepare_source import create_source

ROOT = Path(__file__).resolve().parent


class ArchitectureTests(unittest.TestCase):
    def test_domain_imports_without_loading_gui_or_backends(self):
        script = """import sys
from bakuri.domain.formats import can_convert
from bakuri.domain.models import ConversionRequest
from bakuri.domain.rename_rules import fill_down
assert can_convert('a.png', 'pdf')
assert fill_down('same', 3) == ['same'] * 3
assert not any(n.split('.')[0] in {'PySide6','PIL','fitz','pymupdf','pythoncom','win32com'} for n in sys.modules)
"""
        subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_non_ui_packages_never_import_ui_or_legacy_facades(self):
        forbidden = {
            "app",
            "engine",
            "compression",
            "jobs",
            "rename_engine",
            "file_list",
            "rename_ui",
            "work_ui",
            "settings_ui",
            "PySide6",
        }
        for folder in ["domain", "application", "conversion", "compression", "renaming"]:
            for path in (ROOT / "bakuri" / folder).glob("*.py"):
                for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                    names = (
                        [a.name for a in node.names]
                        if isinstance(node, ast.Import)
                        else (
                            [node.module or ""]
                            if isinstance(node, ast.ImportFrom) and node.level == 0
                            else []
                        )
                    )
                    for name in names:
                        self.assertNotIn(name.split(".")[0], forbidden, str(path))
                        self.assertFalse(name.startswith("bakuri.ui"), str(path))

    def test_source_zip_contains_package_and_guides_without_caches(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, content in {
                "app.py": "entry",
                "pyproject.toml": "config",
                "requirements-dev.txt": "tools",
                "AGENTS.md": "map",
                "bakuri/domain/models.py": "records",
                "tools/context.py": "index",
                "docs/ARCHITECTURE.md": "guide",
                "bakuri/__pycache__/models.pyc": "cache",
                "dist/private.txt": "not source",
            }.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            with zipfile.ZipFile(create_source(root)) as archive:
                names = set(archive.namelist())
                for name in [
                    "bakuri/domain/models.py",
                    "tools/context.py",
                    "docs/ARCHITECTURE.md",
                    "AGENTS.md",
                    "pyproject.toml",
                    "requirements-dev.txt",
                ]:
                    self.assertIn("Bakuri/" + name, names)
                self.assertFalse(any("__pycache__" in n or "/dist/" in n for n in names))

    def test_context_tool_outputs_only_requested_symbol(self):
        process = subprocess.run(
            [sys.executable, "tools/context.py", "jobs", "--symbol", "run_job"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertIn("def run_job(", process.stdout)
        self.assertNotIn("class JobControl", process.stdout)
        self.assertLess(len(process.stdout), 4000)
