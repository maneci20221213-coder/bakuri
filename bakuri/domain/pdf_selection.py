"""Translate one-based page selections into ordered, zero-based groups."""

import re


class PageSelectionError(ValueError):
    """A page option the user can correct."""


def page_groups(count, mode="interval", every=1, selection="", separate=False):
    if count < 1:
        raise PageSelectionError("페이지가 없는 문서입니다.")
    if mode == "interval":
        if type(every) is not int or every < 1:
            raise PageSelectionError("나눌 페이지 수를 1 이상으로 입력해 주세요.")
        return tuple(
            tuple(range(start, min(start + every, count))) for start in range(0, count, every)
        )
    if mode == "boundaries":
        if count == 1:
            raise PageSelectionError("특정 페이지 기준으로 나누려면 두 쪽 이상이어야 합니다.")
        parts = [part.strip() for part in selection.split(",")]
        if not all(re.fullmatch(r"[0-9]+", part) for part in parts):
            raise PageSelectionError("새 파일을 시작할 페이지를 입력해 주세요. 예: 4, 8")
        starts = sorted({int(part) - 1 for part in parts})
        if starts[0] < 1 or starts[-1] >= count:
            raise PageSelectionError(f"새 파일을 시작할 페이지는 2~{count}쪽에서 골라 주세요.")
        edges = [0, *starts, count]
        return tuple(tuple(range(start, stop)) for start, stop in zip(edges, edges[1:]))
    if mode != "extract":
        raise PageSelectionError("나누기 방식을 선택해 주세요.")
    if not selection.strip():
        raise PageSelectionError("추출할 페이지를 입력해 주세요. 예: 1-3, 5, 8-10")
    groups = []
    for part in selection.split(","):
        match = re.fullmatch(r"\s*([0-9]+)\s*(?:-\s*([0-9]+)\s*)?", part)
        if not match:
            raise PageSelectionError("페이지는 1-3, 5, 8-10처럼 입력해 주세요.")
        start, end = int(match[1]), int(match[2] or match[1])
        if not 1 <= start <= end <= count:
            raise PageSelectionError(f"페이지는 1~{count}쪽 안에서 작은 번호부터 입력해 주세요.")
        groups.append(tuple(range(start - 1, end)))
    pages = dict.fromkeys(page for group in groups for page in group)
    if separate:
        if sum(map(len, groups)) != len(pages):
            raise PageSelectionError("범위별로 저장할 때는 페이지가 겹치지 않게 입력해 주세요.")
        return tuple(groups)
    return (tuple(pages),)


def page_output_path(source, count, group, extracted):
    if extracted:
        label = "추출본"
    else:
        width = max(3, len(str(count)))
        first, last = group[0] + 1, group[-1] + 1
        pages = f"{first:0{width}}" if first == last else f"{first:0{width}}-{last:0{width}}"
        label = f"{pages}쪽"
    return source.with_name(f"{source.stem}_{label}{source.suffix}")
