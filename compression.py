"""Compatibility imports. Encoding and orchestration have separate owners."""

from bakuri.compression.profiles import PROFILES, RATIO_PROFILES, TARGET_BYTES, SkipCompression
from bakuri.compression.images import (
    text_like,
    resize,
    metadata,
    encoded,
    compress_tiff,
    compress_image,
    compress_image_ratio,
)
from bakuri.compression.pdf import pdf_colorspace, pdf_snapshot, compress_pdf
from bakuri.compression.service import compress

__all__ = [
    "PROFILES",
    "RATIO_PROFILES",
    "TARGET_BYTES",
    "SkipCompression",
    "text_like",
    "resize",
    "metadata",
    "encoded",
    "compress_tiff",
    "compress_image",
    "compress_image_ratio",
    "pdf_colorspace",
    "pdf_snapshot",
    "compress_pdf",
    "compress",
]
