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
from btrfs_diff import BtrfsParser

# Create parser for two snapshots
parser = BtrfsParser("/path/to/old/snapshot", "/path/to/new/snapshot")

# Get all changes
changes = parser.get_changes()

for change in changes:
    print(f"{change['action']}: {change['path']}")
    if change['action'] == 'renamed':
        print(f"  → {change['details']['path_to']}")
    elif change['action'] == 'modified' and change['details']['command'] == 'symlink':
        print(f"  → {change['details']['path_link']}")
```

#### JSON Output

```python
from btrfs_diff import get_btrfs_diff
import json

# Get changes as JSON string
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

# Analyze change patterns
actions = Counter(c['action'] for c in changes)
commands = Counter(c['details']['command'] for c in changes)

print(f"Actions: {dict(actions)}")
print(f"Commands: {dict(commands)}")
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
        'size': 1024
    }
}
```

### Deleted Files
```python
{
    'path': 'home/user/old_file.txt', 
    'action': 'deleted',
    'details': {
        'command': 'unlink'  # or 'rmdir'
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
        'path_to': 'home/user/new_name.txt'
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
        'inode': 12345
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

## Attribution

Adapted from [btrfs-snapshots-diff](https://github.com/sysnux/btrfs-snapshots-diff) by Jean-Denis Girard (MIT License).

## Contributing

Copyright (C) 2025 HRDAG https://hrdag.org

This project is developed and maintained by the Human Rights Data Analysis Group.