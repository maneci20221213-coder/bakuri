"""Render CAD model space to a fitted vector PDF."""

import os
from pathlib import Path
import re
from shutil import copyfile
import subprocess
from tempfile import TemporaryDirectory
import time

_CAD_UNICODE = re.compile(r"(?<!\\)\\U\+([0-9a-fA-F]{4})")


def decode_cad_text(text):
    """Decode CAD Unicode escapes without consuming MTEXT layout or literal slashes."""

    def replace(match):
        code = int(match[1], 16)
        return chr(code) if not 0xD800 <= code <= 0xDFFF else match[0]

    return _CAD_UNICODE.sub(replace, text)


class CadError(ValueError):
    """A CAD problem with a message the user can act on."""


def find_oda():
    candidates = []
    if os.name == "nt":
        import winreg

        key = r"Software\Microsoft\Windows\CurrentVersion\App Paths\ODAFileConverter.exe"
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as entry:
                        path, _ = winreg.QueryValueEx(entry, "")
                        candidates.append(Path(os.path.expandvars(path.strip('"'))))
                except (OSError, AttributeError, TypeError):
                    continue
    for variable in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        root = os.environ.get(variable)
        if root:
            folder = Path(root)
            for vendor in (folder / "ODA", folder / "Open Design Alliance", folder):
                if vendor != folder:
                    candidates.append(vendor / "ODAFileConverter.exe")
                for pattern in (
                    "ODAFileConverter*/ODAFileConverter.exe",
                    "ODA File Converter*/ODAFileConverter.exe",
                ):
                    candidates.extend(sorted(vendor.glob(pattern), reverse=True))
    return next(
        (
            path
            for path in candidates
            if path.is_absolute() and path.name.lower() == "odafileconverter.exe" and path.is_file()
        ),
        None,
    )


def bundled_converter():
    return Path(__file__).resolve().parents[2] / "cad_tools" / "dwg2dxf.exe"


