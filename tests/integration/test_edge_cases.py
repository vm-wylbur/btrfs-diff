# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.05.13
# License: (c) HRDAG, 2025, GPL-2 or newer
#
# ------
# tests/integration/test_edge_cases.py
"""Integration tests for edge cases and special scenarios in btrfs-diff."""

import os
import shutil
import stat
import time
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
def test_file_persistence(btrfs_test_path):
    """Test that unchanged files are not reported as changes."""
    
    def setup(work_dir: Path):
        """Create various files that should persist."""
        # Regular files
        (work_dir / "persistent.txt").write_text("unchanged content")
        (work_dir / "binary.bin").write_bytes(b'\x00\x01\x02\x03' * 100)
        
        # Directory structure
        subdir = work_dir / "stable_dir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested unchanged")
        
        # Symlink
        (work_dir / "stable_link").symlink_to("persistent.txt")
        
        # Empty file
        (work_dir / "empty").touch()
    
    def modify(work_dir: Path):
        """Make minimal changes - most files should persist unchanged."""
        # Only modify one file
        (work_dir / "changed.txt").write_text("new file")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Should only detect the one new file
    assert len(env.diff_output) == 1, (
        f"Expected only 1 change (new file), but found {len(env.diff_output)}"
    )
    assert env.diff_output[0]['path'] == "changed.txt"
    assert env.diff_output[0]['action'] == "modified"


@pytest.mark.btrfs_required
def test_sparse_files(btrfs_test_path):
    """Test handling of sparse files with holes."""
    
    def setup(work_dir: Path):
        """Create sparse files."""
        # Create a sparse file
        sparse_path = work_dir / "sparse.dat"
        with open(sparse_path, 'wb') as f:
            f.write(b'start')
            f.seek(1024 * 1024)  # Seek 1MB forward
            f.write(b'end')
        
        # Create another that will be modified
        sparse2_path = work_dir / "sparse2.dat"
        with open(sparse2_path, 'wb') as f:
            f.write(b'begin')
            f.seek(2 * 1024 * 1024)  # Seek 2MB forward
            f.write(b'finish')
    
    def modify(work_dir: Path):
        """Modify sparse files."""
        # Modify the second sparse file
        with open(work_dir / "sparse2.dat", 'r+b') as f:
            f.seek(1024 * 1024)  # Write in the middle of the hole
            f.write(b'middle')
        
        # Create new sparse file
        sparse3_path = work_dir / "sparse3.dat"
        with open(sparse3_path, 'wb') as f:
            f.seek(10 * 1024 * 1024)  # 10MB sparse file
            f.write(b'end')
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    modifications = [c for c in env.diff_output if c['action'] == 'modified']
    
    # Should detect modifications to sparse files
    assert len(modifications) >= 2
    assert any(m['path'] == "sparse2.dat" for m in modifications)
    assert any(m['path'] == "sparse3.dat" for m in modifications)


@pytest.mark.btrfs_required
def test_large_files(btrfs_test_path):
    """Test handling of large files."""
    
    def setup(work_dir: Path):
        """Create large files."""
        # Create a 5MB file
        large_path = work_dir / "large.dat"
        large_path.write_bytes(b'x' * (5 * 1024 * 1024))
        
        # Create one that will be modified
        (work_dir / "modify_large.dat").write_bytes(b'y' * (3 * 1024 * 1024))
    
    def modify(work_dir: Path):
        """Modify large files."""
        # Append to large file
        with open(work_dir / "modify_large.dat", 'ab') as f:
            f.write(b'z' * (2 * 1024 * 1024))  # Add 2MB
        
        # Delete and recreate with different content
        (work_dir / "large.dat").unlink()
        (work_dir / "large.dat").write_bytes(b'a' * (5 * 1024 * 1024))
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Should detect large file modifications
    modifications = [c for c in env.diff_output if c['action'] == 'modified']
    
    assert len(modifications) >= 2
    print(f"Large file operations detected: {len(modifications)}")


