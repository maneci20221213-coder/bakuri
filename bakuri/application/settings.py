"""Read settings once on the UI thread; pass immutable options to workers."""

from typing import Protocol
from bakuri.domain.models import CompressionOptions, ConversionOptions, OutputLocation
from bakuri.compression.profiles import RATIO_PROFILES


class SettingsStore(Protocol):
    def value(self, key, defaultValue=None, **kwargs): ...


def output_location(settings: SettingsStore) -> OutputLocation:
    mode = settings.value("output_mode", "smart")
    folder = settings.value("output_folder", "")
    return OutputLocation(
        mode if mode in {"smart", "source", "subfolder", "custom"} else "smart", folder
    )


def conversion_options(settings: SettingsStore, orientation="auto") -> ConversionOptions:
    dpi = settings.value("dpi", 150, type=int)
    if dpi not in {96, 150, 200, 300}:
        dpi = 150
    mode = settings.value("image_mode", "background")
    location = output_location(settings)
    return ConversionOptions(
        dpi,
        mode if mode in {"background", "inline"} else "background",
        orientation,
        location.mode,
        location.folder,
    )


def compression_options(settings: SettingsStore) -> CompressionOptions:
    profile = settings.value("compress_profile", "p80")
    return CompressionOptions(
        profile if profile in RATIO_PROFILES else "p80",
        settings.value("compress_protect", False, type=bool),
        settings.value("compress_strip", False, type=bool),
    )
