"""MPF metadata, lossless frame staging and publication to original folders."""

from dataclasses import replace
from pathlib import Path
import re
import tempfile
from PIL import Image
from bakuri.domain.models import MultiImageSelection, ConversionRequest
from bakuri.application.control import JobControl

JPEG_INPUTS = {".jpg", ".jpeg", ".mpo"}
THUMBNAILS = {"Large Thumbnail (VGA Equivalent)", "Large Thumbnail (Full HD Equivalent)"}


def _auxiliary_xmp(data):
    if not data.startswith(b"http://ns.adobe.com/xap/1.0/\x00"):
        return False
    return (
        b"http://ns.adobe.com/hdr-gain-map/1.0/" in data
        and re.search(rb"hdrgm:Version\s*[=>]", data) is not None
        or b"http://ns.google.com/photos/1.0/depthmap/" in data
        and re.search(rb"GDepth:Data\s*[=>]", data) is not None
    )


def _header(file, end):
    if file.read(2) != b"\xff\xd8":
        raise ValueError("JPEG 이미지 정보를 확인할 수 없습니다.")
    while file.tell() < end:
        marker = file.read(2)
        if len(marker) != 2 or marker[0] != 255:
            raise ValueError("JPEG 이미지 정보가 손상되었습니다.")
        while marker[1] == 255:
            marker = b"\xff" + file.read(1)
            if len(marker) != 2:
                raise ValueError("JPEG 이미지 정보가 손상되었습니다.")
        if marker[1] in {0xD8, 0xD9} or 0xD0 <= marker[1] <= 0xD7:
            raise ValueError("JPEG 이미지 정보가 손상되었습니다.")
        raw_length = file.read(2)
        length = int.from_bytes(raw_length, "big")
        if len(raw_length) != 2 or length < 2 or file.tell() + length - 2 > end:
            raise ValueError("JPEG 이미지 범위를 확인할 수 없습니다.")
        start = file.tell()
        payload = file.read(length - 2)
        yield marker, raw_length, payload, start
        if marker == b"\xff\xda":
            return
    raise ValueError("JPEG 이미지 데이터를 확인할 수 없습니다.")


def _fingerprint(path):
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def _description(path):
    fingerprint = _fingerprint(path)
    size = fingerprint[0]
    with Image.open(path) as image:
        if image.format not in {"JPEG", "MPO"}:
            return None, ()
        mp = getattr(image, "mpinfo", None)
        if mp is None and "mp" in image.info:
            mp = image._getmp()
        auxiliary_xmp = any(
            _auxiliary_xmp(data) for marker, data in image.applist if marker == "APP1"
        )
        if mp is None:
            if not auxiliary_xmp:
                return None, ()
            return MultiImageSelection(str(path), 1, 0, auxiliary=True, fingerprint=fingerprint), (
                (0, size),
            )
        if mp.get(0xB001) == 1 and not auxiliary_xmp:
            return None, ()
        entries = mp.get(0xB002, ())
        count = mp.get(0xB001, 0)
        if count < 1 or len(entries) != count:
            raise ValueError("다중 이미지 정보를 확인할 수 없습니다.")
        primary = next(
            (i for i, e in enumerate(entries) if e["Attribute"].get("RepresentativeImageFlag")),
            None,
        )
        if primary is None:
            primary = next(
                (
                    i
                    for i, e in enumerate(entries)
                    if e["Attribute"].get("MPType") == "Baseline MP Primary Image"
                ),
                0,
            )
        auxiliary = all(
            e["Attribute"].get("MPType") in THUMBNAILS
            for i, e in enumerate(entries)
            if i != primary
        )
        auxiliary = auxiliary or (count == 2 and auxiliary_xmp)
        with path.open("rb") as file:
            base = next(
                (
                    start + 4
                    for marker, _, payload, start in _header(file, size)
                    if marker == b"\xff\xe2" and payload.startswith(b"MPF\x00")
                ),
                None,
            )
        if base is None:
            raise ValueError("다중 이미지 위치 정보를 확인할 수 없습니다.")
        spans = tuple(
            (0 if i == 0 else int(e["DataOffset"]) + base, int(e["Size"]))
            for i, e in enumerate(entries)
        )
        if any(offset < 0 or length < 4 or offset + length > size for offset, length in spans):
            raise ValueError("다중 이미지 범위가 잘못되었습니다. 원본은 변경하지 않았습니다.")
        if _fingerprint(path) != fingerprint:
            raise ValueError("파일이 변경되었습니다. 다시 선택해 주세요.")
        return (
            MultiImageSelection(
                str(path), count, primary, auxiliary=auxiliary, fingerprint=fingerprint
            ),
            spans,
        )


def inspect_multi_image(path):
    path = Path(path).absolute()
    return _description(path)[0] if path.suffix.lower() in JPEG_INPUTS else None


