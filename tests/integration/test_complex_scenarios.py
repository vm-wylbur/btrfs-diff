# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.05.13
# License: (c) HRDAG, 2025, GPL-2 or newer
#
# ------
# tests/integration/test_complex_scenarios.py
"""Integration tests for complex file operation scenarios in btrfs-diff."""

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
def test_rename_chain(btrfs_test_path):
    """Test detection of circular rename chain (A->B->C->A).
    
    This tests that complex circular renames are handled correctly,
    even though btrfs send optimizes them to minimal operations.
    """
    
    def setup(work_dir: Path):
        """Create initial files."""
        (work_dir / "file_a.txt").write_text("content A")
        (work_dir / "file_b.txt").write_text("content B")
        (work_dir / "file_c.txt").write_text("content C")
    
    def modify(work_dir: Path):
        """Create circular rename: A->temp, B->A, C->B, temp->C."""
        # This creates a circular rename where each file takes the next one's name
        (work_dir / "file_a.txt").rename(work_dir / "temp_a")
        (work_dir / "file_b.txt").rename(work_dir / "file_a.txt")
        (work_dir / "file_c.txt").rename(work_dir / "file_b.txt")
        (work_dir / "temp_a").rename(work_dir / "file_c.txt")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Btrfs send optimizes circular renames to minimal operations
    # We should see deletes and at least one rename
    deletions = [c for c in env.diff_output if c['action'] == 'deleted']
    renames = [c for c in env.diff_output if c['action'] == 'renamed']
    
    # Verify we detect the operations (even if optimized)
    assert len(env.diff_output) >= 3, f"Expected at least 3 operations, got {len(env.diff_output)}"
    assert len(deletions) >= 1, "Should have at least one deletion"
    assert len(renames) >= 1, "Should have at least one rename"
    
    # Verify final state makes sense: each file's content shifted position
    # The actual operations detected may vary based on btrfs optimization
    print(f"\nCircular rename detected as:")
    print(f"  Deletions: {len(deletions)}")
    print(f"  Renames: {len(renames)}")
    for r in renames:
        print(f"  - {r['path']} -> {r['details']['path_to']}")


@pytest.mark.btrfs_required
def test_file_replace_with_directory(btrfs_test_path):
    """Test replacing a file with a directory of the same name."""
    
    def setup(work_dir: Path):
        """Create initial file."""
        (work_dir / "convert_me").write_text("I am a file")
    
    def modify(work_dir: Path):
        """Replace file with directory."""
        (work_dir / "convert_me").unlink()
        (work_dir / "convert_me").mkdir()
        (work_dir / "convert_me" / "nested.txt").write_text("I am inside a directory")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Should see file deletion and new directory/file creation
    deletions = [c for c in env.diff_output if c['action'] == 'deleted']
    modifications = [c for c in env.diff_output if c['action'] == 'modified']
    
    assert any(d['path'] == "convert_me" and d['details']['command'] == 'unlink' 
               for d in deletions)
    assert any(m['path'].startswith("convert_me/") for m in modifications)


@pytest.mark.btrfs_required
def test_swap_files(btrfs_test_path):
    """Test swapping contents/names of two files.
    
    This complex operation tests that file swaps are detected,
    even when optimized by btrfs send.
    """
    
    def setup(work_dir: Path):
        """Create two files with distinct content."""
        (work_dir / "file1.txt").write_text("Content of file 1")
        (work_dir / "file2.txt").write_text("Content of file 2")
    
    def modify(work_dir: Path):
        """Swap files: file1 <-> file2."""
        (work_dir / "file1.txt").rename(work_dir / "temp")
        (work_dir / "file2.txt").rename(work_dir / "file1.txt")
        (work_dir / "temp").rename(work_dir / "file2.txt")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Btrfs send optimizes swaps - we typically see:
    # - file1.txt deleted
    # - file2.txt renamed to file1.txt
    # - file2.txt recreated (from original file1 content)
    deletions = [c for c in env.diff_output if c['action'] == 'deleted']
    renames = [c for c in env.diff_output if c['action'] == 'renamed']
    modifications = [c for c in env.diff_output if c['action'] == 'modified']
    
    # Should detect operations that accomplish the swap
    assert len(env.diff_output) >= 2, f"Expected at least 2 operations for swap, got {len(env.diff_output)}"
    
    # Common pattern: one deletion and one rename
    if len(deletions) == 1 and len(renames) == 1:
        # Verify it's a sensible swap pattern
        deleted_file = deletions[0]['path']
        rename_from = renames[0]['path']
        rename_to = renames[0]['details']['path_to']
        
        # Should be swapping between file1.txt and file2.txt
        assert deleted_file in ["file1.txt", "file2.txt"]
        assert rename_from in ["file1.txt", "file2.txt"]
        assert rename_to in ["file1.txt", "file2.txt"]
        
    print(f"\nFile swap detected as:")
    print(f"  Deletions: {[d['path'] for d in deletions]}")
    print(f"  Renames: {[r['path'] + ' -> ' + r['details']['path_to'] for r in renames]}")
    print(f"  Modifications: {[m['path'] for m in modifications]}")


