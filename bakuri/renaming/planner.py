"""Read-only rename previews and collision checks."""

from pathlib import Path
import re
from bakuri.domain.rename_rules import invalid, insert_token
from .storage import identity, key


def preview(
    paths,
    find="",
    replace="",
    prefix="",
    suffix="",
    base="",
    start=1,
    digits=3,
    number_enabled=None,
    number_position="after",
    number_marker="",
    separator="_",
    text_by_source=None,
    text_position="before",
    text_marker="",
    text_mode="insert",
    string="",
    string_position="before",
    string_marker="",
    manual_names=None,
    **unused,
):
    rows = []
    for index, source in enumerate(paths):
        source = Path(source).absolute()
        stem = base or source.stem
        error = ""
        if find:
            stem = stem.replace(find, replace)
        try:
            custom = (text_by_source or {}).get(str(source), "")
            if custom:
                stem = (
                    custom
                    if text_mode == "replace"
                    else insert_token(stem, custom, text_position, "", text_marker)
                )
            if number_enabled if number_enabled is not None else bool(base):
                stem = insert_token(
                    stem, f"{start+index:0{digits}d}", number_position, separator, number_marker
                )
            stem = insert_token(stem, string, string_position, "", string_marker)
        except ValueError as exc:
            error = str(exc)
        name = prefix + stem + suffix + source.suffix
        if str(source) in (manual_names or {}):
            name = manual_names[str(source)]
            error = ""
            if source.suffix and not name.lower().endswith(source.suffix.lower()):
                name += source.suffix
        error = error or invalid(name)
        target = source.with_name(name) if not re.search(r"[/\\\x00]", name) else source
        try:
            if source.is_symlink() or not source.is_file():
                raise ValueError()
            token = identity(source)
        except (OSError, ValueError):
            token = None
            error = "원본 파일을 찾을 수 없거나 바로가기 링크입니다."
        if len(str(source.parent / name)) > 240:
            error = "전체 경로가 너무 깁니다. 이름을 줄여 주세요."
        rows.append(
            dict(
                source=str(source),
                target=str(target),
                name=name,
                identity=token,
                error=error,
                changed=name != source.name,
            )
        )
    sources = {key(r["source"]) for r in rows}
    counts = {}
    for row in rows:
        counts[key(Path(row["source"]).parent / row["name"])] = (
            counts.get(key(Path(row["source"]).parent / row["name"]), 0) + 1
        )
    folders = {}
    for row in rows:
        if row["error"]:
            continue
        target = Path(row["target"])
        k = key(target)
        if counts.get(key(Path(row["source"]).parent / row["name"]), 0) > 1:
            row["error"] = "선택한 파일끼리 이름이 겹칩니다."
        elif row["changed"]:
            try:
                if target.parent not in folders:
                    folders[target.parent] = {key(p) for p in target.parent.iterdir()} - sources
                if k in folders[target.parent]:
                    row["error"] = "같은 폴더에 이미 있는 이름입니다."
            except OSError:
                row["error"] = "폴더를 확인할 수 없습니다."
    return rows


def plan_rename(paths, options):
    """Typed UI boundary; legacy preview keywords remain available for callers."""
    return preview(tuple(paths), **options.as_kwargs())
