# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.05.13
# License: (c) HRDAG, 2025, GPL-2 or newer
#
# ------
# tests/fixtures/btrfs_snapshot_fixture.py
"""Reusable fixture for creating btrfs test environments with snapshots.

NOTE: This fixture requires sudo privileges to:
- Create and manage btrfs subvolumes
- Create read-only snapshots
- Delete subvolumes during cleanup

Tests using this fixture should be marked with @pytest.mark.btrfs_required
and run with the --run-btrfs-tests flag.
"""

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from btrfs_diff import BtrfsParser
from btrfs_diff.types import FileChange


@dataclass
class BtrfsTestEnvironment:
    """Container for btrfs test environment paths and results."""
    
    test_root: Path  # /path/to/btrfs/btrfs-diff-test-<random>/
    before_snapshot: Path  # .../before/
    after_snapshot: Path  # .../after/
    working_dir: Path  # .../work/ (where changes are made)
    diff_output: List[FileChange]  # Parsed diff results
    raw_diff: str  # Raw JSON output


def create_btrfs_test_environment(
    btrfs_path: Path,
    setup_func: Callable[[Path], None],
    modify_func: Callable[[Path], None],
    cleanup: bool = True,
) -> BtrfsTestEnvironment:
    """
    Create a test environment with before/after btrfs snapshots.
    
    This function creates a temporary directory structure on a btrfs filesystem,
    sets up initial state, creates a snapshot, applies modifications, creates
    another snapshot, and runs btrfs-diff to capture the changes.
    
    Args:
        btrfs_path: Path to a btrfs filesystem where tests will be created
        setup_func: Function to create initial state in working directory
        modify_func: Function to apply changes to working directory
        cleanup: Whether to cleanup test directory after completion
        
    Returns:
        BtrfsTestEnvironment containing paths and diff results
        
    Raises:
        subprocess.CalledProcessError: If btrfs commands fail
        PermissionError: If sudo access is not available
    """
    # Create unique test directory with random suffix
    test_dir_name = f"btrfs-diff-test-{next(tempfile._get_candidate_names())}"
    test_root = btrfs_path / test_dir_name
    
    # Ensure we're on a btrfs filesystem
    _verify_btrfs_filesystem(btrfs_path)
    
    try:
        # Create test directory structure
        test_root.mkdir(exist_ok=True)
        working_dir = test_root / "work"
        before_snapshot = test_root / "before"
        after_snapshot = test_root / "after"
        
        # Create working subvolume
        subprocess.run(
            ["sudo", "btrfs", "subvolume", "create", str(working_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        
        # Run setup function to create initial state
        # Need to make the working directory writable by the current user
        subprocess.run(
            ["sudo", "chmod", "777", str(working_dir)],
            check=True,
            capture_output=True,
        )
        setup_func(working_dir)
        
        # Create before snapshot
        subprocess.run(
            ["sudo", "btrfs", "subvolume", "snapshot", "-r", 
             str(working_dir), str(before_snapshot)],
            check=True,
            capture_output=True,
            text=True,
        )
        
        # Apply modifications
        modify_func(working_dir)
        
        # Create after snapshot
        subprocess.run(
            ["sudo", "btrfs", "subvolume", "snapshot", "-r",
             str(working_dir), str(after_snapshot)],
            check=True,
            capture_output=True,
            text=True,
        )
        
        # Run btrfs-diff to get changes
        parser = BtrfsParser(str(before_snapshot), str(after_snapshot))
        diff_output = parser.get_changes()
        raw_diff = json.dumps(
            [change.to_dict() for change in diff_output], indent=2
        )
        
        return BtrfsTestEnvironment(
            test_root=test_root,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            working_dir=working_dir,
            diff_output=diff_output,
            raw_diff=raw_diff,
        )
        
    except Exception:
        # Cleanup on error if requested
        if cleanup and test_root.exists():
            _cleanup_test_directory(test_root)
        raise
        
    finally:
        # Cleanup if requested and no exception
        if cleanup and test_root.exists():
            _cleanup_test_directory(test_root)


def _verify_btrfs_filesystem(path: Path) -> None:
    """Verify that the given path is on a btrfs filesystem."""
    try:
        # Create directory if it doesn't exist
        path.mkdir(parents=True, exist_ok=True)
        
        # Use df to find the mount point for this path
        result = subprocess.run(
            ["df", "--output=fstype", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        # df output has header line, filesystem type is on second line
        lines = result.stdout.strip().split('\n')
        if len(lines) >= 2 and lines[1].strip() != "btrfs":
            raise ValueError(
                f"Path {path} is not on a btrfs filesystem "
                f"(found: {lines[1].strip()})"
            )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to verify filesystem type: {e}")


def _cleanup_test_directory(test_root: Path) -> None:
    """Clean up test directory and all subvolumes."""
    try:
        # Find all subvolumes under test_root
        result = subprocess.run(
            ["sudo", "btrfs", "subvolume", "list", str(test_root.parent)],
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0:
            # Find subvolumes that are under our test directory
            subvols_to_delete = []
            for line in result.stdout.strip().split("\n"):
                if line and str(test_root.name) in line:
                    # Extract the subvolume path
                    parts = line.split()
                    if len(parts) >= 9:
                        # The path is the last element
                        subvol_path = Path("/") / parts[-1]
                        subvols_to_delete.append(subvol_path)
            
            # Delete subvolumes in reverse order (deepest first)
            for subvol in reversed(subvols_to_delete):
                subprocess.run(
                    ["sudo", "btrfs", "subvolume", "delete", str(subvol)],
                    capture_output=True,
                )
        
        # Remove the test directory
        if test_root.exists():
            subprocess.run(["sudo", "rm", "-rf", str(test_root)], capture_output=True)
            
    except Exception as e:
        print(f"Warning: Failed to cleanup {test_root}: {e}")