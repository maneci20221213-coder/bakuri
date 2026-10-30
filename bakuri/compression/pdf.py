"""Optimize internal PDF images while verifying text, links and forms."""

import io, math, re
import fitz
from PIL import Image
from .profiles import PROFILES, SkipCompression
from .images import text_like, encoded


def pdf_colorspace(document, xref):
    kind, value = document.xref_get_key(xref, "ColorSpace")
    if kind == "xref":
        value = document.xref_object(int(value.split()[0]))
    if value.strip() in ("/DeviceRGB", "/DeviceGray"):
        return True, None
    profile = re.search(r"/ICCBased\s+(\d+)\s+0\s+R", value)
    if profile:
        profile_xref = int(profile.group(1))
        channels = document.xref_get_key(profile_xref, "N")[1]
        if channels in ("1", "3"):
            return True, document.xref_stream(profile_xref)
    return False, None


def pdf_snapshot(page):
    return (
        page.get_text(),
        len(page.get_links()),
        len(list(page.annots() or [])),
        [(widget.field_name, widget.field_value) for widget in page.widgets() or []],
    )


def compress_pdf(source, target, profile, protect_text, strip, check, tick):
    settings = PROFILES[profile]
    ratio = settings.get("ratio")
    with fitz.open(source) as document:
        if document.needs_pass or document.is_encrypted:
            raise SkipCompression("암호 PDF는 압축하지 않습니다.")
        if document.get_sigflags() > 0:
            raise SkipCompression(
                "전자서명이 있거나 서명용 칸이 있는 PDF는 원본 보호를 위해 용량을 줄이지 않습니다."
            )
        snapshots = []
        images = {}
        seen_masks = set()
        for number, page in enumerate(document):
            check()
            snapshots.append(pdf_snapshot(page))
            for entry in page.get_images(full=True):
                if entry[1]:
                    seen_masks.add(entry[1])
                    seen_masks.add(entry[0])
            if profile != "lossless":
                for item in page.get_image_info(xrefs=True):
                    xref = item["xref"]
                    if not xref:
                        continue
                    transform = item["transform"]
                    width = math.hypot(*transform[:2])
                    height = math.hypot(*transform[2:4])
                    if not width or not height:
                        continue
                    area = fitz.Rect(item["bbox"]).get_area() / max(1, page.rect.get_area())
                    scan = protect_text or area > 0.65
                    dpi = settings["scan_dpi"] if scan else settings["photo_dpi"]
                    scale = (
                        (1 if protect_text else ratio)
                        if ratio is not None
                        else min(
                            1,
                            max(
                                width * dpi / (72 * item["width"]),
                                height * dpi / (72 * item["height"]),
                            ),
                        )
                    )
                    entry = images.setdefault(xref, dict(page=number, scale=0, scan_scale=0))
                    entry["scale"] = max(entry["scale"], scale)
                    entry["scan_scale"] = max(
                        entry["scan_scale"],
                        min(
                            1,
                            max(
                                width * settings["scan_dpi"] / (72 * item["width"]),
                                height * settings["scan_dpi"] / (72 * item["height"]),
                            ),
                        ),
                    )
            tick(0.15 * (number + 1) / max(1, len(document)))
        for number, (xref, entry) in enumerate(images.items()):
            check()
            tick(0.15 + 0.65 * number / max(1, len(images)))
            if xref in seen_masks:
                continue
            # Special masks, inversion, CMYK/DeviceN stay untouched.
            supported, icc = pdf_colorspace(document, xref)
            if not supported:
                continue
            if any(
                document.xref_get_key(xref, key)[0] != "null" for key in ("SMask", "Mask", "Decode")
            ):
                continue
            original = document.extract_image(xref)
            if not original:
                continue
            with Image.open(io.BytesIO(original["image"])) as image:
                image.load()
                if icc:
                    image.info["icc_profile"] = icc
                graphic = protect_text or text_like(image)
                if graphic:
                    # Scan text keeps more pixels than photos; explicit protection keeps all pixels.
                    scale = (
                        (1 if protect_text else ratio)
                        if ratio is not None
                        else (1 if protect_text else entry["scan_scale"])
                    )
                    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
                    resized = (
                        image.resize(size, Image.Resampling.LANCZOS, reducing_gap=3)
                        if scale < 1
                        else image
                    )
                    candidate = encoded(resized, "PNG", strip=strip)
                else:
                    width = max(1, round(image.width * entry["scale"]))
                    height = max(1, round(image.height * entry["scale"]))
                    resized = (
                        image.resize((width, height), Image.Resampling.LANCZOS, reducing_gap=3)
                        if entry["scale"] < 1
                        else image
                    )
                    candidate = encoded(resized, "JPEG", settings["quality"], strip)
                check()
                if len(candidate) < len(document.xref_stream_raw(xref)):
                    document[entry["page"]].replace_image(xref, stream=candidate)
        check()
        tick(0.85)
        if strip:
            document.set_metadata({})
            document.del_xml_metadata()
        document.save(
            target,
            garbage=3,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            use_objstms=1,
            encryption=fitz.PDF_ENCRYPT_KEEP,
        )
        check()
        tick(0.95)
    with fitz.open(target) as result:
        if len(result) != len(snapshots):
            raise RuntimeError("PDF 페이지 수 검증 실패")
        for number, page in enumerate(result):
            check()
            if pdf_snapshot(page) != snapshots[number]:
                raise RuntimeError("PDF 텍스트/링크/주석/양식 검증 실패")
    return "PDF의 텍스트·도형 유지 · 내부 이미지/구조 최적화"