def run_dwg_converter(args, converted, control, engine, cwd):
    try:
        process = subprocess.Popen(
            args,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as error:
        raise CadError(f"{engine} DWG 변환 도구를 실행하지 못했습니다.") from error
    with process:
        deadline = time.monotonic() + 120
        try:
            while process.poll() is None:
                if control:
                    control.check()
                if time.monotonic() >= deadline:
                    raise CadError(
                        "DWG 변환 시간이 초과됐습니다. DXF로 저장한 뒤 다시 시도해 주세요."
                    )
                time.sleep(0.1)
        finally:
            if process.poll() is None:
                process.kill()
    if process.returncode != 0 or not converted.is_file():
        raise CadError(
            f"{engine}에서 이 DWG를 읽지 못했습니다. CAD 프로그램에서 DXF로 저장한 뒤 다시 시도해 주세요."
        ) from RuntimeError(
            f"{engine} exit code: {process.returncode}; DXF exists: {converted.is_file()}"
        )


def read_dwg(source, control):
    import ezdxf

    oda = find_oda()
    bundled = bundled_converter()
    converters = []
    if oda is not None:
        converters.append(("ODA File Converter", oda))
    if bundled.is_file():
        converters.append(("LibreDWG", bundled))
    if not converters:
        raise CadError(
            "DWG 변환 도구가 없습니다. 바꾸리 설치 파일을 다시 받거나 DXF로 저장해 주세요."
        )

    for index, (engine, executable) in enumerate(converters):
        if control:
            control.check()
        try:
            return convert_dwg_with(source, control, engine, executable)
        except (CadError, ezdxf.DXFError):
            if index + 1 == len(converters):
                raise
            if control:
                control.notes.append("ODA에서 도면을 읽지 못해 LibreDWG로 다시 시도했습니다.")


def convert_dwg_with(source, control, engine, executable):
    import ezdxf

    with TemporaryDirectory(prefix="BakuriCAD-") as directory:
        inputs = Path(directory, "in")
        outputs = Path(directory, "out")
        inputs.mkdir()
        outputs.mkdir()
        staged = inputs / "drawing.dwg"
        converted = outputs / "drawing.dxf"
        copyfile(source, staged)
        cwd = executable.parent
        if engine == "LibreDWG":
            # The Windows build uses narrow C file APIs, so arguments stay ASCII.
            cwd = Path(directory)
            args = [
                str(executable),
                "-o",
                str(converted.relative_to(cwd)),
                str(staged.relative_to(cwd)),
            ]
        else:
            args = [
                str(executable),
                str(inputs),
                str(outputs),
                "ACAD2018",
                "DXF",
                "0",
                "0",
                staged.name,
            ]
        run_dwg_converter(args, converted, control, engine, cwd)
        return ezdxf.readfile(converted)


def cad_to_pdf(source, dest, control, advance, orientation="auto"):
    import ezdxf
    from functools import lru_cache
    from ezdxf.fonts import fonts
    from ezdxf.addons.drawing import RenderContext, config, layout, pymupdf
    from ezdxf.addons.drawing.frontend import UniversalFrontend
    from ezdxf.addons.drawing.pipeline import RenderPipeline2d

    advance(0.1)
    try:
        document = (
            read_dwg(source, control) if source.suffix.lower() == ".dwg" else ezdxf.readfile(source)
        )
    except ezdxf.DXFError as error:
        raise CadError(
            "CAD 도면을 읽지 못했습니다. CAD 프로그램에서 도면을 열어 확인해 주세요."
        ) from error
    if control:
        control.check()
    advance(0.2)
    manager = fonts.font_manager

    @lru_cache(maxsize=None)
    def glyphs(name):
        if not manager.has_font(name) or Path(name).suffix.lower() not in {".ttf", ".ttc", ".otf"}:
            return {}
        try:
            return manager.get_ttf_font(name).getBestCmap() or {}
        except fonts.FontNotFoundError:
            return {}

    def korean_characters(text):
        return {
            code
            for code in map(ord, text)
            if 0x1100 <= code <= 0x11FF
            or 0x3130 <= code <= 0x318F
            or 0xAC00 <= code <= 0xD7AF
            or 0x4E00 <= code <= 0x9FFF
        }

    def supports(face, required):
        return face is not None and required <= glyphs(Path(face.filename).name).keys()

    def fallback_face(required):
        for name in (
            "malgun.ttf",
            "malgunbd.ttf",
            "gulim.ttc",
            "batang.ttc",
            "NotoSansCJK-Regular.ttc",
        ):
            if required <= glyphs(name).keys():
                return manager.get_font_face(name)
        return None

    class KoreanRenderContext(RenderContext):
        def default_lineweight(self):
            # Unspecified strokes should remain thin when the drawing hides lineweights.
            return 0.25 if document.header.get("$LWDISPLAY", 0) else 0.05

        def resolve_font(self, entity):
            original = super().resolve_font(entity)
            plain_text = getattr(entity, "plain_text", None)
            if getattr(entity, "has_embedded_mtext_entity", False):
                plain_text = entity.plain_mtext
            required = (
                korean_characters(decode_cad_text(plain_text())) if callable(plain_text) else set()
            )
            if not required or supports(original, required):
                return original
            return fallback_face(required) or original

    class PrintPipeline(RenderPipeline2d):
        preserve_white_fill = False

        def draw_filled_polygon(self, points, properties):
            # WIPEOUT and MTEXT masks use filled polygons in the canvas color.
            self.preserve_white_fill = properties.color[:7].lower() == "#ffffff"
            try:
                super().draw_filled_polygon(points, properties)
            finally:
                self.preserve_white_fill = False

        def get_backend_properties(self, properties):
            resolved = super().get_backend_properties(properties)
            if self.preserve_white_fill:
                return resolved._replace(color=properties.color)
            return resolved

    class KoreanFrontend(UniversalFrontend):
        def draw_entity(self, entity, properties):
            if control:
                control.check()
            super().draw_entity(entity, properties)

        def draw_text_entity(self, entity, properties):
            # Attribute values inside INSERT title blocks also take this route.
            text = entity.dxf.get("text", "")
            corrected = decode_cad_text(text)
            if corrected != text:
                entity = entity.copy()
                entity.dxf.text = corrected
            super().draw_text_entity(entity, properties)

        def draw_mtext_entity(self, entity, properties):
            corrected = decode_cad_text(entity.text)
            if corrected != entity.text:
                entity = entity.copy()
                entity.text = corrected
            super().draw_mtext_entity(entity, properties)

        def draw_complex_mtext(self, mtext, properties):
            def replace_font(match):
                run = re.split(r"[{}]|\\[fF]", mtext.text[match.end() :], maxsplit=1)[0]
                required = korean_characters(run)
                if not required or supports(fonts.find_best_match(family=match[2]), required):
                    return match[0]
                fallback = fallback_face(required)
                return f"\\{match[1]}{fallback.family}{match[3]};" if fallback else match[0]

            # MTEXT font codes can override the corrected DXF text style.
            corrected = re.sub(r"(?<!\\)\\([fF])([^;|{}]+)([^;{}]*);", replace_font, mtext.text)
            if corrected != mtext.text:
                mtext = mtext.copy()
                mtext.text = corrected
            super().draw_complex_mtext(mtext, properties)

    class PrintRenderBackend(pymupdf.PyMuPdfRenderBackend):
        def resolve_stroke_width(self, width):
            # ezdxf resolves entity/layer weights in mm, using 0.01 mm for zero.
            return width * pymupdf.MM_TO_POINTS

    class PrintRecorder(pymupdf.PyMuPdfBackend):
        def __init__(self):
            super().__init__()
            self.lines = []
            self.line_style = None

        def draw_line(self, start, end, properties):
            # Batch adjacent independent opaque strokes of the same style.
            # Flush on shared endpoints to preserve the original line caps.
            if properties.color[7:9].lower() not in {"", "ff"}:
                super().draw_line(start, end, properties)
                return
            if self.lines and (
                self.line_style[:4] != properties[:4]
                or self.lines[-1][1] == start
                or len(self.lines) >= 256
            ):
                self.flush_lines()
            self.line_style = properties
            self.lines.append((start, end))

        def flush_lines(self):
            if self.lines:
                lines, self.lines = self.lines, []
                super().draw_solid_lines(lines, self.line_style)

        def store(self, record, properties):
            self.flush_lines()
            super().store(record, properties)

        def finalize(self):
            self.flush_lines()
            super().finalize()

        @staticmethod
        def make_backend(page, settings):
            return PrintRenderBackend(page, settings)

    backend = PrintRecorder()
    KoreanFrontend(
        KoreanRenderContext(document),
        PrintPipeline(backend),
        config.Configuration(
            background_policy=config.BackgroundPolicy.WHITE,
            color_policy=config.ColorPolicy.BLACK,
        ),
    ).draw_layout(document.modelspace())
    if control:
        control.check()
    bounds = backend.player().bbox()
    if not bounds.has_data:
        raise CadError("도면의 모형 공간에 변환할 내용이 없습니다.")
    landscape = orientation == "landscape" or (
        orientation == "auto" and bounds.size.x >= bounds.size.y
    )
    width, height = (297, 210) if landscape else (210, 297)
    page = layout.Page(width, height, margins=layout.Margins.all(8))
    # Compact PDF objects and streams without rasterizing the drawing.
    with backend.get_replay(page, render_box=bounds).doc as pdf:
        if control:
            control.check()
        pdf.save(
            dest,
            garbage=4,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            use_objstms=1,
        )
    advance(0.8)
