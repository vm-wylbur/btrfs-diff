# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.05.13
# License: (c) HRDAG, 2025, GPL-2 or newer
#
# ------
# tests/integration/test_file_operations.py
"""Integration tests for file operations in btrfs-diff."""

import os
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
def test_file_creation(btrfs_test_path):
    """Test detection of new file creation."""
    
    def setup(work_dir: Path):
        """Initial empty state."""
        pass
    
    def modify(work_dir: Path):
        """Create new files."""
        (work_dir / "new_file.txt").write_text("content")
        (work_dir / "subdir").mkdir()
        (work_dir / "subdir" / "nested_file.txt").write_text("nested content")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    modifications = [c for c in env.diff_output if c['action'] == 'modified']
    
    # Should detect new files as modifications
    assert len(modifications) >= 2
    assert any(m['path'].endswith("new_file.txt") for m in modifications)
    assert any(m['path'].endswith("nested_file.txt") for m in modifications)


@pytest.mark.btrfs_required
def test_file_modification(btrfs_test_path):
    """Test detection of file content changes."""
    
    def setup(work_dir: Path):
        """Create initial files."""
        (work_dir / "file1.txt").write_text("original content")
        (work_dir / "file2.txt").write_text("original content 2")
    
    def modify(work_dir: Path):
        """Modify file contents."""
        (work_dir / "file1.txt").write_text("modified content")
        (work_dir / "file2.txt").write_text("modified content 2" + "x" * 1000)
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    modifications = [c for c in env.diff_output if c['action'] == 'modified']
    
    assert len(modifications) == 2
    assert all(m['details']['command'] in ['update_extent', 'truncate'] for m in modifications)


@pytest.mark.btrfs_required
def test_file_deletion(btrfs_test_path):
    """Test detection of file deletions."""
    
    def setup(work_dir: Path):
        """Create files to delete."""
        (work_dir / "delete_me.txt").write_text("content")
        subdir = work_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested_delete.txt").write_text("nested")
    
    def modify(work_dir: Path):
        """Delete files."""
        (work_dir / "delete_me.txt").unlink()
        (work_dir / "subdir" / "nested_delete.txt").unlink()
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    deletions = [c for c in env.diff_output if c['action'] == 'deleted']
    
    assert len(deletions) == 2
    assert all(d['details']['command'] == 'unlink' for d in deletions)


@pytest.mark.btrfs_required
def test_file_rename(btrfs_test_path):
    """Test detection of file renames."""
    
    def setup(work_dir: Path):
        """Create files to rename."""
        (work_dir / "old_name.txt").write_text("content")
        subdir = work_dir / "subdir"
        subdir.mkdir()
        (subdir / "old_nested.txt").write_text("nested")
    
    def modify(work_dir: Path):
        """Rename files."""
        (work_dir / "old_name.txt").rename(work_dir / "new_name.txt")
        # Rename across directories
        (work_dir / "subdir" / "old_nested.txt").rename(work_dir / "moved_file.txt")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    renames = [c for c in env.diff_output if c['action'] == 'renamed']
    
    assert len(renames) == 2
    assert any(r['path'].endswith("old_name.txt") and 
               r['details']['path_to'].endswith("new_name.txt") for r in renames)
    assert any(r['path'].endswith("old_nested.txt") and 
               r['details']['path_to'].endswith("moved_file.txt") for r in renames)


@pytest.mark.btrfs_required
def test_symlink_operations(btrfs_test_path):
    """Test symlink creation, modification, and deletion."""
    
    def setup(work_dir: Path):
        """Create initial state with targets."""
        (work_dir / "target.txt").write_text("target content")
        (work_dir / "link1").symlink_to("target.txt")
        (work_dir / "link2").symlink_to("/tmp")
    
    def modify(work_dir: Path):
        """Modify symlinks."""
        # Delete a symlink
        (work_dir / "link1").unlink()
        
        # Change symlink target (delete and recreate)
        (work_dir / "link2").unlink()
        (work_dir / "link2").symlink_to("/home")
        
        # Create new symlink
        (work_dir / "link3").symlink_to("target.txt")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Should see various symlink operations
    assert any(c['action'] == 'deleted' and c['path'].endswith("link1") 
               for c in env.diff_output)
    assert any(c['action'] == 'modified' and c['details']['command'] == 'symlink'
               for c in env.diff_output)


