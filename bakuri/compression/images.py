"""Image encoding, metadata and TIFF preservation."""

import io
from PIL import Image, ImageOps, PngImagePlugin
from .profiles import PROFILES, RATIO_PROFILES, TARGET_BYTES, SkipCompression


def text_like(image):
    """A conservative heuristic, not OCR. User can force text protection."""
    sample = image.convert("RGB")
    sample.thumbnail((192, 192), Image.Resampling.NEAREST, reducing_gap=None)
    if sample.getcolors(64) is not None:
        return True
    histogram = sample.convert("L").histogram()
    count = sum(histogram)
    return (
        sum(histogram[230:]) / max(1, count) > 0.55
        and (sum(histogram[:36]) + sum(histogram[220:])) / max(1, count) > 0.78
    )


def resize(image, long_side):
    if not long_side or max(image.size) <= long_side:
        return image.copy()
    ratio = long_side / max(image.size)
    source = image.convert("RGBA") if image.mode == "P" else image
    return source.resize(
        (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
        Image.Resampling.LANCZOS,
        reducing_gap=3.0,
    )


def metadata(image, strip=False):
    result = {}
    if image.info.get("icc_profile"):
        result["icc_profile"] = image.info["icc_profile"]
    if image.info.get("dpi"):
        result["dpi"] = image.info["dpi"]
    if not strip:
        exif = image.getexif()
        if exif:
            exif[274] = 1
            if 40962 in exif:
                exif[40962] = image.width
            if 40963 in exif:
                exif[40963] = image.height
            result["exif"] = exif.tobytes()
        text = PngImagePlugin.PngInfo()
        for key, value in image.info.items():
            if isinstance(value, str):
                text.add_text(key, value)
        result["pnginfo"] = text
    return result


def encoded(image, fmt, quality=92, strip=False):
    options = metadata(image, strip)
    data = io.BytesIO()
    if fmt == "JPEG":
        options.pop("pnginfo", None)
        if image.mode not in ("RGB", "L", "CMYK"):
            image = image.convert("RGB")
        image.save(
            data, fmt, quality=quality, subsampling=0, optimize=True, progressive=True, **options
        )
    elif fmt == "WEBP":
        options.pop("pnginfo", None)
        options.pop("dpi", None)
        image.save(data, fmt, quality=quality, method=6, **options)
    else:
        image.save(data, "PNG", optimize=True, **options)
    return data.getvalue()


def compress_tiff(source, target, strip, check, tick, ratio=1):
    images = []
    memory = 0
    with Image.open(source) as original:
        count = getattr(original, "n_frames", 1)
        for index in range(count):
            check()
            original.seek(index)
            baseline = {
                254,
                256,
                257,
                258,
                259,
                262,
                266,
                273,
                274,
                277,
                278,
                279,
                282,
                283,
                284,
                296,
                317,
                320,
                322,
                323,
                324,
                325,
                338,
                339,
                34675,
            }
            if not strip and set(original.tag_v2) - baseline:
                raise SkipCompression(
                    "TIFF의 촬영 정보 등 부가정보(메타데이터)를 유지하기 위해 건너뛰었습니다. 해당 정보가 필요 없다면 메타데이터 삭제 옵션을 켜고 다시 시도해 주세요."
                )
            memory += original.width * original.height * max(1, len(original.getbands()))
            if memory > 256 * 1024 * 1024:
                raise SkipCompression(
                    "여러 페이지가 있는 큰 TIFF는 메모리 사용을 줄이기 위해 건너뜁니다. 페이지를 나눠서 다시 시도해 주세요."
                )
            image = ImageOps.exif_transpose(original).copy()
            if ratio < 1:
                image = image.resize(
                    (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
                    Image.Resampling.LANCZOS,
                )
            images.append(image)
            tick(0.7 * (index + 1) / count)
        check()
        options = {}
        if original.info.get("icc_profile"):
            options["icc_profile"] = original.info["icc_profile"]
        if original.info.get("dpi"):
            options["dpi"] = original.info["dpi"]
        images[0].save(
            target,
            "TIFF",
            save_all=True,
            append_images=images[1:],
            compression="tiff_adobe_deflate",
            **options,
        )
    with Image.open(target) as verify:
        if verify.n_frames != len(images):
            raise RuntimeError("TIFF 페이지 수가 달라졌습니다.")
        for index, image in enumerate(images):
            check()
            verify.seek(index)
            if (
                verify.size != image.size
                or verify.convert("RGBA").tobytes() != image.convert("RGBA").tobytes()
            ):
                raise RuntimeError("TIFF 픽셀 검증 실패")
    return target, ".tiff", f"TIFF 전체 페이지 보존 · 가로·세로 원본의 {ratio:.0%}"


def compress_image(source, folder, profile, protect_text, strip, check, tick):
    settings = PROFILES[profile]
    suffix = source.suffix.lower()
    target = folder / "image.tmp"
    if profile in RATIO_PROFILES:
        return compress_image_ratio(
            source, folder, settings["ratio"], protect_text, strip, check, tick
        )
    if suffix == ".ico":
        raise SkipCompression("여러 아이콘 크기 보존을 위해 ICO 압축은 건너뜁니다.")
    if suffix in {".tif", ".tiff"}:
        return compress_tiff(source, target, strip, check, tick)
    with Image.open(source) as original:
        if getattr(original, "n_frames", 1) > 1:
            raise SkipCompression("움직이는 이미지의 모든 프레임 보존을 위해 압축을 건너뜁니다.")
        if suffix == ".gif":
            raise SkipCompression("GIF의 색상과 투명도를 유지하기 위해 용량 축소를 건너뛰었습니다.")
        if profile == "lossless" and suffix in {".jpg", ".jpeg"}:
            raise SkipCompression(
                "이 설정으로는 JPEG 사진을 더 줄일 수 없습니다. 다른 축소 비율을 선택해 주세요."
            )
        if profile == "size" and source.stat().st_size <= TARGET_BYTES:
            raise SkipCompression("이미 1MB 이하입니다.")
        image = ImageOps.exif_transpose(original)
        image.load()
        check()
        graphic = protect_text or text_like(image)
        transparent = (
            "A" in image.getbands()
            and image.getchannel("A").getextrema()[0] < 255
            or image.mode == "P"
            and "transparency" in image.info
        )
        lossless = profile == "lossless" or graphic or transparent
        if lossless:
            # No PNG/WebP palette reduction, no text/alpha resolution reduction.
            fmt = "WEBP" if suffix == ".webp" else "PNG"
            if suffix in {".jpg", ".jpeg"}:
                if protect_text:
                    raise SkipCompression("글자 보호 설정으로 JPEG의 화질 변경을 건너뜁니다.")
                fmt = "JPEG"
        else:
            fmt = "WEBP" if suffix == ".webp" else "JPEG"
        output_suffix = {"JPEG": ".jpeg", "PNG": ".png", "WEBP": ".webp"}[fmt]
        if fmt == "WEBP" and lossless:
            data = io.BytesIO()
            options = metadata(image, strip)
            options.pop("pnginfo", None)
            options.pop("dpi", None)
            image.save(data, "WEBP", lossless=True, method=6, **options)
            candidate = data.getvalue()
            check()
            target.write_bytes(candidate)
            tick(0.9)
            detail = "투명도/글자/픽셀 보존을 위한 무손실 WebP 압축"
        elif lossless:
            # A JPEG detected as text may only be resaved at high quality if resized;
            # leaving it untouched is safer than claiming a lossless JPEG encoder.
            if fmt == "JPEG":
                raise SkipCompression("글자/도형 보호를 위해 JPEG 재압축을 건너뜁니다.")
            check()
            candidate = encoded(image, fmt, strip=strip)
            check()
            target.write_bytes(candidate)
            tick(0.9)
            detail = "글자/투명도/픽셀 보존을 위한 무손실 압축"
        else:
            dimensions = [settings["long"]]
            qualities = [settings["quality"]]
            if profile == "size":
                dimensions = list(
                    dict.fromkeys(min(max(image.size), side) for side in [2560, 2240, 1920, 1600])
                )
                qualities = [88, 85, 82]
            best = None
            best_dimensions = None
            attempt = 0
            planned = len(dimensions) * len(qualities)
            for side in dimensions:
                check()
                resized = resize(image, side)
                for quality in qualities:
                    check()
                    candidate = encoded(resized, fmt, quality, strip)
                    check()
                    attempt += 1
                    tick(0.1 + 0.8 * attempt / planned)
                    if best is None or len(candidate) < len(best):
                        best = candidate
                        best_dimensions = resized.size
                    if profile == "size" and len(candidate) <= TARGET_BYTES:
                        best = candidate
                        best_dimensions = resized.size
                        break
                if profile == "size" and len(best) <= TARGET_BYTES:
                    break
            target.write_bytes(best)
            detail = f"{best_dimensions[0]}×{best_dimensions[1]}"
            if profile == "size":
                detail += " · " + (
                    "1MB 목표 달성"
                    if len(best) <= TARGET_BYTES
                    else "화질 하한으로 중단 · 1MB 목표 미달"
                )
        check()
        with Image.open(target) as verify:
            verify.load()
            if transparent and ("A" not in verify.getbands() and "transparency" not in verify.info):
                raise RuntimeError("투명도 검증 실패")
        return target, output_suffix, detail


def compress_image_ratio(source, folder, ratio, protect_text, strip, check, tick):
    target = folder / "image.tmp"
    suffix = source.suffix.lower()
    if suffix == ".ico":
        raise SkipCompression("여러 크기 아이콘 보존을 위해 ICO는 건너뜁니다.")
    effective = 1 if protect_text else ratio
    if suffix in {".tif", ".tiff"}:
        return compress_tiff(source, target, strip, check, tick, effective)
    with Image.open(source) as original:
        if getattr(original, "n_frames", 1) > 1:
            raise SkipCompression("애니메이션의 모든 프레임 보존을 위해 건너뜁니다.")
        check()
        image = ImageOps.exif_transpose(original)
        image.load()
        transparent = "transparency" in image.info or "A" in image.getbands()
        if image.mode == "P":
            image = image.convert("RGBA" if transparent else "RGB")
        size = (max(1, round(image.width * effective)), max(1, round(image.height * effective)))
        if effective < 1:
            image = image.resize(size, Image.Resampling.LANCZOS, reducing_gap=3)
        check()
        tick(0.6)
        fmt = (
            "PNG"
            if transparent or suffix in {".png", ".bmp", ".gif"}
            else "WEBP" if suffix == ".webp" else "JPEG"
        )
        target.write_bytes(encoded(image, fmt, 95, strip))
        check()
        tick(0.9)
        with Image.open(target) as verify:
            verify.load()
            if verify.size != size:
                raise RuntimeError("축소 해상도 검증 실패")
        return (
            target,
            {"PNG": ".png", "WEBP": ".webp", "JPEG": ".jpeg"}[fmt],
            f"{size[0]}×{size[1]} · 가로·세로 원본의 {effective:.0%}"
            + (" · 글자 보호로 해상도 유지" if protect_text else ""),
        )
