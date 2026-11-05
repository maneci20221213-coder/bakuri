"""Run the staged Windows DWG converter against two upstream drawings."""

from pathlib import Path
import sys
import tarfile
from tempfile import TemporaryDirectory
from unittest.mock import patch

import fitz
from PIL import Image

from bakuri.conversion.service import convert

tools = Path(sys.argv[1]).resolve()
source = Path(sys.argv[2])
with (
    TemporaryDirectory() as directory,
    tarfile.open(source) as archive,
    patch("bakuri.conversion.cad.bundled_converter", return_value=tools / "dwg2dxf.exe"),
    patch("bakuri.conversion.cad.find_oda", side_effect=AssertionError("Unexpected ODA lookup")),
):
    folder = Path(directory) / "한글 경로"
    folder.mkdir()
    for version in ("2000", "2018"):
        drawing = folder / f"도면_{version}.dwg"
        fixture = archive.extractfile(f"libredwg-0.14/test/test-data/example_{version}.dwg")
        original = fixture.read()
        drawing.write_bytes(original)
        for kind in ("pdf", "png", "jpeg"):
            with patch("tempfile.tempdir", str(folder)):
                output = Path(convert([drawing], kind, dpi=96)[0])
            if kind == "pdf":
                with fitz.open(output) as pdf:
                    assert len(pdf) == 1 and len(pdf[0].get_drawings()) > 1
            else:
                with Image.open(output) as image:
                    assert image.convert("RGB").getextrema() != ((255, 255),) * 3
        assert drawing.read_bytes() == original
print("Bundled LibreDWG converted the DWG 2000 and 2018 fixtures to PDF, PNG and JPEG.")
