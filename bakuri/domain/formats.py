"""One dependency-free support matrix for UI and execution."""

from pathlib import Path

IMAGES = {".png", ".jpg", ".jpeg", ".mpo", ".bmp", ".gif", ".tif", ".tiff", ".webp", ".ico"}
HANCOM = {".hwp", ".hwpx"}
SPREADSHEETS = {
    ".xls",
    ".xlsx",
    ".xlsm",
    ".xlsb",
    ".xlt",
    ".xltx",
    ".xltm",
    ".csv",
    ".tsv",
    ".ods",
    ".dif",
    ".slk",
}
WORDS = {".doc", ".docx"}
PAGE_SPLIT_INPUTS = {".pdf"} | HANCOM | WORDS
CAD = {".dxf", ".dwg"}
PRESENTATIONS = {".ppt", ".pptx"}
SUPPORTED = IMAGES | {".pdf", ".hwp", ".hwpx", ".odt"} | SPREADSHEETS | WORDS | PRESENTATIONS | CAD


def can_convert(path, fmt):
    fmt = "jpeg" if fmt.lower() == "jpg" else fmt.lower()
    ext = Path(path).suffix.lower()
    return ext in SUPPORTED and (
        fmt in {"pdf", "png", "jpeg"}
        or fmt == "hwpx"
        and ext in (IMAGES | {".odt", ".hwp", ".hwpx", ".pdf"} | WORDS)
        or fmt == "xlsx"
        and ext in SPREADSHEETS
        or fmt == "docx"
        and ext in (IMAGES | HANCOM | {".odt", ".pdf"})
        or fmt == "pptx"
        and ext in (IMAGES | {".pdf"})
    )


def can_merge(paths, fmt):
    extensions = {Path(p).suffix.lower() for p in paths}
    return (
        fmt.lower() in {"pdf", "pptx"}
        or fmt.lower() == "xlsx"
        and len(paths) > 1
        and extensions <= SPREADSHEETS
        or fmt.lower() == "hwpx"
        and bool(extensions)
        and (extensions <= IMAGES | {".pdf"} or extensions <= HANCOM)
    )
