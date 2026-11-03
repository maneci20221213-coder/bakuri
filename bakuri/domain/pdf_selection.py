"""One-based PDF selections, normalized to original document order."""

import re


def page_groups(count, mode="interval", every=1, selection="", separate=False):
    if count < 1:
        raise ValueError("페이지가 없는 PDF입니다.")
    if mode == "interval":
        if type(every) is not int or every < 1:
            raise ValueError("나눌 페이지 수를 1 이상으로 입력해 주세요.")
        return tuple(
            tuple(range(start, min(start + every, count))) for start in range(0, count, every)
        )
    if mode != "extract":
        raise ValueError("나누기 방식을 선택해 주세요.")
    if not selection.strip():
        raise ValueError("추출할 페이지를 입력해 주세요. 예: 1-3, 5, 8-10")
    groups = []
    for part in selection.split(","):
        match = re.fullmatch(r"\s*([0-9]+)\s*(?:-\s*([0-9]+)\s*)?", part)
        if not match:
            raise ValueError("페이지는 1-3, 5, 8-10처럼 입력해 주세요.")
        start, end = int(match[1]), int(match[2] or match[1])
        if not 1 <= start <= end <= count:
            raise ValueError(f"페이지는 1~{count}쪽 안에서 작은 번호부터 입력해 주세요.")
        groups.append(tuple(range(start - 1, end)))
    groups.sort(key=lambda group: group[0])
    pages = sorted({page for group in groups for page in group})
    if separate:
        if sum(map(len, groups)) != len(pages):
            raise ValueError("범위별로 저장할 때는 페이지가 겹치지 않게 입력해 주세요.")
        return tuple(groups)
    return (tuple(pages),)
