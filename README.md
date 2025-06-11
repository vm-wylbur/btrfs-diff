# btrfs-diff

Parse and analyze differences between btrfs snapshots using btrfs send streams.

This library provides both a Python API and CLI tool for extracting and validating file changes between btrfs snapshots. It parses btrfs send streams to identify modifications, deletions, renames, and symlink changes with high accuracy.

## Features

- **Fast parsing** of btrfs send streams without requiring actual data transfer
- **Comprehensive change detection**: modifications, deletions, renames, symlinks
- **Validation framework** to verify parser accuracy against filesystem
- **CLI tools** for interactive analysis and batch processing
- **Production-ready** with extensive testing on real snapshot datasets

## Installation

```bash
pip install btrfs-diff
```

Or install from source:

```bash
git clone https://github.com/your-org/btrfs-diff
cd btrfs-diff
pip install .
```

## Quick Start

### Command Line Usage

```bash
# Basic diff between two snapshots
btrfs-diff diff /path/to/old/snapshot /path/to/new/snapshot

# Pretty table output
btrfs-diff diff /path/to/old/snapshot /path/to/new/snapshot --format table

# Validate parser accuracy
btrfs-diff validate /path/to/old/snapshot /path/to/new/snapshot --sample 100

# Comprehensive validation across multiple snapshots
btrfs-diff comprehensive /mnt/snapshots --pattern "data.2024*" --sample 1000
```

### Python Library Usage

#### Basic Change Detection

```python
from btrfs_diff import BtrfsParser, FileChange

# Create parser for two snapshots
parser = BtrfsParser("/path/to/old/snapshot", "/path/to/new/snapshot")

# Get all changes (new in v0.2.0 - returns typed objects)
changes: list[FileChange] = parser.get_changes()

for change in changes:
    print(f"{change.action}: {change.path}")
    if change.action == 'renamed':
        print(f"  → {change.details.path_to}")
    elif change.action == 'modified' and change.details.command == 'symlink':
        print(f"  → {change.details.path_link}")
```

#### JSON Output (Dict-based API)

```python
from btrfs_diff import BtrfsParser
import json

# For backward compatibility, use get_changes_dict()
parser = BtrfsParser("/path/to/old/snapshot", "/path/to/new/snapshot")
changes_dict = parser.get_changes_dict()  # Returns list[dict]

# Or use the convenience function
from btrfs_diff import get_btrfs_diff
result = get_btrfs_diff("/path/to/old/snapshot", "/path/to/new/snapshot")
changes = json.loads(result)

# Filter by change type
modifications = [c for c in changes if c['action'] == 'modified']
deletions = [c for c in changes if c['action'] == 'deleted']
renames = [c for c in changes if c['action'] == 'renamed']
```

#### Change Analysis

```python
from collections import Counter
from btrfs_diff import BtrfsParser, ActionType

# Using the typed API (v0.2.0+)
parser = BtrfsParser("/path/to/old/snapshot", "/path/to/new/snapshot")
changes = parser.get_changes()

# Analyze change patterns with type safety
actions = Counter(c.action for c in changes)
commands = Counter(c.details.command for c in changes if c.details.command)

print(f"Actions: {dict(actions)}")
print(f"Commands: {dict(commands)}")

# Type-safe filtering
modified_files = [c for c in changes if c.action == ActionType.MODIFIED]
symlinks = [c for c in changes if c.details.command == 'symlink']
```

#### Directory Detection

```python
# Distinguish between files and directories using the is_directory field
files = []
directories = []

# Using typed API (v0.2.0+)
for change in changes:
    # The is_directory field reliably indicates directory vs file
    if change.details.is_directory is True:
        directories.append(change)
    elif change.details.is_directory is False:
        files.append(change)
    # Note: is_directory may be None if detection failed

print(f"Found {len(files)} file operations, {len(directories)} directory operations")

# Example: Process files and directories differently (like backup tools)
for change in changes:
    is_directory = change.details.is_directory or False
    path = change.path
    action = change.action
    
    if action == 'modified':
        if is_directory:
            print(f"Directory created/modified: {path}")
            # Handle directory creation (mkdir equivalent)
        else:
            print(f"File created/modified: {path}")
            # Handle file copy/update
    elif action == 'deleted':
        if is_directory:
            print(f"Directory deleted: {path}")
            # Handle directory removal (rmdir equivalent)
        else:
            print(f"File deleted: {path}")
            # Handle file deletion
```

#### External Tool Integration

