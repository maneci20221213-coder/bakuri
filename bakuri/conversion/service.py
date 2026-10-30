"""Conversion routing and batch orchestration; adapters own format details."""

from pathlib import Path
import tempfile
from PIL import Image
import fitz
from image_inputs import frames, white_rgb, save_png
from bakuri.domain.formats import IMAGES, HANCOM, SUPPORTED, can_convert, can_merge
from bakuri.application.control import JobControl
from merged_names import merged_path
from .office import OfficeSession
from .pdf import to_pdf


def convert(
    files, fmt, merge=False, progress=lambda s: None, dpi=150, image_mode="background", control=None
):
    files = [Path(p).resolve() for p in files]
    fmt = fmt.lower()
    fmt = "jpeg" if fmt == "jpg" else fmt
    control = control or JobControl()
    results = []
    if not files:
        raise ValueError("파일을 추가해 주세요.")
    if fmt not in {"png", "jpeg", "pdf", "hwpx", "xlsx", "docx", "pptx"}:
        raise ValueError("지원하지 않는 출력 형식")
    if merge and fmt not in {"pdf", "hwpx", "pptx"}:
        raise ValueError("합치기는 PDF·PPTX 또는 이미지의 HWPX 변환만 가능합니다.")
    if merge and not can_merge(files, fmt):
        raise ValueError("한글 문서와 이미지·PDF는 따로 선택해 합쳐 주세요.")
    for path in files:
        control.check()
        if not path.is_file() or path.suffix.lower() not in SUPPORTED:
            raise ValueError(f"지원하지 않는 파일: {path}")
        if not can_convert(path, fmt):
            raise ValueError("선택한 입력과 출력 형식의 조합을 지원하지 않습니다.")

    def message(text):
        control.check()
        progress(text)

    with OfficeSession() as session, tempfile.TemporaryDirectory() as td:
        session.control = control
        td = Path(td)
        pdfs = []
        if merge and fmt == "pptx":
            temp = td / "merged.pptx"
            session.slides_document(files, temp, td, dpi)
            control.check()
            results.append(control.publish(temp, merged_path(files, "pptx")))
        elif merge and fmt == "hwpx":
            session.advance = lambda f, t: control.update(f * 95, t)
            temp = td / "merged.hwpx"
            if all(p.suffix.lower() in HANCOM for p in files):
                from hancom_merge import merge_documents

                merge_documents(session.hwp(), files, temp, session.check, session.advance)
            else:
                session.image_document(files, temp, td, image_mode, message)
            control.check()
            results.append(control.publish(temp, merged_path(files, "hwpx")))
        else:
            for index, src in enumerate(files):
                base = index * 90 / len(files)
                width = 90 / len(files)

                def advance(fraction, text=""):
                    control.update(base + width * min(0.98, fraction), text or src.name)

                session.advance = advance
                advance(0)
                message(f"{index+1}/{len(files)} · {src.name}")
                temp = td / f"{index}.{fmt}"
                if fmt == "pptx":
                    session.slides_document([src], temp, td, dpi)
                elif fmt == "hwpx" and src.suffix.lower() in IMAGES | {".pdf"}:
                    session.image_document([src], temp, td, image_mode, message)
                elif fmt in {"hwpx", "xlsx", "docx"}:
                    advance(0.15)
                    session.export(src, temp, fmt.upper())
                    advance(0.9)
                elif fmt in {"png", "jpeg"} and src.suffix.lower() in IMAGES:
                    with Image.open(src) as image:
                        pages = (
                            getattr(image, "n_frames", 1)
                            if src.suffix.lower() in {".tif", ".tiff"}
                            else 1
                        )
                    for number, image in enumerate(frames(src)):
                        advance(0.1 + 0.7 * number / pages)
                        if fmt == "jpeg":
                            image = white_rgb(image)
                        if fmt == "png":
                            save_png(image, temp, src)
                        else:
                            image.save(temp, "JPEG", quality=95, optimize=True)
                        control.check()
                        name = (
                            f"{src.stem}.{fmt}" if pages == 1 else f"{src.stem}_{number+1:03}.{fmt}"
                        )
                        results.append(control.publish(temp, src.with_name(name)))
                        advance(0.1 + 0.8 * (number + 1) / pages)
                    continue
                else:
                    pdf = src if src.suffix.lower() == ".pdf" else td / f"{index}.pdf"
                    advance(0.05)
                    if pdf != src:
                        to_pdf(src, pdf, session, control, advance)
                    control.check()
                    advance(0.35)
                    if fmt == "pdf":
                        temp = pdf
                    if merge:
                        pdfs.append(pdf)
                        advance(0.98)
                        continue
                    if fmt != "pdf":
                        with fitz.open(pdf) as document:
                            if document.needs_pass:
                                raise ValueError("암호가 있는 PDF는 지원하지 않습니다.")
                            for number, page in enumerate(document):
                                advance(0.35 + 0.6 * number / len(document))
                                message(
                                    f"{index+1}/{len(files)} · {src.name} · {number+1}/{len(document)}페이지"
                                )
                                pix = page.get_pixmap(dpi=dpi, alpha=False)
                                control.check()
                                if fmt == "jpeg":
                                    pix.save(str(temp), jpg_quality=95)
                                else:
                                    pix.save(str(temp))
                                name = (
                                    f"{src.stem}.{fmt}"
                                    if len(document) == 1
                                    else f"{src.stem}_{number+1:03}.{fmt}"
                                )
                                results.append(control.publish(temp, src.with_name(name)))
                                advance(0.35 + 0.6 * (number + 1) / len(document))
                        continue
                advance(0.95)
                results.append(control.publish(temp, src.with_suffix("." + fmt)))
            if merge:
                merged = td / "merged.pdf"
                with fitz.open() as document:
                    for number, pdf in enumerate(pdfs):
                        control.update(90 + 7 * number / len(pdfs), "PDF 합치기")
                        with fitz.open(pdf) as part:
                            if part.needs_pass:
                                raise ValueError("암호가 있는 PDF는 지원하지 않습니다.")
                            control.check()
                            document.insert_pdf(part)
                            control.check()
                    control.check()
                    document.save(merged, garbage=4, deflate=True, deflate_images=True)
                    control.check()
                results.append(control.publish(merged, merged_path(files, "pdf")))
        control.update(99, "저장 확인")
    control.complete()
    return results
