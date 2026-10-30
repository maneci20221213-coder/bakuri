"""Compatibility imports for the pre-package API."""

from bakuri.domain.rename_rules import (
    RESERVED,
    invalid,
    insert_token,
    _text_lines,
    pasted_lines,
    fill_down,
)
from bakuri.renaming.storage import identity, key, write_journal, move
from bakuri.renaming.planner import preview
from bakuri.renaming.transaction import apply, undo

__all__ = [
    "RESERVED",
    "invalid",
    "insert_token",
    "_text_lines",
    "pasted_lines",
    "fill_down",
    "identity",
    "key",
    "write_journal",
    "move",
    "preview",
    "apply",
    "undo",
]
