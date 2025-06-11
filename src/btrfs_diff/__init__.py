# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.06.09
# Copyright (C) 2025 HRDAG https://hrdag.org
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
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
from .types import FileChange, ChangeDetails, ValidationResult, ActionType

__version__ = "0.1.1"

__all__ = [
    "BtrfsParser",
    "get_btrfs_diff", 
    "validate_deletions",
    "validate_modifications",
    "validate_symlinks_targeted",
    "FileChange",
    "ChangeDetails", 
    "ValidationResult",
    "ActionType",
]