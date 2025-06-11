# btrfs-diff v0.2.0 Release Notes

We're excited to announce the release of btrfs-diff v0.2.0! This release marks a significant milestone in the project's evolution, introducing a fully typed Python API while maintaining complete backward compatibility.

## 🎯 Highlights

### Typed API is Here!

The most significant change in v0.2.0 is the introduction of a typed API. The `get_changes()` method now returns typed `FileChange` objects instead of dictionaries, providing:

- **Type Safety**: Catch errors at development time with IDE support
- **Better Autocomplete**: Your IDE now knows exactly what attributes are available
- **Clearer Code**: No more guessing what's in those dictionaries
- **Future-Proof**: Aligns with modern Python best practices

```python
# New typed API (v0.2.0)
from btrfs_diff import BtrfsParser

parser = BtrfsParser(old_snapshot, new_snapshot)
changes = parser.get_changes()  # Returns list[FileChange]

for change in changes:
    print(f"{change.action}: {change.path}")  # IDE knows these attributes!
    if change.details.is_directory:
        print("  It's a directory!")
```

### Complete Backward Compatibility

We understand that breaking changes can be disruptive. That's why v0.2.0 maintains full backward compatibility:

```python
# Still works exactly as before
changes = parser.get_changes_dict()  # Returns list[dict]
```

This gives you time to migrate at your own pace. See our [Migration Guide](README.md#migration-guide) for details.

### Enhanced Test Coverage

We've converted 5 "aspirational" tests into production tests, ensuring btrfs-diff correctly handles complex real-world scenarios:

- **Circular rename chains** (A→B→C→A)
- **File swapping** operations
- **Bulk directory moves**
- **Deep directory restructuring**
- **Case-sensitivity filename changes

These tests verify that btrfs-diff handles even the most complex filesystem operations that btrfs send optimizes.

## 📋 What's Changed

### Breaking Changes (with compatibility layer)
- `parser.get_changes()` now returns `list[FileChange]` instead of `list[dict]`
- The dict-based API moved to `parser.get_changes_dict()`

### New Features
- Full type annotations with `FileChange`, `ChangeDetails`, and `ActionType` classes
- Comprehensive migration guide in README
- CHANGELOG.md for tracking all releases

### Improvements
- Updated all documentation examples to show typed API
- Better IDE integration and developer experience
- More robust handling of complex filesystem operations

## 🚀 Migration

Migrating to the typed API is straightforward:

**Before (v0.1.x):**
```python
if change['action'] == 'modified':
    print(change['details']['path'])
```

**After (v0.2.0):**
```python
if change.action == 'modified':
    print(change.details.path)
```

Or keep using dicts with `get_changes_dict()` until you're ready to migrate.

## 🔮 Looking Forward

- **v0.3.0**: Dict API will be deprecated with warnings
- **v0.4.0**: Dict API may be removed entirely

We recommend migrating to the typed API when convenient to take advantage of better tooling support and cleaner code.

## 🙏 Acknowledgments

This release represents significant improvements to the internal architecture while maintaining the stability and reliability you depend on. Special thanks to all users who have provided feedback and use cases that shaped these improvements.

## 📦 Installation

```bash
pip install --upgrade btrfs-diff
```

Or from source:
```bash
git clone https://github.com/your-org/btrfs-diff
cd btrfs-diff
pip install .
```

## 📚 Documentation

- [README](README.md) - Updated with typed API examples
- [Migration Guide](README.md#migration-guide) - Step-by-step upgrade instructions
- [CHANGELOG](CHANGELOG.md) - Detailed version history

---

Co-authored-by: PB and Claude