def resolve_selections(files, selections):
    choices = {choice.path: choice for choice in selections}
    result = []
    for file in files:
        info = inspect_multi_image(file.path)
        choice = choices.get(file.path)
        if choice is not None and (info is None or replace(choice, mode="primary") != info):
            raise ValueError("파일 내용이 변경되었습니다. 이미지 처리 범위를 다시 선택해 주세요.")
        if info is None:
            continue
        if choice is None and info.count > 1 and not info.auxiliary:
            raise ValueError(
                "여러 이미지가 들어 있습니다. 대표 이미지 또는 모든 이미지 처리를 선택해 주세요."
            )
        result.append(choice or info)
    return tuple(result)


def _stage_frame(path, info, span, target, control):
    offset, size = span
    with path.open("rb") as source, target.open("xb") as output:
        source.seek(offset)
        output.write(b"\xff\xd8")
        for marker, length, payload, _ in _header(source, offset + size):
            control.check()
            if marker == b"\xff\xe2" and payload.startswith(b"MPF\x00"):
                continue
            if marker == b"\xff\xe1" and _auxiliary_xmp(payload):
                continue
            output.write(marker + length + payload)
        remaining = offset + size - source.tell()
        while remaining:
            control.check()
            block = source.read(min(1024 * 1024, remaining))
            if not block:
                raise ValueError("이미지 데이터가 중간에 끝났습니다.")
            output.write(block)
            remaining -= len(block)
    with target.open("rb") as verify:
        verify.seek(-2, 2)
        if verify.read() != b"\xff\xd9":
            raise ValueError("이미지 끝을 확인할 수 없습니다. 원본은 변경하지 않았습니다.")
    with Image.open(target) as image:
        if image.format != "JPEG":
            raise ValueError("단일 JPEG 준비를 완료하지 못했습니다.")
    if _fingerprint(path) != info.fingerprint:
        raise ValueError("파일이 변경되었습니다. 다시 선택해 주세요.")


class _Publication(JobControl):
    def __init__(self, parent, folders):
        super().__init__(
            lambda percent, text: parent.update(5 + percent * 0.93, text), parent.measure_units
        )
        self.cancelled = parent.cancelled
        self.outputs = parent.outputs
        self.parent = parent
        self.folders = folders

    def complete(self):
        self.check()

    def publish(self, source, desired):
        desired = Path(desired)
        return self.parent.publish(
            source, self.folders.get(desired.parent, desired.parent) / desired.name
        )


def process_selected_images(request, selections, control):
    from .service import convert
    from bakuri.compression.service import compress

    choices = {choice.path: choice for choice in selections}
    with tempfile.TemporaryDirectory(prefix="BakuriImages-") as directory:
        paths, folders, origins = [], {}, {}
        for index, file in enumerate(request.files):
            control.check()
            source = Path(file.path)
            choice = choices.get(file.path)
            if choice is None:
                paths.append(source)
                continue
            info, spans = _description(source)
            if replace(choice, mode="primary") != info:
                raise ValueError("파일이 변경되었습니다. 이미지 처리 범위를 다시 선택해 주세요.")
            folder = Path(directory).resolve() / str(index)
            folder.mkdir()
            folders[folder] = source.parent.resolve()
            indexes = range(info.count) if choice.mode == "all" else (info.primary,)
            for frame in indexes:
                suffix = f"_{frame+1:02}" if choice.mode == "all" else ""
                target = folder / f"{source.stem}{suffix}.jpeg"
                _stage_frame(source, info, spans[frame], target, control)
                paths.append(target)
                detail = f"이미지 {frame+1}/{info.count}"
                if choice.mode == "primary":
                    detail += " · 대표 이미지만 선택"
                if info.auxiliary:
                    detail += " · 보조 이미지 제외"
                origins[str(target.resolve())] = (str(source.resolve()), detail)
        control.update(5, "이미지 준비 완료")
        counts = [sum(c.mode == mode for c in selections) for mode in ("primary", "all")]
        auxiliary = sum(c.auxiliary for c in selections)
        control.notes.append(
            f"다중 이미지 선택: 대표만 {counts[0]}개 · 전체 각각 {counts[1]}개 · 보조 이미지 제외 {auxiliary}개"
        )
        publication = _Publication(control, folders)
        if isinstance(request, ConversionRequest):
            merge = request.merge and not any(c.mode == "all" for c in selections)
            convert(
                paths,
                request.output.value,
                merge,
                control=publication,
                source_folders=folders,
                **request.options.as_kwargs(),
            )
        else:
            try:
                compress(paths, control=publication, **request.options.as_kwargs())
            finally:
                for row in publication.rows:
                    if row["source"] in origins:
                        row["source"], detail = origins[row["source"]]
                        row["detail"] = detail + " · " + row["detail"]
                    control.rows.append(row)
        control.complete()
    return list(control.outputs)
