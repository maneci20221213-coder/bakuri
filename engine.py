"""Compatibility imports. New code imports the owning bakuri module directly."""

from bakuri.domain.formats import (
    IMAGES,
    HANCOM,
    SPREADSHEETS,
    WORDS,
    PRESENTATIONS,
    SUPPORTED,
    can_convert,
    can_merge,
)
from bakuri.conversion.office import OfficeSession, office, text_import_options
from bakuri.conversion.pdf import to_pdf
from bakuri.conversion.service import convert

__all__ = [
    "IMAGES",
    "HANCOM",
    "SPREADSHEETS",
    "WORDS",
    "PRESENTATIONS",
    "SUPPORTED",
    "can_convert",
    "can_merge",
    "OfficeSession",
    "office",
    "text_import_options",
    "to_pdf",
    "convert",
]
