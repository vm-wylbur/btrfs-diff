# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.06.09
# License: (c) HRDAG, 2025, GPL-2 or newer
#
# ------
# btrfs-diff/src/btrfs_diff/validator.py

"""Validation framework for btrfs snapshot diff results."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .types import ValidationResult


def timestamp() -> str:
    """Get current timestamp for logging."""
    return datetime.now().strftime("%H:%M:%S")


def get_fd_changes(start_time: datetime, end_time: datetime, root_path: Path) -> dict:
    """Get file changes using fd within the time window."""
    # Convert to UTC for consistency
    start_utc = start_time.astimezone(timezone.utc)
    end_utc = end_time.astimezone(timezone.utc)
    
    start_str = start_utc.strftime('%Y-%m-%d %H:%M:%S')
    end_str = end_utc.strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        # Find files changed within the window
        cmd = [
            'fdfind', '.',
            '--type', 'file', '--type', 'symlink',
            '--changed-within', start_str,
            '--changed-before', end_str,
            '--absolute-path',
            '--no-ignore',  # Don't skip .git etc
            str(root_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, check=True)
        
        # Handle non-UTF-8 filenames
        stdout_text = result.stdout.decode('utf-8', errors='replace')
        changed_files = [line.strip() for line in stdout_text.strip().split('\n') if line.strip()]
        
        # Filter out .snapshots directory
        filtered_files = [f for f in changed_files if '/.snapshots/' not in f and not f.endswith('/.snapshots')]
        
        # Separate into files and symlinks
        files = []
        symlinks = []
        
        for file_path in filtered_files:
            try:
                p = Path(file_path)
                if p.exists():
                    if p.is_symlink():
                        target = p.readlink() if p.is_symlink() else None
                        symlinks.append({
                            'path': str(p),
                            'target': str(target) if target else None,
                            'relative_path': str(p.relative_to(root_path)) if p.is_relative_to(root_path) else str(p)
                        })
                    else:
                        files.append({
                            'path': str(p),
                            'relative_path': str(p.relative_to(root_path)) if p.is_relative_to(root_path) else str(p)
                        })
            except (OSError, UnicodeError, ValueError):
                # Skip files with problematic names/paths
                continue
        
        return {
            'files': files,
            'symlinks': symlinks,
            'total': len(filtered_files)
        }
    
    except subprocess.CalledProcessError:
        return {'files': [], 'symlinks': [], 'total': 0}


def parse_snapshot_time(snapshot_name: str) -> datetime:
    """Parse timestamp from snapshot name like 'home.20250605T000001-0700' or 'data.20240101T000001+0000'."""
    # Extract the timestamp part
    time_part = snapshot_name.split('.')[1] if '.' in snapshot_name else snapshot_name
    
    # Parse timezone offset
    if '+' in time_part:
        dt_str, tz_str = time_part.rsplit('+', 1)
        tz = timezone.utc  # Assume UTC for + offsets
    elif '-' in time_part:
        dt_str, tz_str = time_part.rsplit('-', 1)
        # For -0700/-0800, convert to timezone offset
        if tz_str in ['0700', '0800']:
            from datetime import timedelta
            hours = int(tz_str[:2])
            minutes = int(tz_str[2:])
            tz = timezone(timedelta(hours=-hours, minutes=-minutes))
        else:
            tz = timezone.utc  # Fallback
    else:
        dt_str = time_part
        tz = timezone.utc
    
    # Parse the datetime part and apply timezone
    naive_dt = datetime.strptime(dt_str, '%Y%m%dT%H%M%S')
    return naive_dt.replace(tzinfo=tz)


def get_snapshot_contents(snapshot_path: Path) -> dict:
    """Get all symlinks and files from a snapshot directory using fdfind."""
    try:
        # Find all files and symlinks in the snapshot
        cmd = [
            'fdfind', '.',
            '--type', 'file', '--type', 'symlink',
            '--absolute-path',
            '--no-ignore',
            str(snapshot_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, check=True)
        
        # Handle non-UTF-8 filenames
        stdout_text = result.stdout.decode('utf-8', errors='replace')
        all_files = [line.strip() for line in stdout_text.strip().split('\n') if line.strip()]
        
        # Filter out .snapshots directory 
        filtered_files = [f for f in all_files if '/.snapshots/' not in f and not f.endswith('/.snapshots')]
        
        # Separate into files and symlinks
        files = []
        symlinks = []
        
        for file_path in filtered_files:
            try:
                p = Path(file_path)
                if p.exists():
                    # Convert to relative path from snapshot root
                    rel_path = p.relative_to(snapshot_path)
                    if p.is_symlink():
                        target = p.readlink() if p.is_symlink() else None
                        symlinks.append({
                            'path': str(p),
                            'target': str(target) if target else None,
                            'relative_path': str(rel_path)
                        })
                    else:
                        files.append({
                            'path': str(p),
                            'relative_path': str(rel_path)
                        })
            except (OSError, UnicodeError, ValueError) as e:
                # Skip files with problematic names/paths
                continue
        
        return {
            'files': files,
            'symlinks': symlinks,
            'total': len(filtered_files)
        }
    
    except subprocess.CalledProcessError as e:
        return {'files': [], 'symlinks': [], 'total': 0}


def validate_symlinks_targeted(btrfs_symlinks: list, snapshot_path: Path, 
                              max_check: int = 10, concise: bool = False) -> ValidationResult:
    """Fast targeted validation - directly check specific symlink paths in snapshot."""
    validated = 0
    missing = 0
    mismatched_targets = 0
    
    for btrfs_sym in btrfs_symlinks[:max_check]:  # Check first N
        path = btrfs_sym['path']  # This is already relative path from btrfs diff
        expected_target = btrfs_sym['details']['path_link']
        
        # Check symlink directly in snapshot
        full_path = snapshot_path / path
        try:
            # Check if it's a symlink first (works even for broken symlinks)
            if full_path.is_symlink():
                actual_target = full_path.readlink()
                if str(actual_target) == str(expected_target):
                    validated += 1
                else:
                    mismatched_targets += 1
            elif full_path.exists():
                missing += 1
            else:
                missing += 1
        except (OSError, UnicodeError) as e:
            missing += 1
    
    return ValidationResult(
        validated=validated,
        missing=missing,
        mismatched_targets=mismatched_targets
    )


def validate_deletions(btrfs_deletions: list, old_snapshot: Path, new_snapshot: Path, 
                      max_check: int = 10, concise: bool = False, 
                      collect_failures: bool = False) -> ValidationResult:
    """Validate deletions by comparing old vs new snapshot contents."""
    actually_deleted = 0
    found_in_new = 0
    missing_from_old = 0
    permission_errors = 0
    
    for deletion in btrfs_deletions[:max_check]:  # Check first N
        path = deletion['path']
        old_path = old_snapshot / path
        new_path = new_snapshot / path
        
        try:
            # Check if file existed in old snapshot
            if not old_path.exists():
                missing_from_old += 1
                continue
                
            # Check if file is gone from new snapshot
            if not new_path.exists():
                actually_deleted += 1
            else:
                found_in_new += 1
                    
        except (PermissionError, OSError) as e:
            permission_errors += 1
    
    return ValidationResult(
        validated=0,
        missing=0,
        actually_deleted=actually_deleted,
        found_in_new=found_in_new,
        missing_from_old=missing_from_old,
        permission_errors=permission_errors
    )


def validate_modifications(btrfs_modifications: list, old_snapshot: Path, new_snapshot: Path, 
                          max_check: int = 10, concise: bool = False, 
                          collect_failures: bool = False) -> ValidationResult:
    """Validate modifications by checking file existence and modification times."""
    file_exists = 0
    file_missing = 0
    mtime_in_range = 0
    mtime_out_of_range = 0
    permission_errors = 0
    
    # Parse snapshot time for mtime validation
    old_snap_time = parse_snapshot_time(old_snapshot.name)
    new_snap_time = parse_snapshot_time(new_snapshot.name)
    # Files should be modified between the two snapshot times
    time_window_start = old_snap_time
    time_window_end = new_snap_time
    
    for modification in btrfs_modifications[:max_check]:  # Check first N
        path = modification['path']
        new_path = new_snapshot / path
        old_path = old_snapshot / path
        
        try:
            # Check if file exists in new snapshot
            if new_path.exists():
                file_exists += 1
                
                # Check modification time
                stat = new_path.stat()
                file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                
                if time_window_start <= file_mtime <= time_window_end:
                    mtime_in_range += 1
                else:
                    mtime_out_of_range += 1
            else:
                file_missing += 1
                    
        except (PermissionError, OSError) as e:
            permission_errors += 1
    
    return ValidationResult(
        validated=0,
        missing=0,
        file_exists=file_exists,
        file_missing=file_missing,
        mtime_in_range=mtime_in_range,
        mtime_out_of_range=mtime_out_of_range,
        permission_errors=permission_errors
    )