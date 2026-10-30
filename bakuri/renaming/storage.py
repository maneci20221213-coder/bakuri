"""Filesystem identity, durable journal and non-overwriting rename primitive."""

from pathlib import Path
import json, os


def identity(path):
    stat = Path(path).stat()
    return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns]


def key(path):
    return str(Path(path).absolute()).casefold()


def write_journal(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def move(source, target):
    if os.name == "nt":
        os.rename(source, target)  # Windows rename refuses an existing destination.
    else:
        os.link(source, target, follow_symlinks=False)
        try:
            os.unlink(source)
        except BaseException:
            os.unlink(target)
            raise