@pytest.mark.btrfs_required
def test_special_files(btrfs_test_path):
    """Test handling of special files (FIFOs, device files if supported)."""
    
    def setup(work_dir: Path):
        """Create special files."""
        # Create a FIFO (named pipe)
        fifo_path = work_dir / "myfifo"
        os.mkfifo(fifo_path)
        
        # Note: Device files require special privileges
        # We'll just test FIFOs which are more commonly supported
    
    def modify(work_dir: Path):
        """Modify special files."""
        # Delete the FIFO
        (work_dir / "myfifo").unlink()
        
        # Create a new FIFO
        os.mkfifo(work_dir / "newfifo")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Check if special files are handled
    print(f"Special file changes: {len(env.diff_output)}")
    for c in env.diff_output:
        print(f"  - {c['action']}: {c['path']} ({c['details']['command']})")


@pytest.mark.btrfs_required
def test_extended_attributes(btrfs_test_path):
    """Test detection of extended attribute changes."""
    
    def setup(work_dir: Path):
        """Create files with extended attributes."""
        file_path = work_dir / "xattr_file.txt"
        file_path.write_text("content with xattrs")
        
        # Set extended attributes (if supported)
        try:
            os.setxattr(file_path, "user.comment", b"original comment")
            os.setxattr(file_path, "user.author", b"test suite")
        except (OSError, AttributeError):
            pytest.skip("Extended attributes not supported")
    
    def modify(work_dir: Path):
        """Modify extended attributes."""
        file_path = work_dir / "xattr_file.txt"
        
        # Modify xattr
        os.setxattr(file_path, "user.comment", b"modified comment")
        
        # Add new xattr
        os.setxattr(file_path, "user.version", b"2.0")
        
        # Remove xattr
        os.removexattr(file_path, "user.author")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # btrfs may or may not detect xattr changes as modifications
    print(f"Extended attribute changes detected: {len(env.diff_output)}")


@pytest.mark.btrfs_required
def test_concurrent_modifications(btrfs_test_path):
    """Test multiple modifications to the same file."""
    
    def setup(work_dir: Path):
        """Create initial file."""
        (work_dir / "concurrent.txt").write_text("initial content")
    
    def modify(work_dir: Path):
        """Apply multiple modifications."""
        file_path = work_dir / "concurrent.txt"
        
        # Multiple writes
        file_path.write_text("first modification")
        file_path.write_text("second modification")
        
        # Append
        with open(file_path, 'a') as f:
            f.write("\nappended content")
        
        # Truncate
        with open(file_path, 'r+') as f:
            f.truncate(10)
        
        # Final write
        file_path.write_text("final content")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Should only see the net effect - one modification
    modifications = [c for c in env.diff_output if c['action'] == 'modified']
    assert len(modifications) == 1
    assert modifications[0]['path'] == "concurrent.txt"


@pytest.mark.btrfs_required
def test_path_length_limits(btrfs_test_path):
    """Test handling of very long paths and filenames."""
    
    def setup(work_dir: Path):
        """Create files with long paths."""
        # Create a deep directory structure
        deep_path = work_dir
        for i in range(20):  # 20 levels deep
            deep_path = deep_path / f"level{i:02d}"
        deep_path.mkdir(parents=True)
        
        # Create file with long name (just under typical 255 char limit)
        long_name = "a" * 250 + ".txt"
        (deep_path / long_name).write_text("deep file")
        
        # Create moderately long path that will be renamed
        (work_dir / ("x" * 100 + ".txt")).write_text("long name")
    
    def modify(work_dir: Path):
        """Modify long paths."""
        # Rename the long filename
        old_name = work_dir / ("x" * 100 + ".txt")
        new_name = work_dir / ("y" * 100 + ".txt")
        old_name.rename(new_name)
        
        # Add file to deep directory
        deep_path = work_dir
        for i in range(20):
            deep_path = deep_path / f"level{i:02d}"
        (deep_path / "another.txt").write_text("another deep file")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Verify long paths are handled
    assert len(env.diff_output) >= 2
    print(f"Long path operations: {len(env.diff_output)}")