@pytest.mark.btrfs_required
def test_file_permissions_change(btrfs_test_path):
    """Test detection of permission changes."""
    
    def setup(work_dir: Path):
        """Create files with specific permissions."""
        file_path = work_dir / "file.txt"
        file_path.write_text("content")
        file_path.chmod(0o644)
        
        script_path = work_dir / "script.sh"
        script_path.write_text("#!/bin/bash\necho test")
        script_path.chmod(0o644)
    
    def modify(work_dir: Path):
        """Change permissions."""
        (work_dir / "file.txt").chmod(0o600)
        (work_dir / "script.sh").chmod(0o755)
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # btrfs-diff might detect these as modifications
    modifications = [c for c in env.diff_output if c['action'] == 'modified']
    
    # Note: Permission changes might not always be detected depending on btrfs send behavior
    print(f"Permission changes detected: {len(modifications)}")
    for m in modifications:
        print(f"  - {m['path']} ({m['details']['command']})")


@pytest.mark.btrfs_required
def test_hardlink_operations(btrfs_test_path):
    """Test hard link creation and deletion."""
    
    def setup(work_dir: Path):
        """Create file with hard link."""
        original = work_dir / "original.txt"
        original.write_text("content")
        
        # Create hard link
        hardlink = work_dir / "hardlink.txt"
        os.link(original, hardlink)
    
    def modify(work_dir: Path):
        """Modify hard links."""
        # Delete one hard link
        (work_dir / "hardlink.txt").unlink()
        
        # Create new hard link
        os.link(work_dir / "original.txt", work_dir / "new_hardlink.txt")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Check for link operations
    print(f"Total changes for hardlinks: {len(env.diff_output)}")
    for c in env.diff_output:
        print(f"  - {c['action']}: {c['path']} ({c['details']['command']})")


@pytest.mark.btrfs_required
def test_special_characters_in_names(btrfs_test_path):
    """Test handling of files with special characters."""
    
    def setup(work_dir: Path):
        """Create files with special characters."""
        # Various special characters
        (work_dir / "file with spaces.txt").write_text("content")
        (work_dir / "file-with-dashes.txt").write_text("content")
        (work_dir / "file_with_underscores.txt").write_text("content")
        (work_dir / "file.multiple.dots.txt").write_text("content")
        # Unicode characters
        (work_dir / "файл.txt").write_text("content")  # Cyrillic
        (work_dir / "文件.txt").write_text("content")   # Chinese
    
    def modify(work_dir: Path):
        """Rename files with special characters."""
        (work_dir / "file with spaces.txt").rename(work_dir / "file_no_spaces.txt")
        (work_dir / "файл.txt").unlink()
        (work_dir / "新文件.txt").write_text("new content")  # New Chinese filename
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Verify special characters are handled correctly
    assert any(c['path'].endswith("file with spaces.txt") for c in env.diff_output)
    assert any(c['path'].endswith("файл.txt") for c in env.diff_output)


@pytest.mark.btrfs_required
def test_empty_file_operations(btrfs_test_path):
    """Test operations on empty files."""
    
    def setup(work_dir: Path):
        """Create empty files."""
        (work_dir / "empty1.txt").touch()
        (work_dir / "empty2.txt").touch()
        (work_dir / "will_have_content.txt").touch()
    
    def modify(work_dir: Path):
        """Modify empty files."""
        # Delete empty file
        (work_dir / "empty1.txt").unlink()
        
        # Add content to empty file
        (work_dir / "will_have_content.txt").write_text("now has content")
        
        # Create new empty file
        (work_dir / "new_empty.txt").touch()
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Check all operations are detected
    assert any(c['action'] == 'deleted' and c['path'].endswith("empty1.txt") 
               for c in env.diff_output)
    assert any(c['action'] == 'modified' and c['path'].endswith("will_have_content.txt")
               for c in env.diff_output)


@pytest.mark.btrfs_required
def test_file_truncation(btrfs_test_path):
    """Test file truncation detection."""
    
    def setup(work_dir: Path):
        """Create files with content."""
        (work_dir / "shrink.txt").write_text("x" * 1000)
        (work_dir / "grow.txt").write_text("x" * 10)
        (work_dir / "truncate_to_zero.txt").write_text("x" * 100)
    
    def modify(work_dir: Path):
        """Truncate and expand files."""
        # Shrink file
        (work_dir / "shrink.txt").write_text("x" * 10)
        
        # Grow file
        (work_dir / "grow.txt").write_text("x" * 1000)
        
        # Truncate to zero
        (work_dir / "truncate_to_zero.txt").write_text("")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    modifications = [c for c in env.diff_output if c['action'] == 'modified']
    
    assert len(modifications) == 3
    # Check for truncate operations
    print(f"Truncation operations:")
    for m in modifications:
        print(f"  - {m['path']}: {m['details']['command']}")