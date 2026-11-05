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


def run_dwg_converter(args, converted, control, engine):
    try:
        process = subprocess.Popen(
            args,
            cwd=Path(args[0]).parent,
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
        if engine == "LibreDWG":
            args = [str(executable), "-o", str(converted), str(staged)]
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
        run_dwg_converter(args, converted, control, engine)
        return ezdxf.readfile(converted)


def cad_to_pdf(source, dest, control, advance):
    import ezdxf
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
    backend = pymupdf.PyMuPdfBackend()
    Frontend(
        RenderContext(document),
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
    width, height = (297, 210) if bounds.size.x >= bounds.size.y else (210, 297)
    page = layout.Page(width, height, margins=layout.Margins.all(8))
    dest.write_bytes(backend.get_pdf_bytes(page))
    advance(0.8)
