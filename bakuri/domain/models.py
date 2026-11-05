"""Immutable values passed across the UI/worker boundary. No GUI or engines."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
from uuid import uuid4


class OutputFormat(StrEnum):
    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    HWPX = "hwpx"
    XLSX = "xlsx"
    DOCX = "docx"
    PPTX = "pptx"

    @classmethod
    def parse(cls, value):
        text = str(value).lower()
        return cls("jpeg" if text == "jpg" else text)


class JobKind(StrEnum):
    CONVERT = "convert"
    COMPRESS = "compress"


class JobOutcome(StrEnum):
    DONE = "done"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class InputFile:
    path: str
    file_id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self):
        object.__setattr__(self, "path", str(Path(self.path).absolute()))


@dataclass(frozen=True, slots=True)
class ConversionOptions:
    dpi: int = 150
    image_mode: str = "background"
    orientation: str = "auto"
    output_mode: str = "source"
    output_folder: str = ""

    def __post_init__(self):
        if not 1 <= self.dpi <= 1200:
            raise ValueError("이미지 해상도 설정을 확인해 주세요.")
        if self.image_mode not in {"background", "inline"}:
            raise ValueError("이미지 배치 설정을 확인해 주세요.")

        if self.orientation not in {"auto", "landscape", "portrait"}:
            raise ValueError("PDF 용지 방향을 확인해 주세요.")
        if self.output_mode not in {"source", "subfolder", "custom"}:
            raise ValueError("변환 파일 저장 위치를 확인해 주세요.")
        if self.output_mode == "custom" and not Path(self.output_folder).is_absolute():
            raise ValueError("변환 파일을 저장할 폴더를 지정해 주세요.")

    def as_kwargs(self):
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class CompressionOptions:
    profile: str = "p80"
    protect_text: bool = False
    strip_metadata: bool = False

    def as_kwargs(self):
        return dict(
            profile=self.profile, protect_text=self.protect_text, strip_metadata=self.strip_metadata
        )


@dataclass(frozen=True, slots=True)
class MultiImageSelection:
    path: str
    count: int
    primary: int
    mode: str = "primary"
    auxiliary: bool = False
    fingerprint: tuple[int, int] = ()

    def __post_init__(self):
        object.__setattr__(self, "path", str(Path(self.path).absolute()))
        object.__setattr__(self, "fingerprint", tuple(self.fingerprint))
        if self.mode not in {"primary", "all"} or not 0 <= self.primary < self.count:
            raise ValueError("이미지 처리 범위를 다시 선택해 주세요.")


@dataclass(frozen=True, slots=True)
class ConversionRequest:
    files: tuple[InputFile, ...]
    output: OutputFormat
    merge: bool = False
    options: ConversionOptions = field(default_factory=ConversionOptions)
    multi_images: tuple[MultiImageSelection, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "files", tuple(self.files))
        object.__setattr__(self, "multi_images", tuple(self.multi_images))
        object.__setattr__(self, "output", OutputFormat.parse(self.output))


@dataclass(frozen=True, slots=True)
class CompressionRequest:
    files: tuple[InputFile, ...]
    options: CompressionOptions = field(default_factory=CompressionOptions)
    multi_images: tuple[MultiImageSelection, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "files", tuple(self.files))
        object.__setattr__(self, "multi_images", tuple(self.multi_images))


@dataclass(frozen=True, slots=True)
class PdfPagesRequest:
    file: InputFile
    mode: str = "interval"
    every: int = 1
    selection: str = ""
    separate: bool = False


@dataclass(frozen=True, slots=True)
class CompressionRow:
    source: str
    before: int
    after: int
    output: str = ""
    status: str = "축소 효과 없음"
    detail: str = ""

    def as_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class JobReport:
    kind: JobKind
    outcome: JobOutcome
    paths: tuple[str, ...] = ()
    rows: tuple[CompressionRow, ...] = ()
    error: str = ""
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RenameOptions:
    find: str = ""
    replace: str = ""
    prefix: str = ""
    suffix: str = ""
    base: str = ""
    start: int = 1
    digits: int = 1
    number_enabled: bool | None = None
    number_position: str = "after"
    number_marker: str = ""
    separator: str = "_"
    text_by_source: Mapping[str, str] = field(default_factory=dict)
    text_position: str = "before"
    text_marker: str = ""
    text_mode: str = "insert"
    string: str = ""
    string_position: str = "before"
    string_marker: str = ""
    manual_names: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self):
        for name in ("text_by_source", "manual_names"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))

    def as_kwargs(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}
