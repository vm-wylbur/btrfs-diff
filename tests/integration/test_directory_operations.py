# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.05.13
# License: (c) HRDAG, 2025, GPL-2 or newer
#
# ------
# tests/integration/test_directory_operations.py
"""Integration tests for directory operations in btrfs-diff."""

import shutil
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
def test_directory_deletion_with_files(btrfs_test_path):
    """
    Test that directory deletions with files inside are properly detected.
    
    This test reproduces the reported bug where btrfs-diff fails to detect
    directory deletions, missing both the files within the directory and the
    directory removal itself.
    """
    
    def setup(work_dir: Path):
        """Create a directory with a file inside."""
        test_dir = work_dir / "pball" / "tmp" / "test_delete"
        test_dir.mkdir(parents=True)
        (test_dir / "file.txt").write_text("test content")
    
    def modify(work_dir: Path):
        """Delete the directory and its contents."""
        test_dir = work_dir / "pball" / "tmp" / "test_delete"
        shutil.rmtree(test_dir)
    
    # Create test environment and run btrfs-diff
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Verify the test setup worked correctly
    assert (env.before_snapshot / "pball" / "tmp" / "test_delete" / "file.txt").exists(), \
        "File should exist in before snapshot"
    assert not (env.after_snapshot / "pball" / "tmp" / "test_delete").exists(), \
        "Directory should not exist in after snapshot"
    
    # Extract deletions from diff output
    deletions = [c for c in env.diff_output if c.action == "deleted"]
    
    # Debug output
    print(f"\nTotal changes detected: {len(env.diff_output)}")
    print(f"Deletions detected: {len(deletions)}")
    for deletion in deletions:
        print(f"  - {deletion.path} ({deletion.details.command})")
    
    # Show all changes for debugging
    if len(env.diff_output) > 0:
        print("\nAll changes detected:")
        for change in env.diff_output:
            print(f"  - {change.action}: {change.path} ({change.details.command})")
    
    # Verify we detect both the file and directory deletion
    assert len(deletions) >= 2, (
        f"Expected at least 2 deletions (file + directory), "
        f"but found {len(deletions)}"
    )
    
    # Check for file deletion
    file_deletion = next(
        (d for d in deletions if d.path.endswith("file.txt")), None
    )
    assert file_deletion is not None, "File deletion not detected"
    assert file_deletion.details.command == "unlink", (
        f"Expected 'unlink' command for file, got "
        f"'{file_deletion.details.command}'"
    )
    
    # Check for directory deletion
    dir_deletion = next(
        (d for d in deletions if d.path.endswith("test_delete")), None
    )
    assert dir_deletion is not None, "Directory deletion not detected"
    assert dir_deletion.details.command == "rmdir", (
        f"Expected 'rmdir' command for directory, got "
        f"'{dir_deletion.details.command}'"
    )


@pytest.mark.btrfs_required
def test_empty_directory_deletion(btrfs_test_path):
    """Test that empty directory deletions are detected."""
    
    def setup(work_dir: Path):
        """Create an empty directory."""
        test_dir = work_dir / "empty_dir"
        test_dir.mkdir(parents=True)
    
    def modify(work_dir: Path):
        """Delete the empty directory."""
        test_dir = work_dir / "empty_dir"
        test_dir.rmdir()
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    deletions = [c for c in env.diff_output if c.action == "deleted"]
    
    assert len(deletions) == 1, (
        f"Expected 1 deletion for empty directory, found {len(deletions)}"
    )
    assert deletions[0].path.endswith("empty_dir")
    assert deletions[0].details.command == "rmdir"


@pytest.mark.btrfs_required
def test_nested_directory_deletion(btrfs_test_path):
    """Test detection of nested directory structure deletion."""
    
    def setup(work_dir: Path):
        """Create nested directories with files."""
        base = work_dir / "nested"
        sub1 = base / "level1"
        sub2 = sub1 / "level2"
        sub2.mkdir(parents=True)
        
        (base / "file1.txt").write_text("level 0")
        (sub1 / "file2.txt").write_text("level 1")
        (sub2 / "file3.txt").write_text("level 2")
    
    def modify(work_dir: Path):
        """Delete the entire nested structure."""
        shutil.rmtree(work_dir / "nested")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    deletions = [c for c in env.diff_output if c.action == "deleted"]
    
    # Should detect: 3 files + 3 directories
    assert len(deletions) >= 6, (
        f"Expected at least 6 deletions, found {len(deletions)}"
    )
    
    # Verify all files detected
    file_paths = ["file1.txt", "file2.txt", "file3.txt"]
    for filename in file_paths:
        assert any(d.path.endswith(filename) for d in deletions), (
            f"File {filename} deletion not detected"
        )
    
    # Verify all directories detected
    dir_paths = ["nested", "level1", "level2"]
    for dirname in dir_paths:
        assert any(
            d.path.endswith(dirname) and d.details.command == "rmdir"
            for d in deletions
        ), f"Directory {dirname} deletion not detected"


@pytest.mark.btrfs_required
def test_directory_rename(btrfs_test_path):
    """Verify that directory renames are still detected correctly."""
    
    def setup(work_dir: Path):
        """Create a directory with content."""
        test_dir = work_dir / "original_name"
        test_dir.mkdir()
        (test_dir / "content.txt").write_text("test file")
    
    def modify(work_dir: Path):
        """Rename the directory."""
        old_path = work_dir / "original_name"
        new_path = work_dir / "new_name"
        old_path.rename(new_path)
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    renames = [c for c in env.diff_output if c.action == "renamed"]
    
    assert len(renames) >= 1, "Directory rename not detected"
    
    dir_rename = next(
        (r for r in renames if r.path.endswith("original_name")), None
    )
    assert dir_rename is not None
    assert dir_rename.details.command == "rename"
    assert hasattr(dir_rename.details, "path_to")
    assert dir_rename.details.path_to.endswith("new_name")


@pytest.mark.btrfs_required
def test_directory_to_symlink(btrfs_test_path):
    """Test replacing a directory with a symlink to another location."""
    
    def setup(work_dir: Path):
        """Create a directory and a target for symlink."""
        test_dir = work_dir / "will_be_symlink"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("original content")
        
        target_dir = work_dir / "symlink_target"
        target_dir.mkdir()
        (target_dir / "target.txt").write_text("target content")
    
    def modify(work_dir: Path):
        """Replace directory with symlink."""
        test_dir = work_dir / "will_be_symlink"
        target_dir = work_dir / "symlink_target"
        
        # Remove directory
        shutil.rmtree(test_dir)
        
        # Create symlink
        test_dir.symlink_to(target_dir)
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Should see deletions and a new symlink
    deletions = [c for c in env.diff_output if c.action == "deleted"]
    modifications = [
        c for c in env.diff_output 
        if c.action == "modified" and c.details.command == "symlink"
    ]
    
    # Verify directory and its contents were deleted
    assert any(d.path.endswith("will_be_symlink") for d in deletions)
    assert any(d.path.endswith("file.txt") for d in deletions)
    
    # Verify symlink creation
    assert len(modifications) >= 1, "Symlink creation not detected"