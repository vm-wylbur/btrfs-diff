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
# btrfs-diff/src/btrfs_diff/types.py

"""Type definitions for btrfs snapshot diff operations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal


ActionType = Literal["modified", "deleted", "renamed"]


@dataclass(frozen=True)
class ChangeDetails:
    """Details of a specific btrfs command."""
    command: str
    path: str
    path_to: str | None = None
    path_link: str | None = None
    size: int | None = None
    inode: int | None = None
    file_offset: int | None = None


@dataclass(frozen=True)
class FileChange:
    """Represents a single file change between snapshots."""
    path: str
    action: ActionType
    details: ChangeDetails


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a set of changes."""
    validated: int
    missing: int
    mismatched_targets: int = 0
    actually_deleted: int = 0
    found_in_new: int = 0
    missing_from_old: int = 0
    file_exists: int = 0
    file_missing: int = 0
    mtime_in_range: int = 0
    mtime_out_of_range: int = 0
    permission_errors: int = 0