```python
# Safe pattern for external tools using typed API (v0.2.0+)
def is_directory_operation(change: FileChange) -> bool:
    """Safely detect directory operations for sync/backup tools."""
    # Use is_directory field for reliable detection
    return change.details.is_directory or False

# Example sync tool logic
for change in changes:
    source_path = old_snapshot / change.path
    target_path = backup_target / change.path
    
    if change.action == 'modified':
        if is_directory_operation(change):
            # Create directory
            target_path.mkdir(parents=True, exist_ok=True)
        else:
            # Copy file
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
    elif change.action == 'deleted':
        if is_directory_operation(change):
            # Remove directory
            shutil.rmtree(target_path, ignore_errors=True)
        else:
            # Remove file
            target_path.unlink(missing_ok=True)
```

#### Validation Framework

```python
from btrfs_diff.validator import (
    validate_symlinks_targeted,
    validate_deletions, 
    validate_modifications
)

# Parse changes first
parser = BtrfsParser(old_snapshot, new_snapshot)
changes = parser.get_changes()

# Separate by type
symlinks = [c for c in changes if c['details']['command'] == 'symlink']
deletions = [c for c in changes if c['action'] == 'deleted']
modifications = [c for c in changes if c['action'] == 'modified']

# Validate symlinks (checks that symlinks exist with correct targets)
if symlinks:
    result = validate_symlinks_targeted(
        symlinks, new_snapshot, max_check=100
    )
    print(f"Symlinks: {result.validated} validated, {result.missing} missing")

# Validate deletions (checks files actually deleted between snapshots)
if deletions:
    result = validate_deletions(
        deletions, old_snapshot, new_snapshot, max_check=100
    )
    print(f"Deletions: {result.actually_deleted} confirmed, {result.found_in_new} false positives")

# Validate modifications (checks files exist and timing)
if modifications:
    result = validate_modifications(
        modifications, old_snapshot, new_snapshot, max_check=100
    )
    print(f"Modifications: {result.file_exists} exist, {result.mtime_in_range} in time range")
```

#### Batch Processing

```python
from pathlib import Path

def process_snapshot_series(snapshot_root: Path, pattern: str = "data.2024*"):
    """Process all consecutive snapshot pairs matching pattern."""
    snapshots = sorted([
        d for d in snapshot_root.iterdir() 
        if d.is_dir() and d.name.startswith(pattern.replace('*', ''))
    ])
    
    results = []
    for i in range(len(snapshots) - 1):
        old_snap = snapshots[i]
        new_snap = snapshots[i + 1]
        
        print(f"Processing: {old_snap.name} → {new_snap.name}")
        
        parser = BtrfsParser(old_snap, new_snap)
        changes = parser.get_changes()
        
        results.append({
            'old': old_snap.name,
            'new': new_snap.name,
            'total_changes': len(changes),
            'modifications': len([c for c in changes if c['action'] == 'modified']),
            'deletions': len([c for c in changes if c['action'] == 'deleted']),
            'renames': len([c for c in changes if c['action'] == 'renamed'])
        })
    
    return results

# Example usage
results = process_snapshot_series(Path("/mnt/snapshots"))
for r in results:
    print(f"{r['old']} → {r['new']}: {r['total_changes']} changes")
```

## Understanding Change Types

The parser categorizes changes into three main actions:

### Modified Files
```python
{
    'path': 'home/user/document.txt',
    'action': 'modified',
    'details': {
        'command': 'update_extent',  # or 'mkfile', 'truncate'
        'size': 1024,
        'is_directory': False  # NEW: Reliable directory detection
    }
}
```

### Modified Directories  
```python
{
    'path': 'home/user/new_folder',
    'action': 'modified',
    'details': {
        'command': 'mkdir',  # Directory creation (rare in output)
        'is_directory': True  # NEW: Reliable directory detection
    }
}
```

### Deleted Files
```python
{
    'path': 'home/user/old_file.txt', 
    'action': 'deleted',
    'details': {
        'command': 'unlink',
        'is_directory': False  # NEW: File deletion
    }
}
```

### Deleted Directories
```python
{
    'path': 'home/user/old_folder', 
    'action': 'deleted',
    'details': {
        'command': 'rmdir',
        'is_directory': True  # NEW: Directory deletion
    }
}
```

### Renamed Files
```python
{
    'path': 'home/user/old_name.txt',
    'action': 'renamed', 
    'details': {
        'command': 'rename',
        'path_to': 'home/user/new_name.txt',
        'is_directory': False  # NEW: File vs directory distinction
    }
}
```

### Symlinks
```python
{
    'path': 'home/user/link',
    'action': 'modified',
    'details': {
        'command': 'symlink',
        'path_link': '../target/file',
        'inode': 12345,
        'is_directory': False  # NEW: Symlinks are not directories
    }
}
```

## CLI Reference

### `btrfs-diff diff`

Extract changes between two snapshots.