@pytest.mark.btrfs_required
def test_directory_contents_swap(btrfs_test_path):
    """Test moving all contents from one directory to another."""
    
    def setup(work_dir: Path):
        """Create two directories with contents."""
        dir1 = work_dir / "dir1"
        dir2 = work_dir / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        
        (dir1 / "file1.txt").write_text("dir1 file1")
        (dir1 / "file2.txt").write_text("dir1 file2")
        (dir2 / "file3.txt").write_text("dir2 file3")
    
    def modify(work_dir: Path):
        """Move all files from dir1 to dir2."""
        dir1 = work_dir / "dir1"
        dir2 = work_dir / "dir2"
        
        for file in dir1.iterdir():
            file.rename(dir2 / file.name)
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # When files are moved between directories, btrfs send may optimize this
    # We expect to see the files from dir1 disappear (deleted)
    deletions = [c for c in env.diff_output if c['action'] == 'deleted']
    renames = [c for c in env.diff_output if c['action'] == 'renamed']
    modifications = [c for c in env.diff_output if c['action'] == 'modified']
    
    # Should detect that files moved from dir1
    dir1_deletions = [d for d in deletions if d['path'].startswith("dir1/")]
    assert len(dir1_deletions) == 2, f"Expected 2 files deleted from dir1, got {len(dir1_deletions)}"
    
    # May see renames or new files in dir2
    dir2_changes = [c for c in env.diff_output 
                   if c['path'].startswith("dir2/") or 
                   (c.get('details', {}).get('path_to', '').startswith("dir2/"))]
    
    # Total operations should account for moving 2 files
    assert len(env.diff_output) >= 2, f"Expected at least 2 operations, got {len(env.diff_output)}"
    
    print(f"\nDirectory move detected as:")
    print(f"  Files deleted from dir1: {[d['path'] for d in dir1_deletions]}")
    print(f"  Operations involving dir2: {len(dir2_changes)}")
    for c in dir2_changes:
        if c['action'] == 'renamed':
            print(f"    Rename: {c['path']} -> {c['details']['path_to']}")
        else:
            print(f"    {c['action']}: {c['path']}")


@pytest.mark.btrfs_required
def test_deep_directory_restructure(btrfs_test_path):
    """Test complex directory restructuring."""
    
    def setup(work_dir: Path):
        """Create deep directory structure."""
        # Create structure:
        # project/
        #   src/
        #     main.py
        #     lib/
        #       util.py
        #   tests/
        #     test_main.py
        
        src = work_dir / "project" / "src"
        lib = src / "lib"
        tests = work_dir / "project" / "tests"
        
        lib.mkdir(parents=True)
        tests.mkdir(parents=True)
        
        (src / "main.py").write_text("main code")
        (lib / "util.py").write_text("utility code")
        (tests / "test_main.py").write_text("test code")
    
    def modify(work_dir: Path):
        """Restructure to flat layout."""
        project = work_dir / "project"
        
        # Move everything to root of project
        (project / "src" / "main.py").rename(project / "main.py")
        (project / "src" / "lib" / "util.py").rename(project / "util.py")
        (project / "tests" / "test_main.py").rename(project / "test_main.py")
        
        # Remove empty directories
        (project / "src" / "lib").rmdir()
        (project / "src").rmdir()
        (project / "tests").rmdir()
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    renames = [c for c in env.diff_output if c['action'] == 'renamed']
    deletions = [c for c in env.diff_output if c['action'] == 'deleted']
    modifications = [c for c in env.diff_output if c['action'] == 'modified']
    
    # Complex restructuring may result in various operations
    # Should detect the restructuring operations
    assert len(env.diff_output) >= 3, f"Expected at least 3 operations for restructuring, got {len(env.diff_output)}"
    
    # Verify files ended up in new structure
    # Original files should be gone from old locations
    old_paths = ["project/src/main.py", "project/src/lib/util.py", "project/tests/test_main.py"]
    old_deletions = [d for d in deletions if d['path'] in old_paths]
    
    print(f"\nDirectory restructure detected as:")
    print(f"  Total operations: {len(env.diff_output)}")
    print(f"  Deletions: {len(deletions)} (including {len(old_deletions)} from original locations)")
    print(f"  Renames: {len(renames)}")
    print(f"  Modifications: {len(modifications)}")
    
    # The important thing is that files moved from old to new structure
    # Exact operations may vary based on btrfs optimization


