# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.06.09
# License: (c) HRDAG, 2025, GPL-2 or newer
#
# ------
# btrfs-diff/src/btrfs_diff/__init__.py

"""Btrfs snapshot diff parser and validator."""

from .parser import BtrfsParser, get_btrfs_diff
from .validator import (
    validate_deletions,
    validate_modifications, 
    validate_symlinks_targeted
)
from .types import FileChange, ChangeDetails, ValidationResult

__version__ = "0.1.0"

__all__ = [
    "BtrfsParser",
    "get_btrfs_diff", 
    "validate_deletions",
    "validate_modifications",
    "validate_symlinks_targeted",
    "FileChange",
    "ChangeDetails", 
    "ValidationResult",
]