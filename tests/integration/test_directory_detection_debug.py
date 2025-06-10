# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.06.10
# License: (c) HRDAG, 2025, GPL-2 or newer
#
# ------
# tests/integration/test_directory_detection_debug.py

"""Debug test to understand exactly what btrfs-diff reports for directories."""

from pathlib import Path

import pytest

from tests.fixtures.btrfs_snapshot_fixture import (
    create_btrfs_test_environment,
)


@pytest.fixture
def btrfs_test_path(request):
    """Get the btrfs path from command line option."""
    return Path(request.config.getoption("--btrfs-path"))


@pytest.mark.btrfs_required
def test_directory_with_content_creation(btrfs_test_path):
    """Test what btrfs-diff reports when directories with content are created."""
    def setup(work_dir):
        """Initial state."""
        pass
    
    def modify(work_dir):
        """Create directory with content."""
        test_dir = work_dir / "content_dir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True
    )
    
    print(f"\nDirectory with content - Found {len(env.diff_output)} changes:")
    for i, change in enumerate(env.diff_output):
        print(f"  {i}: {change}")


@pytest.mark.btrfs_required
def test_directory_deletion_scenario(btrfs_test_path):
    """Test what happens when we delete directories - reproducing production scenario."""
    def setup(work_dir):
        """Create initial directories with content."""
        # Create multiple directories with content like production
        for i in range(3):
            dir_path = work_dir / f"dir_{i}"
            dir_path.mkdir()
            (dir_path / "content.txt").write_text(f"content {i}")
    
    def modify(work_dir):
        """Delete one directory."""
        dir_to_delete = work_dir / "dir_1"
        # Delete the file first, then directory
        (dir_to_delete / "content.txt").unlink()
        dir_to_delete.rmdir()
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True
    )
    
    print(f"\nDirectory deletion - Found {len(env.diff_output)} changes:")
    for i, change in enumerate(env.diff_output):
        print(f"  {i}: {change}")


@pytest.mark.btrfs_required  
def test_mkdir_command_availability(btrfs_test_path):
    """Test if mkdir commands are available when directories have content."""
    def setup(work_dir):
        """Initial state."""
        pass
    
    def modify(work_dir):
        """Create directory and immediately add content."""
        test_dir = work_dir / "mkdir_test"
        test_dir.mkdir()  # This should generate mkdir command
        (test_dir / "immediate.txt").write_text("immediate content")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True
    )
    
    print(f"\nMkdir with immediate content - Found {len(env.diff_output)} changes:")
    for i, change in enumerate(env.diff_output):
        print(f"  {i}: {change}")
        # Check if any command is 'mkdir'
        if change['details'].get('command') == 'mkdir':
            print(f"    *** FOUND MKDIR COMMAND! ***")


if __name__ == "__main__":
    pytest.main([__file__])