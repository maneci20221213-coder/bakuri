"""CAD-escaped title block labels must render like their Unicode equivalents."""

import tempfile
import unittest
from pathlib import Path
import ezdxf
import fitz
from engine import convert
from bakuri.conversion.cad import decode_cad_text


class CadTitleTests(unittest.TestCase):
    def test_codes_decode_without_losing_mtext_commands_or_literal_backslashes(self):
        self.assertEqual(decode_cad_text(r"\U+ACF5\U+C0AC\U+BA85"), "공사명")
        self.assertEqual(
            decode_cad_text(r"{\fMalgun Gothic|b0;\U+B0A0\U+C9DC}\P2026"),
            r"{\fMalgun Gothic|b0;날짜}\P2026",
        )
        for literal in (r"\\U+ACF5", r"\U+ZZZZ", r"\U+ABC", r"\U+D800", "DATE 2026"):
            self.assertEqual(decode_cad_text(literal), literal)

    def test_title_block_text_attributes_and_mtext_match_real_korean(self):
        from ezdxf.fonts import fonts

        manager = fonts.font_manager
        if not any(
            manager.has_font(name)
            for name in (
                "malgun.ttf",
                "malgunbd.ttf",
                "gulim.ttc",
                "batang.ttc",
                "NotoSansCJK-Regular.ttc",
            )
        ):
            self.skipTest("No Korean CAD fallback font installed")

        with tempfile.TemporaryDirectory() as directory:
            renders = []
            for encoded in (False, True):

                def label(value):
                    if not encoded:
                        return value
                    return "".join(r"\U+%04X" % ord(c) if ord(c) > 127 else c for c in value)

                doc = ezdxf.new("R2018")
                doc.styles.new("TITLE", dxfattribs={"font": "missing-title-font.shx"})
                space = doc.modelspace()
                space.add_lwpolyline([(0, 0), (65, 0), (65, 100), (0, 100)], close=True)
                space.add_text(
                    label("공사명"), dxfattribs={"insert": (2, 92), "height": 3, "style": "TITLE"}
                )
                block = doc.blocks.new("TITLE_BLOCK")
                block.add_attdef(
                    "HEADING",
                    (0, 0),
                    text=label("도면번호"),
                    dxfattribs={"height": 3, "style": "TITLE", "flags": 2},
                )
                insert = space.add_blockref("TITLE_BLOCK", (2, 55))
                insert.add_attrib(
                    "NAME", label("도면명"), (2, 75), dxfattribs={"height": 3, "style": "TITLE"}
                )
                space.add_mtext(
                    r"{\fMissing CAD Font|b0;" + label("날짜") + r"}\P2026년 11월",
                    dxfattribs={"insert": (2, 45), "char_height": 3, "width": 60, "style": "TITLE"},
                )
                attribute = insert.add_attrib("MULTILINE", "", (2, 25))
                mtext = ezdxf.entities.MText.new(
                    dxfattribs={"insert": (2, 25), "char_height": 3, "width": 60, "style": "TITLE"}
                )
                mtext.text = label("작성자") + r"\P" + label("확인자")
                attribute.set_mtext(mtext)
                source = Path(directory) / f"title-{encoded}.dxf"
                doc.saveas(source)
                original = source.read_bytes()
                with fitz.open(convert([source], "pdf")[0]) as pdf:
                    renders.append(pdf[0].get_pixmap().samples)
                self.assertEqual(source.read_bytes(), original)
            self.assertEqual(renders[0], renders[1])
