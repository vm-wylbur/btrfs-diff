# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-01-11

### Added
- **Typed API**: `parser.get_changes()` now returns `list[FileChange]` with full type safety
- Type exports: `FileChange`, `ChangeDetails`, `ActionType` for better IDE support
- Migration guide in README for upgrading from v0.1.x
- Five new production tests for complex filesystem scenarios (converted from aspirational tests)

### Changed
- **BREAKING**: `parser.get_changes()` now returns typed objects instead of dictionaries
- Dict-based API moved to `parser.get_changes_dict()` for backward compatibility
- Updated all README examples to demonstrate the new typed API
- Improved test coverage for circular renames, file swaps, and directory restructuring

### Fixed
- None

### Deprecated
- Dict-based API (`get_changes_dict()`) will be deprecated in v0.3.0

## [0.1.2] - 2025-01-11

### Added
- Internal architecture refactored to use typed dataclasses
- Comprehensive testing strategy established

### Changed
- Parser internals now use typed objects (FileChange, ChangeDetails)
- Improved code organization and type safety

## [0.1.1] - 2025-01-10

### Added
- Reliable directory detection with `is_directory` field
- Improved handling of directory vs file operations

### Fixed
- Directory detection bug that affected backup tools

## [0.1.0] - 2025-01-09

### Added
- Initial release
- Fast parsing of btrfs send streams
- Comprehensive change detection (modifications, deletions, renames, symlinks)
- Validation framework to verify parser accuracy
- CLI tools for interactive analysis
- Python API for integration

[0.2.0]: https://github.com/your-org/btrfs-diff/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/your-org/btrfs-diff/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/your-org/btrfs-diff/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/your-org/btrfs-diff/releases/tag/v0.1.0