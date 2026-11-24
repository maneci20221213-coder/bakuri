"""Real MPF fixtures, source preservation and shared conversion/compression routing."""

from dataclasses import replace
from pathlib import Path
import io
import struct
import tempfile
import unittest
from PIL import Image, TiffImagePlugin
import fitz
from bakuri.conversion.multi_image import inspect_multi_image, resolve_selections
from bakuri.domain.models import (
    InputFile,
    ConversionRequest,
    ConversionOptions,
    CompressionRequest,
    CompressionOptions,
)
from bakuri.application.control import JobControl
from bakuri.application.runner import execute, run_job


def make_mpo(path):
    images = []
    for index in range(2):
        image = Image.effect_noise((600, 400), 65).convert("RGB")
        image.paste(("red", "blue")[index], (0, 0, 100, 100))
        images.append(image)
    images[0].save(path, format="MPO", save_all=True, append_images=images[1:], quality=65)
    return path


def patch_entries(path, changes, prepend=b""):
    data = bytearray(path.read_bytes())
    with Image.open(path) as im:
        raw = im.info["mp"]
    stream = io.BytesIO(raw)
    head = stream.read(8)
    directory = TiffImagePlugin.ImageFileDirectory_v2(head)
    stream.seek(directory.next)
    directory.load(stream)
    offset = data.index(directory[0xB002], data.index(b"MPF\x00") + 4)
    endian = "<" if head.startswith(b"II") else ">"
    for frame, field, value in changes:
        struct.pack_into(endian + "L", data, offset + 16 * frame + field * 4, value)
    if prepend:
        size = struct.unpack_from(endian + "L", data, offset + 4)[0]
        struct.pack_into(endian + "L", data, offset + 4, size + len(prepend))
        data = data[:2] + prepend + data[2:]
    path.write_bytes(data)


class MultiImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = make_mpo(Path(self.temp.name) / "사진.jpg")
        self.files = (InputFile(str(self.path)),)
        self.info = inspect_multi_image(self.path)
        self.before = self.path.read_bytes()

    def choices(self, mode):
        return (replace(self.info, mode=mode),)

    def test_unknown_and_stereo_need_explicit_choice(self):
        self.assertEqual(self.info.count, 2)
        self.assertFalse(self.info.auxiliary)
        with self.assertRaises(ValueError):
            resolve_selections(self.files, ())
        for kind in (0x020002, 0x000000):
            patch_entries(self.path, [(1, 0, kind)])
            self.assertFalse(inspect_multi_image(self.path).auxiliary)

    def test_thumbnail_is_automatic(self):
        patch_entries(self.path, [(1, 0, 0x010001)])
        self.assertTrue(inspect_multi_image(self.path).auxiliary)
        control = JobControl()
        execute(ConversionRequest(self.files, "pdf"), control)
        self.assertEqual(len(control.outputs), 1)
        with fitz.open(control.outputs[0]) as doc:
            self.assertEqual(len(doc), 1)

    def test_ultra_hdr_marker_is_automatic_but_namespace_alone_is_not(self):
        prefix = b"http://ns.adobe.com/xap/1.0/\x00"
        for prop, expected in [(b"", False), (b' hdrgm:Version="1.0"', True)]:
            self.path.write_bytes(self.before)
            xml = (
                prefix
                + b'<x:xmpmeta xmlns:hdrgm="http://ns.adobe.com/hdr-gain-map/1.0/"'
                + prop
                + b"/>"
            )
            patch_entries(self.path, [], b"\xff\xe1" + struct.pack(">H", len(xml) + 2) + xml)
            self.assertEqual(inspect_multi_image(self.path).auxiliary, expected)
        control = JobControl()
        execute(ConversionRequest(self.files, "jpeg"), control)
        with Image.open(control.outputs[0]) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertNotIn("mp", image.info)
        self.assertNotIn(b"hdrgm:Version", Path(control.outputs[0]).read_bytes())

    def test_all_pdf_and_png_go_to_original_folder_without_merge(self):
        for fmt in ("pdf", "png"):
            control = JobControl()
            execute(
                ConversionRequest(
                    self.files,
                    fmt,
                    True,
                    ConversionOptions(output_mode="source"),
                    self.choices("all"),
                ),
                control,
            )
            self.assertEqual(
                [Path(p).name for p in control.outputs], [f"사진_01.{fmt}", f"사진_02.{fmt}"]
            )
            for i, path in enumerate(control.outputs):
                self.assertEqual(Path(path).parent, self.path.parent.resolve())
                if fmt == "pdf":
                    with fitz.open(path) as doc:
                        self.assertEqual(len(doc), 1)
                        raw = doc.extract_image(doc[0].get_images()[0][0])["image"]
                    image = Image.open(io.BytesIO(raw))
                    self.assertNotIn("mp", image.info)
                else:
                    image = Image.open(path)
                with image:
                    color = image.convert("RGB").getpixel((20, 20))
                    self.assertGreater(color[0 if i == 0 else 2], 230)
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_multi_image_outputs_follow_original_subfolder_and_pdf_orientation(self):
        control = JobControl()
        request = ConversionRequest(
            self.files,
            "pdf",
            options=ConversionOptions(orientation="landscape", output_mode="subfolder"),
            multi_images=self.choices("all"),
        )
        execute(request, control)
        self.assertEqual(len(control.outputs), 2)
        for output in control.outputs:
            self.assertEqual(Path(output).parent, self.path.parent.resolve() / "바꾸리 변환")
            with fitz.open(output) as pdf:
                self.assertEqual(pdf[0].rect, fitz.paper_rect("a4-l"))

    def test_representative_flag_can_choose_second_image(self):
        patch_entries(self.path, [(1, 0, 0x20000000)])
        info = inspect_multi_image(self.path)
        self.assertEqual(info.primary, 1)
        control = JobControl()
        execute(ConversionRequest(self.files, "png", multi_images=(info,)), control)
        self.assertEqual(Path(control.outputs[0]).name, "사진.png")
        with Image.open(control.outputs[0]) as image:
            self.assertGreater(image.getpixel((20, 20))[2], 230)

    def test_compress_savings_use_each_frame_and_original_source(self):
        control = JobControl()
        execute(
            CompressionRequest(self.files, CompressionOptions("p80"), self.choices("all")), control
        )
        self.assertEqual(
            [Path(p).name for p in control.outputs],
            ["사진_01_용량축소.jpeg", "사진_02_용량축소.jpeg"],
        )
        self.assertEqual(len(control.rows), 2)
        for row in control.rows:
            self.assertLess(row["before"], len(self.before))
            self.assertLess(row["after"], row["before"])
            self.assertEqual(row["source"], str(self.path.resolve()))
            self.assertIn("이미지", row["detail"])
            with Image.open(row["output"]) as image:
                self.assertEqual(image.size, (480, 320))
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_cancel_retains_completed_results_and_rows(self):
        control = JobControl()
        publish = control.publish

        def once(src, dest):
            path = publish(src, dest)
            control.cancel()
            return path

        control.publish = once
        request = CompressionRequest(self.files, multi_images=self.choices("all"))
        report = run_job(request, control, "compress", lambda e, c: str(e))
        self.assertEqual(report.outcome, "cancelled")
        self.assertEqual(len(report.paths), 1)
        self.assertEqual(len(report.rows), 1)
        self.assertTrue(Path(report.paths[0]).is_file())
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_changed_file_is_rejected_without_outputs(self):
        self.path.write_bytes(self.before + b"changed")
        with self.assertRaises(ValueError):
            execute(
                ConversionRequest(self.files, "pdf", multi_images=self.choices("primary")),
                JobControl(),
            )
        self.assertFalse(list(self.path.parent.glob("*.pdf")))

    def test_mpo_extension_and_normal_jpeg(self):
        from bakuri.domain.formats import can_convert

        source = self.path.with_suffix(".mpo")
        source.write_bytes(self.before)
        self.assertTrue(can_convert(source, "pdf"))
        self.assertEqual(inspect_multi_image(source).count, 2)
        image = self.path.with_name("normal.jpeg")
        Image.new("RGB", (30, 20)).save(image)
        self.assertIsNone(inspect_multi_image(image))
        self.assertEqual(resolve_selections((InputFile(str(image)),), ()), ())
