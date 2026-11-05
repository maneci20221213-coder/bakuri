"""Supported quick-menu actions and selection profiles."""

from pathlib import Path

from .formats import CAD, HANCOM, IMAGES, PAGE_SPLIT_INPUTS, PRESENTATIONS, SPREADSHEETS, WORDS
from .formats import SUPPORTED, can_convert

DIRECTIONS = {"pdf": "위", "png": "왼쪽", "jpeg": "오른쪽", "more": "아래"}
PROFILES = {
    "image": "이미지",
    "pdf": "PDF",
    "hancom": "한글",
    "word": "Word",
    "sheet": "스프레드시트",
    "slides": "프레젠테이션",
    "cad": "CAD 도면",
    "other": "기타 / 혼합",
}
PROFILE_CHOICES = {**PROFILES, **{ext: ext[1:].upper() for ext in sorted(SUPPORTED)}}
ACTIONS = {
    "pdf": ("PDF 변환", "pdf"),
    "png": ("PNG 변환", "png"),
    "jpeg": ("JPEG 변환", "jpeg"),
    "hwpx": ("한글 변환", "hwpx"),
    "xlsx": ("XLSX 변환", "xlsx"),
    "docx": ("Word 변환", "odt"),
    "pptx": ("PowerPoint 변환", "odt"),
    "pdf_split": ("페이지 나누기", "pdf"),
    "pdf_merge": ("PDF 합치기", "pdf"),
    "hwp_merge": ("한글 합치기", "hwpx"),
    "compress": ("용량 축소", "compress"),
    "more": ("확장 기능", "plus"),
}


def selection_profile(extensions):
    for name, group in (
        ("image", IMAGES),
        ("pdf", {".pdf"}),
        ("hancom", HANCOM),
        ("word", WORDS),
        ("sheet", SPREADSHEETS),
        ("slides", PRESENTATIONS),
        ("cad", CAD),
    ):
        if extensions and extensions <= group:
            return name
    return "other"


def action_available(action, paths):
    if action == "more":
        return True
    extensions = {Path(path).suffix.lower() for path in paths}
    if action == "pdf_split":
        return len(paths) == 1 and extensions <= PAGE_SPLIT_INPUTS
    if action == "pdf_merge":
        return len(paths) > 1 and extensions == {".pdf"}
    if action == "hwp_merge":
        return len(paths) > 1 and extensions <= HANCOM
    if action == "compress":
        return bool(paths) and extensions <= IMAGES | {".pdf"}
    return bool(paths) and all(can_convert(path, action) for path in paths)