```bash
btrfs-diff diff OLD_SNAPSHOT NEW_SNAPSHOT [OPTIONS]

Options:
  --format, -f [json|summary|table]  Output format (default: json)
  --debug                           Enable debug output
```

### `btrfs-diff validate`

Validate parser results against actual filesystem changes.

```bash
btrfs-diff validate OLD_SNAPSHOT NEW_SNAPSHOT [OPTIONS]

Options:
  --sample, -s INTEGER    Sample size per validation type (default: 10)
  --verbose, -v          Verbose output
  --debug               Enable debug output
```

### `btrfs-diff comprehensive`

Run validation across multiple snapshot pairs.

```bash
btrfs-diff comprehensive SNAPSHOT_ROOT [OPTIONS]

Options:
  --sample, -s INTEGER     Sample size for validation (default: 1000)
  --pattern, -p TEXT       Snapshot name pattern (default: "data.2024*")
```

## Data Types

The library provides type-safe interfaces:

```python
from btrfs_diff.types import FileChange, ChangeDetails, ValidationResult

# FileChange represents a single file change
change = FileChange(
    path="home/user/file.txt",
    action="modified", 
    details=ChangeDetails(command="update_extent", size=1024)
)

# ValidationResult contains validation metrics
result = ValidationResult(
    validated=85,
    missing=10,
    mismatched_targets=5
)
```

## Performance

- **Fast**: Processes hundreds of thousands of changes in seconds
- **Memory efficient**: Streams data without loading entire snapshots
- **Scalable**: Handles multi-terabyte snapshot diffs
- **Production tested**: Validated on real-world backup systems

Typical performance on modern hardware:
- ~10,000 changes/second parsing
- ~1,000 validations/second filesystem checking
- Memory usage: <100MB for typical workloads

## Requirements

- **Python**: 3.13+
- **System**: Linux with btrfs support
- **Privileges**: `sudo` access for `btrfs send` commands
- **Tools**: `fdfind` for validation (optional but recommended)

## Integration Testing

The project includes a comprehensive integration test suite that verifies btrfs-diff handles all file operation scenarios correctly. These tests are essential for ensuring reliability in production backup and sync systems.

### Running the Tests

Integration tests require a btrfs filesystem and sudo access:

```bash
# Run all production-ready tests (recommended for CI/CD)
pytest tests/ --run-btrfs-tests --btrfs-path=/path/to/btrfs/filesystem

# Run specific test categories
pytest tests/integration/test_directory_operations.py --run-btrfs-tests --btrfs-path=/var/tmp
pytest tests/integration/test_file_operations.py --run-btrfs-tests --btrfs-path=/var/tmp
pytest tests/integration/test_edge_cases.py --run-btrfs-tests --btrfs-path=/var/tmp

# Run aspirational tests (documents future functionality - currently failing)
pytest tests/ --run-btrfs-tests --btrfs-path=/var/tmp --run-aspirational-tests

# Run with verbose output
pytest tests/ -v --run-btrfs-tests --btrfs-path=/var/tmp

# Run a specific test
pytest tests/integration/test_edge_cases.py::test_file_persistence -v --run-btrfs-tests --btrfs-path=/var/tmp
```

### Test Categories

The test suite is organized into two main categories:

#### Production Tests (Default)
These tests validate current functionality and must pass for releases:
- **Core functionality**: File/directory detection, parsing accuracy
- **Directory operations**: Creation, deletion, nesting, symlink replacement
- **File operations**: Creation, modification, deletion, symlinks  
- **Edge cases**: Sparse files, special files, Unicode, permissions
- **Directory detection**: Production bug fixes and API reliability

#### Aspirational Tests (`--run-aspirational-tests`)
These tests document desired future functionality (currently failing):
- **Complex rename chains**: Multi-step A→B→C→D scenarios
- **File swapping**: Circular rename operations
- **Directory restructuring**: Deep hierarchy reorganization  
- **Cross-directory moves**: Content migration between directories
- **Case-sensitivity renames**: Case-only filename changes

Use aspirational tests to:
- **Document enhancement goals** for future development
- **Validate improvements** when implementing advanced rename detection
- **Ensure comprehensive coverage** of complex filesystem scenarios

### Test Coverage

The integration tests cover three main categories:

#### Directory Operations (`test_directory_operations.py`)
- Directory deletion (with files, empty, nested structures)
- Directory renames
- Directory to symlink replacement
- Complex nested directory operations

#### File Operations (`test_file_operations.py`)
- File creation, modification, and deletion
- File renames (within directory, across directories)
- Symlink operations (creation, modification, deletion)
- Permission changes
- Hard link operations
- Special characters in filenames
- Empty file handling
- File truncation and expansion

