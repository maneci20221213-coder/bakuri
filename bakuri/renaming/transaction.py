"""Two-phase rename, rollback and one-level undo. Never overwrite an input."""

from pathlib import Path
import json, uuid
from .storage import identity, key, write_journal, move


def apply(rows, journal):
    if not rows or any(r["error"] for r in rows):
        raise ValueError("미리보기의 오류를 먼저 해결해 주세요.")
    changed = [r for r in rows if r["changed"]]
    if not changed:
        return []
    for row in rows:
        if identity(row["source"]) != row["identity"]:
            raise ValueError("미리보기 이후 파일이 바뀌었습니다. 목록을 다시 확인해 주세요.")
        if Path(row["source"]).parent != Path(row["target"]).parent:
            raise ValueError("다른 폴더로 이동할 수 없습니다.")
    sources = {key(r["source"]) for r in rows}
    for row in changed:
        if Path(row["target"]).exists() and key(row["target"]) not in sources:
            raise ValueError("대상 이름이 이미 사용 중입니다.")
    entries = [
        dict(
            original=r["source"],
            target=r["target"],
            current=r["source"],
            identity=r["identity"],
            temporary=str(Path(r["source"]).with_name(".bakuri-rename-" + uuid.uuid4().hex)),
        )
        for r in changed
    ]
    data = dict(state="working", entries=entries)
    write_journal(journal, data)

    def relocate(entry, target):
        if identity(entry["current"]) != entry["identity"]:
            raise ValueError("작업 중 원본이 변경되었습니다.")
        move(entry["current"], target)
        entry["current"] = target
        write_journal(journal, data)

    try:
        for entry in entries:
            relocate(entry, entry["temporary"])
        for entry in entries:
            relocate(entry, entry["target"])
    except Exception as exc:
        try:
            for entry in entries:
                if entry["current"] != entry["temporary"]:
                    relocate(entry, entry["temporary"])
            for entry in entries:
                relocate(entry, entry["original"])
            data["state"] = "rolled_back"
            write_journal(journal, data)
        except Exception:
            data["state"] = "recovery_needed"
            write_journal(journal, data)
            raise RuntimeError(
                "일부 파일을 되돌리지 못했습니다. 이름 변경 기록을 보존했습니다. 파일을 이동하지 말고 기록을 확인해 주세요."
            ) from exc
        raise RuntimeError(
            "이름을 변경하지 못해 원래 이름으로 되돌렸습니다. 파일이 다른 프로그램에서 사용 중인지 확인해 주세요."
        ) from exc
    data["state"] = "complete"
    write_journal(journal, data)
    return entries


def undo(journal):
    data = json.loads(Path(journal).read_text(encoding="utf-8"))
    if data.get("state") != "complete":
        raise ValueError("되돌릴 수 있는 완료 기록이 없습니다.")
    entries = data["entries"]
    rows = []
    sources = {key(e["current"]) for e in entries}
    for entry in entries:
        if identity(entry["current"]) != entry["identity"]:
            raise ValueError("변경 후 파일이 수정되거나 교체되어 되돌릴 수 없습니다.")
        target = Path(entry["original"])
        if target.exists() and key(target) not in sources:
            raise ValueError("원래 이름을 다른 파일이 사용 중입니다.")
        rows.append(
            dict(
                source=entry["current"],
                target=entry["original"],
                name=target.name,
                identity=entry["identity"],
                changed=True,
                error="",
            )
        )
    result = apply(rows, journal)
    write_journal(journal, dict(state="undone", entries=result))
    return result