@pytest.mark.btrfs_required
def test_binary_files(btrfs_test_path):
    """Test modifications to binary files."""
    
    def setup(work_dir: Path):
        """Create binary files."""
        # Create binary file with specific pattern
        binary_data = bytes(range(256)) * 10  # All byte values
        (work_dir / "binary1.bin").write_bytes(binary_data)
        
        # Create another binary file
        (work_dir / "binary2.bin").write_bytes(b'\xff\xfe\xfd' * 1000)
        
        # Create a file with null bytes
        (work_dir / "nulls.bin").write_bytes(b'\x00' * 1000)
    
    def modify(work_dir: Path):
        """Modify binary files."""
        # Modify in the middle
        with open(work_dir / "binary1.bin", 'r+b') as f:
            f.seek(500)
            f.write(b'\xaa\xbb\xcc\xdd' * 10)
        
        # Replace entirely
        (work_dir / "binary2.bin").write_bytes(b'\x11\x22\x33' * 1000)
        
        # Delete nulls file
        (work_dir / "nulls.bin").unlink()
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Should detect binary file changes
    modifications = [c for c in env.diff_output if c['action'] == 'modified']
    deletions = [c for c in env.diff_output if c['action'] == 'deleted']
    
    assert len(modifications) == 2
    assert len(deletions) == 1


@pytest.mark.btrfs_required
def test_circular_symlinks(btrfs_test_path):
    """Test handling of circular symlink references."""
    
    def setup(work_dir: Path):
        """Create circular symlinks."""
        # Create a circular symlink chain
        (work_dir / "link1").symlink_to("link2")
        (work_dir / "link2").symlink_to("link3")
        (work_dir / "link3").symlink_to("link1")
        
        # Create a self-referencing symlink
        (work_dir / "self").symlink_to("self")
    
    def modify(work_dir: Path):
        """Modify circular symlinks."""
        # Break the circle
        (work_dir / "link2").unlink()
        (work_dir / "link2").symlink_to("real_file.txt")
        
        # Create the real file
        (work_dir / "real_file.txt").write_text("breaking the circle")
        
        # Delete self-referencing link
        (work_dir / "self").unlink()
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Should handle circular symlinks without errors
    print(f"Circular symlink changes: {len(env.diff_output)}")
    for c in env.diff_output:
        print(f"  - {c['action']}: {c['path']} ({c['details']['command']})")


@pytest.mark.btrfs_required
def test_delete_recreate_same_name(btrfs_test_path):
    """Test delete and recreate with same name but different inode."""
    
    def setup(work_dir: Path):
        """Create initial files."""
        # File that will be replaced
        (work_dir / "replaced.txt").write_text("original content")
        
        # Directory that will be replaced
        dir_path = work_dir / "replaced_dir"
        dir_path.mkdir()
        (dir_path / "child.txt").write_text("child content")
        
        # Symlink that will be replaced
        (work_dir / "replaced_link").symlink_to("/tmp")
    
    def modify(work_dir: Path):
        """Delete and recreate with same names."""
        # Replace file with different content
        (work_dir / "replaced.txt").unlink()
        (work_dir / "replaced.txt").write_text("completely new content")
        
        # Replace directory with file
        shutil.rmtree(work_dir / "replaced_dir")
        (work_dir / "replaced_dir").write_text("now I'm a file!")
        
        # Replace symlink with directory
        (work_dir / "replaced_link").unlink()
        (work_dir / "replaced_link").mkdir()
        (work_dir / "replaced_link" / "inside.txt").write_text("inside new dir")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # These should show as modifications or delete+create patterns
    print(f"Delete/recreate operations: {len(env.diff_output)}")
    for c in env.diff_output:
        print(f"  - {c['action']}: {c['path']} ({c['details']['command']})")
    
    # Should detect the type changes
    assert any(c['path'] == "replaced_dir" for c in env.diff_output)
    assert any(c['path'] == "replaced_link" for c in env.diff_output)