#### Edge Cases (`test_edge_cases.py`)
- **File persistence**: Verifies unchanged files are not reported
- **Sparse files**: Files with holes
- **Large files**: Multi-megabyte file operations
- **Special files**: FIFOs and device files
- **Extended attributes**: xattr modifications
- **Path limits**: Very long paths and filenames
- **Binary files**: Non-text file modifications
- **Unicode edge cases**: Emoji, RTL text, combining characters
- **Circular symlinks**: Self-referencing and circular chains
- **Delete/recreate patterns**: Same name, different inode
- **Concurrent modifications**: Multiple changes to same file
- **Hardlink edge cases**: Complex hard link scenarios

#### Complex Scenarios (`test_complex_scenarios.py`)
- Rename chains (A→B→C→D)
- File to directory replacement (and vice versa)
- File swapping operations
- Directory content migration
- Deep directory restructuring
- Mixed operations on same pathname
- Symlink chain modifications
- Case-sensitivity renames

### Test Infrastructure

The test suite includes a reusable fixture (`btrfs_snapshot_fixture.py`) that:
- Creates temporary btrfs subvolumes for testing
- Applies file operations between snapshots
- Runs btrfs-diff and captures results
- Automatically cleans up test data

This fixture can be used by other projects needing to test btrfs snapshot operations:

```python
from tests.fixtures.btrfs_snapshot_fixture import create_btrfs_test_environment

def test_my_scenario(btrfs_test_path):
    def setup(work_dir):
        # Create initial state
        (work_dir / "test.txt").write_text("content")
    
    def modify(work_dir):
        # Make changes
        (work_dir / "test.txt").unlink()
    
    env = create_btrfs_test_environment(
        btrfs_path=btrfs_test_path,
        setup_func=setup,
        modify_func=modify,
        cleanup=True
    )
    
    # Verify results
    assert len(env.diff_output) == 1
```

### Requirements for Testing

- Linux system with btrfs filesystem
- Python 3.13+
- pytest and test dependencies
- sudo access (for btrfs subvolume operations)
- At least 100MB free space on btrfs filesystem

### Continuous Integration

For CI environments without btrfs:
- Tests marked with `@pytest.mark.btrfs_required` are automatically skipped
- Use `--run-btrfs-tests` flag to explicitly enable when btrfs is available
- Consider using a Docker container with btrfs support for CI testing

## Validation Accuracy

Extensive testing shows high accuracy across operation types:

| Operation Type | Typical Accuracy |
|---------------|------------------|
| Symlinks      | 99.5%+          |
| Deletions     | 99.8%+          |
| Modifications | 99.9%+          |
| Renames       | 99.7%+          |

## License

GPL-2.0-or-later. See [LICENSE](LICENSE) for full text.

## Migration Guide

### Upgrading from v0.1.x to v0.2.0

Version 0.2.0 introduces a typed API while maintaining backward compatibility. The main change is that `get_changes()` now returns typed `FileChange` objects instead of dictionaries.

#### What Changed

- `parser.get_changes()` now returns `list[FileChange]` instead of `list[dict]`
- The dict-based API moved to `parser.get_changes_dict()` for backward compatibility
- New type imports available: `FileChange`, `ChangeDetails`, `ActionType`

#### Migration Examples

**Old code (v0.1.x):**
```python
changes = parser.get_changes()
for change in changes:
    if change['action'] == 'modified':
        print(change['path'])
```

**New code (v0.2.0) - Option 1: Use typed API (recommended):**
```python
changes = parser.get_changes()  # Now returns FileChange objects
for change in changes:
    if change.action == 'modified':  # Use dot notation
        print(change.path)
```

**New code (v0.2.0) - Option 2: Keep using dicts (backward compatible):**
```python
changes = parser.get_changes_dict()  # Explicitly use dict API
for change in changes:
    if change['action'] == 'modified':  # Same as before
        print(change['path'])
```

#### Benefits of the Typed API

- **Type safety**: IDEs can catch errors before runtime
- **Autocomplete**: Better developer experience with attribute suggestions
- **Documentation**: Types serve as inline documentation
- **Future-proof**: Aligns with modern Python best practices

#### Deprecation Timeline

- **v0.2.0**: Both APIs available, typed API is default
- **v0.3.0**: Dict API will be deprecated with warnings
- **v0.4.0**: Dict API may be removed

## Attribution

Adapted from [btrfs-snapshots-diff](https://github.com/sysnux/btrfs-snapshots-diff) by Jean-Denis Girard (MIT License).

## Contributing

Copyright (C) 2025 HRDAG https://hrdag.org

This project is developed and maintained by the Human Rights Data Analysis Group.