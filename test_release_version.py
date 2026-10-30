"""Windows numeric metadata retains the exact beta display version."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import build_metadata

class ReleaseVersionTests(unittest.TestCase):
    def test_beta_and_stable_metadata(self):
        for version, flags in [("1.0.0-beta.1", "0x2"), ("1.0.0", "0x0")]:
            with self.subTest(version=version), tempfile.TemporaryDirectory() as root:
                with patch.object(build_metadata, "VERSION", version):
                    data = build_metadata.generate(Path(root)).read_text(encoding="utf-8")
                self.assertIn("filevers=(1, 0, 0, 0)", data)
                self.assertIn(f"flags={flags}", data)
                self.assertIn(repr(version), data)
