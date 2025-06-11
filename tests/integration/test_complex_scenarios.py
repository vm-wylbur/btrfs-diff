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
@pytest.mark.aspirational
def test_rename_chain(btrfs_test_path):
    """Test detection of chained renames (A->B, B->C, C->D)."""
    
    def setup(work_dir: Path):
        """Create initial files."""
        (work_dir / "file_a.txt").write_text("content A")
        (work_dir / "file_b.txt").write_text("content B")
        (work_dir / "file_c.txt").write_text("content C")
    
    def modify(work_dir: Path):
        """Create rename chain."""
        # Create a circular rename scenario
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
    
    renames = [c for c in env.diff_output if c['action'] == 'renamed']
    
    # Should detect all renames in the chain
    assert len(renames) >= 3
    print(f"Rename chain detected:")
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
@pytest.mark.aspirational
def test_swap_files(btrfs_test_path):
    """Test swapping contents/names of two files."""
    
    def setup(work_dir: Path):
        """Create two files."""
        (work_dir / "file1.txt").write_text("Content of file 1")
        (work_dir / "file2.txt").write_text("Content of file 2")
    
    def modify(work_dir: Path):
        """Swap files using temp name."""
        (work_dir / "file1.txt").rename(work_dir / "temp")
        (work_dir / "file2.txt").rename(work_dir / "file1.txt")
        (work_dir / "temp").rename(work_dir / "file2.txt")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    renames = [c for c in env.diff_output if c['action'] == 'renamed']
    
    # Should detect the swap operation
    assert len(renames) == 2
    assert any(r['path'] == "file1.txt" and r['details']['path_to'] == "file2.txt" 
               for r in renames)
    assert any(r['path'] == "file2.txt" and r['details']['path_to'] == "file1.txt" 
               for r in renames)


@pytest.mark.btrfs_required
@pytest.mark.aspirational
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
    
    renames = [c for c in env.diff_output if c['action'] == 'renamed']
    
    assert len(renames) == 2
    assert all(r['path'].startswith("dir1/") and 
               r['details']['path_to'].startswith("dir2/") for r in renames)


@pytest.mark.btrfs_required
@pytest.mark.aspirational
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
    
    # Should see file moves and directory deletions
    assert len(renames) == 3
    assert len(deletions) == 3  # Three empty directories


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
@pytest.mark.aspirational
def test_case_sensitivity_renames(btrfs_test_path):
    """Test case-only renames (important for case-sensitive filesystems)."""
    
    def setup(work_dir: Path):
        """Create files with specific cases."""
        (work_dir / "lowercase.txt").write_text("content")
        (work_dir / "UPPERCASE.TXT").write_text("content")
        (work_dir / "CamelCase.txt").write_text("content")
    
    def modify(work_dir: Path):
        """Change case of filenames."""
        # These renames only work on case-sensitive filesystems
        try:
            (work_dir / "lowercase.txt").rename(work_dir / "LOWERCASE.TXT")
            (work_dir / "UPPERCASE.TXT").rename(work_dir / "uppercase.txt")
            (work_dir / "CamelCase.txt").rename(work_dir / "camelcase.txt")
        except OSError:
            # Skip on case-insensitive filesystems
            pytest.skip("Filesystem is case-insensitive")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    renames = [c for c in env.diff_output if c['action'] == 'renamed']
    
    # Should detect case-only renames
    assert len(renames) == 3