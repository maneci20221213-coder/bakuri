"""Render CAD model space to a fitted vector PDF."""

import os
from pathlib import Path
from shutil import copyfile
import subprocess
from tempfile import TemporaryDirectory
import time


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

    bundled = bundled_converter()
    if bundled.is_file():
        executable = bundled
        engine = "LibreDWG"
    else:
        executable = find_oda()
        engine = "ODA File Converter"
        if executable is None:
            raise CadError(
                "DWG 변환 도구가 없습니다. 바꾸리 설치 파일을 다시 받거나 DXF로 저장해 주세요."
            )

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
    from ezdxf.addons.drawing import Frontend, RenderContext, config, layout, pymupdf

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

    class KoreanRenderContext(RenderContext):
        def resolve_font(self, entity):
            original = super().resolve_font(entity)
            plain_text = getattr(entity, "plain_text", None)
            if not callable(plain_text):
                return original
            required = {
                code
                for code in map(ord, plain_text())
                if 0x1100 <= code <= 0x11FF
                or 0x3130 <= code <= 0x318F
                or 0xAC00 <= code <= 0xD7AF
                or 0x4E00 <= code <= 0x9FFF
            }
            if not required or (
                original and required <= glyphs(Path(original.filename).name).keys()
            ):
                return original
            for name in (
                "malgun.ttf",
                "malgunbd.ttf",
                "gulim.ttc",
                "batang.ttc",
                "NotoSansCJK-Regular.ttc",
            ):
                if required <= glyphs(name).keys():
                    return manager.get_font_face(name)
            return original

    backend = pymupdf.PyMuPdfBackend()
    Frontend(
        KoreanRenderContext(document),
        backend,
        config.Configuration(
            background_policy=config.BackgroundPolicy.WHITE,
            color_policy=config.ColorPolicy.COLOR_SWAP_BW,
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
            clean=True,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            use_objstms=1,
            compression_effort=100,
        )
    advance(0.8)
