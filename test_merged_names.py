"""Folder fallback refers to original inputs, including temporarily staged photos."""

import tempfile
import unittest
from pathlib import Path
import fitz
from engine import convert
from merged_names import merged_path


class FolderMergeNamesTests(unittest.TestCase):
    def test_common_name_wins_and_otherwise_first_source_folder_is_used(self):
        files = [Path("공사자료/one.pdf"), Path("참고/two.pdf")]
        self.assertEqual(merged_path(files, "pdf"), Path("공사자료/공사자료_통합본.pdf"))
        common = [Path("공사자료/단면도_1.pdf"), Path("참고/단면도_2.pdf")]
        self.assertEqual(merged_path(common, "pdf").name, "단면도_통합본.pdf")

    def test_staged_image_names_use_original_folder(self):
        folder = Path("temporary/0").resolve()
        inputs = [folder / "one.jpeg", folder / "two.jpeg"]
        result = merged_path(inputs, "hwpx", source_folders={folder: Path("원본사진")})
        self.assertEqual(result.name, "원본사진_통합본.hwpx")
        self.assertEqual(result.parent, folder)

    def test_merge_in_custom_output_folder_keeps_source_folder_name_and_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "설계도면"
            source.mkdir()
            paths = [source / "one.pdf", source / "two.pdf"]
            for path in paths:
                with fitz.open() as pdf:
                    pdf.new_page()
                    pdf.save(path)
            original = [path.read_bytes() for path in paths]
            target = Path(directory) / "저장위치"
            output = Path(
                convert(paths, "pdf", True, output_mode="custom", output_folder=str(target))[0]
            )
            self.assertEqual(output, target.resolve() / "설계도면_통합본.pdf")
            with fitz.open(output) as pdf:
                self.assertEqual(len(pdf), 2)
            self.assertEqual([path.read_bytes() for path in paths], original)