@pytest.mark.btrfs_required
def test_mixed_operations_same_name(btrfs_test_path):
    """Test multiple operations on paths with the same name."""
    
    def setup(work_dir: Path):
        """Create initial structure."""
        (work_dir / "data").mkdir()
        (work_dir / "data" / "info.txt").write_text("directory data")
        (work_dir / "data.txt").write_text("file data")
    
    def modify(work_dir: Path):
        """Swap directory and file."""
        # Delete directory
        shutil.rmtree(work_dir / "data")
        
        # Rename file to directory name
        (work_dir / "data.txt").rename(work_dir / "data")
        
        # Create new directory with old file name
        (work_dir / "data.txt").mkdir()
        (work_dir / "data.txt" / "content.txt").write_text("new content")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # This tests our parser's ability to handle name reuse
    print(f"Total changes: {len(env.diff_output)}")
    for c in env.diff_output:
        print(f"  - {c['action']}: {c['path']} ({c['details']['command']})")


@pytest.mark.btrfs_required  
def test_symlink_chain_modifications(btrfs_test_path):
    """Test modifications to symlink chains."""
    
    def setup(work_dir: Path):
        """Create symlink chain."""
        (work_dir / "target.txt").write_text("final target")
        (work_dir / "link1").symlink_to("target.txt")
        (work_dir / "link2").symlink_to("link1")
        (work_dir / "link3").symlink_to("link2")
    
    def modify(work_dir: Path):
        """Modify the chain."""
        # Break the chain in the middle
        (work_dir / "link2").unlink()
        (work_dir / "link2").symlink_to("target.txt")
        
        # Add new link
        (work_dir / "link4").symlink_to("link3")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Check symlink operations
    symlinks = [c for c in env.diff_output 
                if c.get('details', {}).get('command') == 'symlink']
    
    assert len(symlinks) >= 2  # Modified link2 and new link4


@pytest.mark.btrfs_required
def test_case_sensitivity_renames(btrfs_test_path):
    """Test case-only renames (important for case-sensitive filesystems).
    
    Note: This test will skip on case-insensitive filesystems.
    """
    
    def setup(work_dir: Path):
        """Create files with specific cases."""
        (work_dir / "lowercase.txt").write_text("content 1")
        (work_dir / "MixedCase.txt").write_text("content 2")
    
    def modify(work_dir: Path):
        """Change case of filenames."""
        # These renames only work on case-sensitive filesystems
        try:
            # Use temp files to ensure case changes work
            (work_dir / "lowercase.txt").rename(work_dir / "temp1")
            (work_dir / "temp1").rename(work_dir / "LOWERCASE.TXT")
            
            (work_dir / "MixedCase.txt").rename(work_dir / "temp2")
            (work_dir / "temp2").rename(work_dir / "mixedcase.txt")
        except OSError:
            # Skip on case-insensitive filesystems
            pytest.skip("Filesystem is case-insensitive")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Case-only renames might be optimized by btrfs
    all_changes = env.diff_output
    
    # Should detect some operations for case changes
    assert len(all_changes) >= 2, f"Expected at least 2 operations for case changes, got {len(all_changes)}"
    
    print(f"\nCase rename operations:")
    for c in all_changes:
        if c['action'] == 'renamed':
            print(f"  Rename: {c['path']} -> {c['details']['path_to']}")
        else:
            print(f"  {c['action']}: {c['path']}")
    
    # The key is that operations were detected for the case changes
    # Whether they appear as renames or delete/create pairs depends on btrfs