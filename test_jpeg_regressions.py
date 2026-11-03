"""JPEG streams stay compressed through EXIF orientation; resizing avoids re-encoding inflation."""

import tempfile
from pathlib import Path
import unittest
from PIL import Image, ImageOps
import fitz
from bakuri.conversion.pdf import to_pdf
from bakuri.compression.service import compress
from bakuri.application.control import JobControl


class JpegRegressionTests(unittest.TestCase):
    def test_all_exif_orientations_keep_original_stream_and_render_correctly(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            im = Image.new("RGB", (120, 80))
            for rect, color in [
                ((0, 0, 60, 40), "red"),
                ((60, 0, 120, 40), "green"),
                ((0, 40, 60, 80), "blue"),
                ((60, 40, 120, 80), "yellow"),
            ]:
                im.paste(color, rect)
            for orientation in range(1, 9):
                with self.subTest(orientation=orientation):
                    src, dest = root / "photo.jpeg", root / "photo.pdf"
                    exif = im.getexif()
                    exif[274] = orientation
                    im.save(src, quality=60, exif=exif)
                    to_pdf(src, dest)
                    with Image.open(src) as original:
                        expected = ImageOps.exif_transpose(original).convert("RGB")
                    with fitz.open(dest) as pdf:
                        self.assertEqual(
                            pdf.extract_image(pdf[0].get_images()[0][0])["image"], src.read_bytes()
                        )
                        pix = pdf[0].get_pixmap(dpi=150)
                        actual = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                        self.assertEqual(actual.size, expected.size)
                        for x, y in [
                            (actual.width // 4, actual.height // 4),
                            (3 * actual.width // 4, actual.height // 4),
                            (actual.width // 4, 3 * actual.height // 4),
                        ]:
                            self.assertLess(
                                max(
                                    abs(a - b)
                                    for a, b in zip(
                                        actual.getpixel((x, y)), expected.getpixel((x, y))
                                    )
                                ),
                                6,
                            )
                    self.assertLess(dest.stat().st_size, src.stat().st_size + 4096)

    def test_low_quality_jpeg_reduces_in_size_instead_of_resaving_at_quality_95(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            src = root / "photo.jpg"
            Image.effect_noise((1100, 800), 80).convert("RGB").save(src, quality=45, subsampling=2)
            before = src.read_bytes()
            with Image.open(src) as original:
                quantization = original.quantization
            control = JobControl()
            outputs = compress([src], profile="p80", control=control)
            self.assertEqual(control.rows[0]["status"], "저장 완료")
            self.assertLess(Path(outputs[0]).stat().st_size, len(before))
            with Image.open(outputs[0]) as result:
                self.assertEqual(result.size, (880, 640))
                self.assertEqual(result.quantization, quantization)
            self.assertEqual(src.read_bytes(), before)

    def test_multi_picture_jpeg_reports_why_it_is_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            src = Path(root) / "multiple.jpg"
            Image.new("RGB", (30, 20), "red").save(
                src, format="MPO", save_all=True, append_images=[Image.new("RGB", (30, 20), "blue")]
            )
            control = JobControl()
            self.assertEqual(compress([src], profile="p80", control=control), [])
            self.assertEqual(control.rows[0]["status"], "건너뜀")
            self.assertIn("JPEG/MPO", control.rows[0]["detail"])
