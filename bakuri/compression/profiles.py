"""Compression choices and limits shared by UI and adapters."""

TARGET_BYTES = 1_000_000
PROFILES = {
    "lossless": dict(label="픽셀 유지", long=0, quality=0, photo_dpi=0, scan_dpi=0),
    "quality": dict(label="화질 우선", long=3200, quality=92, photo_dpi=250, scan_dpi=300),
    "size": dict(
        label="용량 우선 · 사진 1MB 목표", long=2560, quality=88, photo_dpi=200, scan_dpi=250
    ),
}

RATIO_PROFILES = {
    f"p{p}": dict(
        label=f"{100-p}% 축소 · 원본의 {p}%", ratio=p / 100, quality=95, photo_dpi=0, scan_dpi=0
    )
    for p in range(90, 0, -10)
}
PROFILES.update(RATIO_PROFILES)


class SkipCompression(Exception):
    pass
