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


def read_dwg(source, control):
    import ezdxf

    executable = find_oda()
    if executable is None:
        raise CadError("DWG를 변환하려면 ODA File Converter를 설치하거나 DXF로 저장해 주세요.")
    with TemporaryDirectory(prefix="BakuriCAD-") as directory:
        inputs = Path(directory, "in")
        outputs = Path(directory, "out")
        inputs.mkdir()
        outputs.mkdir()
        copyfile(source, inputs / "drawing.dwg")
        args = [
            str(executable),
            str(inputs),
            str(outputs),
            "ACAD2018",
            "DXF",
            "0",
            "0",
            "drawing.dwg",
        ]
        try:
            process = subprocess.Popen(
                args,
                cwd=executable.parent,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as error:
            raise CadError(
                "ODA File Converter를 실행하지 못했습니다. ODA가 직접 실행되는지 확인해 주세요."
            ) from error
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
        converted = outputs / "drawing.dxf"
        if process.returncode != 0 or not converted.is_file():
            raise CadError(
                "ODA File Converter가 DWG에서 DXF를 만들지 못했습니다. "
                "ODA에서 도면이 열리는지 확인하거나 CAD 프로그램에서 DXF로 저장해 주세요."
            ) from RuntimeError(
                f"ODA exit code: {process.returncode}; DXF exists: {converted.is_file()}"
            )
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