@pytest.mark.btrfs_required
def test_unicode_edge_cases(btrfs_test_path):
    """Test Unicode edge cases in filenames."""
    
    def setup(work_dir: Path):
        """Create files with various Unicode challenges."""
        # Emoji in filenames
        (work_dir / "😀🎉.txt").write_text("emoji file")
        
        # Right-to-left text
        (work_dir / "مرحبا.txt").write_text("RTL text")
        
        # Zero-width characters
        (work_dir / "normal​file.txt").write_text("has zero-width space")
        
        # Combining characters
        (work_dir / "café.txt").write_text("combining acute")
        
        # Different normalization forms (if filesystem preserves)
        try:
            import unicodedata
            # NFC form
            nfc_name = unicodedata.normalize('NFC', 'café.txt')
            # NFD form  
            nfd_name = unicodedata.normalize('NFD', 'café.txt')
            if nfc_name != nfd_name:
                (work_dir / nfd_name).write_text("decomposed form")
        except:
            pass
    
    def modify(work_dir: Path):
        """Modify Unicode files."""
        # Rename emoji file
        if (work_dir / "😀🎉.txt").exists():
            (work_dir / "😀🎉.txt").rename(work_dir / "🎊🎈.txt")
        
        # Delete RTL file
        if (work_dir / "مرحبا.txt").exists():
            (work_dir / "مرحبا.txt").unlink()
        
        # Create new Unicode file
        (work_dir / "中文文件名.txt").write_text("Chinese filename")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Verify Unicode handling
    print(f"Unicode operations: {len(env.diff_output)}")
    assert len(env.diff_output) >= 2  # At least some operations detected


@pytest.mark.btrfs_required
def test_timestamp_only_changes(btrfs_test_path):
    """Test if timestamp-only changes are detected."""
    
    def setup(work_dir: Path):
        """Create files with specific timestamps."""
        file_path = work_dir / "timestamp_test.txt"
        file_path.write_text("content")
        
        # Set specific timestamp
        past_time = time.time() - 86400  # 1 day ago
        os.utime(file_path, (past_time, past_time))
    
    def modify(work_dir: Path):
        """Only change timestamps."""
        file_path = work_dir / "timestamp_test.txt"
        
        # Touch file to update timestamp without changing content
        file_path.touch()
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # btrfs-diff might not detect timestamp-only changes
    print(f"Timestamp-only changes detected: {len(env.diff_output)}")
    if len(env.diff_output) > 0:
        print("  Timestamp changes ARE detected")
    else:
        print("  Timestamp changes are NOT detected")


@pytest.mark.btrfs_required
def test_hardlink_edge_cases(btrfs_test_path):
    """Test edge cases with hard links."""
    
    def setup(work_dir: Path):
        """Create hard link scenarios."""
        # Create file with multiple hard links
        original = work_dir / "original.txt"
        original.write_text("shared content")
        
        os.link(original, work_dir / "link1.txt")
        os.link(original, work_dir / "link2.txt")
        os.link(original, work_dir / "link3.txt")
    
    def modify(work_dir: Path):
        """Modify hard links."""
        # Delete one link (others should remain)
        (work_dir / "link1.txt").unlink()
        
        # Modify content (affects all links)
        (work_dir / "original.txt").write_text("modified shared content")
        
        # Delete original (other links should still exist)
        (work_dir / "original.txt").unlink()
        
        # Create new hard link to remaining file
        os.link(work_dir / "link2.txt", work_dir / "link4.txt")
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True,
    )
    
    # Analyze hard link behavior
    print(f"Hard link operations: {len(env.diff_output)}")
    for c in env.diff_output:
        print(f"  - {c['action']}: {c['path']} ({c['details']['command']})")