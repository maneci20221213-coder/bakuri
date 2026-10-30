"""Batch compression, safe publication and per-file outcomes."""

from pathlib import Path
import tempfile
from user_messages import friendly_error
from bakuri.domain.formats import IMAGES
from bakuri.application.control import JobControl, Cancelled
from .profiles import PROFILES, SkipCompression
from .images import compress_image
from .pdf import compress_pdf


def compress(files, profile="p80", protect_text=False, strip_metadata=False, control=None):
    if profile not in PROFILES:
        raise ValueError("알 수 없는 압축 설정입니다.")
    files = [Path(path).resolve() for path in files]
    if not files:
        raise ValueError("파일을 선택해 주세요.")
    if any(path.suffix.lower() not in IMAGES | {".pdf"} for path in files):
        raise ValueError("용량 축소는 이미지와 PDF만 지원합니다.")
    control = control or JobControl()
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        for index, source in enumerate(files):
            control.check()
            before = source.stat().st_size

            def tick(fraction):
                control.update(99 * (index + min(1, fraction)) / len(files), source.name)

            row = dict(
                source=str(source),
                before=before,
                after=before,
                output="",
                status="축소 효과 없음",
                detail="",
            )
            try:
                tick(0)
                if source.suffix.lower() == ".pdf":
                    candidate = folder / "compressed.pdf"
                    detail = compress_pdf(
                        source,
                        candidate,
                        profile,
                        protect_text,
                        strip_metadata,
                        control.check,
                        tick,
                    )
                    suffix = ".pdf"
                else:
                    candidate, suffix, detail = compress_image(
                        source, folder, profile, protect_text, strip_metadata, control.check, tick
                    )
                control.check()
                after = candidate.stat().st_size
                row["detail"] = detail
                if after < before:
                    row["output"] = control.publish(
                        candidate, source.with_name(source.stem + "_용량축소" + suffix)
                    )
                    row["after"] = after
                    row["status"] = "저장 완료"
                else:
                    row["detail"] += " · 원본보다 작아지지 않아 저장하지 않았습니다."
            except Cancelled:
                raise
            except SkipCompression as exc:
                row["status"] = "건너뜀"
                row["detail"] = str(exc)
            except Exception as exc:
                row["status"] = "실패"
                row["detail"] = friendly_error(exc, "compression")
            control.rows.append(row)
            tick(1)
    control.complete()
    return list(control.outputs)
