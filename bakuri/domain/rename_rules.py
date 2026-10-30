"""Pure filename and clipboard rules; no filesystem, Qt or converters."""

import re

RESERVED = (
    {p + n for p in ("COM", "LPT") for n in "¹²³"}
    | {"CON", "PRN", "AUX", "NUL", "CLOCK$", "CONIN$", "CONOUT$"}
    | {f"{p}{n}" for p in ("COM", "LPT") for n in range(1, 10)}
)


def invalid(name):
    if not name or name in {".", ".."} or name.endswith((" ", ".")):
        return "끝의 공백·마침표 또는 빈 이름은 사용할 수 없습니다."
    if re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
        return "파일명에 사용할 수 없는 문자가 있습니다."
    if name.split(".")[0].upper() in RESERVED:
        return "Windows 예약 이름은 사용할 수 없습니다."
    if len(name.encode("utf-16-le")) // 2 > 255:
        return "파일명이 너무 깁니다."
    return ""


def insert_token(stem, token, position="after", separator="_", marker=""):
    if not token:
        return stem
    if position == "before":
        index = 0
    elif position == "after":
        index = len(stem)
    elif position in {"before_marker", "after_marker"}:
        if not marker:
            raise ValueError("삽입 기준 문자를 입력해 주세요.")
        index = stem.find(marker)
        if index < 0:
            raise ValueError("삽입 기준 문자가 이름에 없습니다.")
        if position == "after_marker":
            index += len(marker)
    else:
        raise ValueError("삽입 위치를 확인해 주세요.")
    left, right = stem[:index], stem[index:]
    before = separator if left and separator and not left.endswith(separator) else ""
    after = separator if right and separator and not right.startswith(separator) else ""
    return left + before + token + after + right


def _text_lines(text):
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    if any("\t" in line for line in lines):
        raise ValueError("한 열만 복사해 주세요. 여러 열은 붙여넣을 수 없습니다.")
    return lines


def pasted_lines(text, count):
    lines = _text_lines(text)
    if len(lines) != count:
        raise ValueError(
            f"선택 파일은 {count}개, 붙여넣은 문구는 {len(lines)}줄입니다. 개수를 맞춰 주세요."
        )
    return lines


def fill_down(text, count):
    """Forward-fill blank rows and missing trailing rows without shifting files."""
    if count <= 0:
        raise ValueError("문구를 붙일 파일을 먼저 선택해 주세요.")
    lines = _text_lines(text)
    if len(lines) > count:
        raise ValueError(
            f"선택 파일은 {count}개, 붙여넣은 문구는 {len(lines)}줄입니다. 넘치는 줄을 지워 주세요."
        )
    if not any(line.strip() for line in lines):
        raise ValueError("채울 문구를 한 줄 이상 입력해 주세요.")
    previous = ""
    values = []
    for line in lines + [""] * (count - len(lines)):
        if line.strip():
            previous = line
        values.append(previous)
    return values
