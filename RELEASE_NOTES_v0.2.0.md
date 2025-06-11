# btrfs-diff v0.2.0

## Summary

Version 0.2.0 introduces a typed Python API while maintaining backward compatibility. The primary change is that `get_changes()` now returns typed `FileChange` objects instead of dictionaries.

## Breaking Changes

- `parser.get_changes()` returns `list[FileChange]` instead of `list[dict]`
- Dict-based API moved to `parser.get_changes_dict()` for compatibility

## New Features

- Typed API with `FileChange`, `ChangeDetails`, and `ActionType` classes
- Full type annotations for better IDE support
- Migration guide in README
- CHANGELOG.md for release tracking

## Migration

```python
# Old (v0.1.x)
changes = parser.get_changes()
if change['action'] == 'modified':
    print(change['details']['path'])

# New (v0.2.0) - Typed API
changes = parser.get_changes()
if change.action == 'modified':
    print(change.details.path)

# Backward compatible
changes = parser.get_changes_dict()  # Still returns dicts
```

## Test Coverage

Added production tests for complex filesystem operations:
- Circular rename chains
- File swapping
- Directory content moves
- Deep directory restructuring
- Case-only filename changes

## Installation

```bash
pip install --upgrade btrfs-diff
```

## Documentation

- [README](README.md) - Updated examples and migration guide
- [CHANGELOG](CHANGELOG.md) - Complete version history

## Deprecation Timeline

- v0.3.0: Dict API deprecated with warnings
- v0.4.0: Dict API removal (tentative)

---

Co-authored-by: PB and Claude