# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.06.09
# Copyright (C) 2025 HRDAG https://hrdag.org
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.
#
# ------
# btrfs-diff/src/btrfs_diff/parser.py

"""Main btrfs snapshot parser."""

import json
import subprocess
from collections import OrderedDict
from pathlib import Path

from .stream import BtrfsStream
from .types import FileChange, ChangeDetails


class BtrfsParser:
    """Extract file changes between two btrfs snapshots."""
    
    def __init__(self, old_snapshot: Path | str, new_snapshot: Path | str):
        self.old_snapshot = Path(old_snapshot)
        self.new_snapshot = Path(new_snapshot)
        
        if not self.old_snapshot.exists():
            raise ValueError(f"Old snapshot does not exist: {old_snapshot}")
        if not self.new_snapshot.exists():
            raise ValueError(f"New snapshot does not exist: {new_snapshot}")
    
    def _run_btrfs_send(self) -> bytes:
        """Run btrfs send and return the output stream."""
        cmd = [
            "sudo", "btrfs", "send", "--no-data",
            "-p", str(self.old_snapshot),
            str(self.new_snapshot)
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"btrfs send failed: {e.stderr.decode()}") from e
    
    def _is_orphan_path(self, path: str) -> bool:
        """Check if path is an orphan inode (temporary btrfs send name)."""
        import re
        orphan_pattern = r'(^|/)o\d+-\d+-\d+(/|$)'
        return bool(re.search(orphan_pattern, path))
    
    def _is_phantom_deletion(self, path: str) -> bool:
        """Check if a path marked for deletion actually existed in the old snapshot."""
        try:
            return not (self.old_snapshot / path).exists()
        except (OSError, UnicodeError):
            # If we can't check, assume it's real to be safe
            return False

    def get_changes(self, debug: bool = False) -> list[dict]:
        """Get all file changes between snapshots as JSON-serializable list."""
        send_stream = self._run_btrfs_send()
        stream = BtrfsStream(send_stream)
        commands, paths = stream.decode()
        
        if debug:
            print(f"Total commands: {len(commands)}")
            cmd_counts = {}
            for cmd in commands:
                cmd_type = cmd.get('command', 'unknown')
                cmd_counts[cmd_type] = cmd_counts.get(cmd_type, 0) + 1
            print(f"Command counts: {cmd_counts}")
        
        # Build rename chain map to resolve orphan paths
        rename_map = {}
        reverse_rename_map = {}  # To trace orphan paths back to original names
        
        for cmd in commands:
            if cmd.get('command') == 'rename':
                source = cmd['path']
                dest = cmd['path_to']
                rename_map[source] = dest
                reverse_rename_map[dest] = source
        
        # Track which orphan paths get deleted (to avoid following their chains)
        deleted_orphans = set()
        for cmd in commands:
            if cmd.get('command') in ['rmdir', 'unlink']:
                path = cmd['path']
                if self._is_orphan_path(path):
                    deleted_orphans.add(path)
        
        if debug:
            print(f"Rename map entries: {len(rename_map)}")
            if len(rename_map) > 0:
                print("First 5 renames:")
                for i, (src, dst) in enumerate(list(rename_map.items())[:5]):
                    print(f"  {src} -> {dst}")
        
        # Resolve rename chains (follow orphan → final destination)
        def resolve_final_path(path: str) -> str:
            seen = set()
            current = path
            original = path
            while current in rename_map and current not in seen:
                seen.add(current)
                next_path = rename_map[current]
                # Stop if the next path is a deleted orphan
                if next_path in deleted_orphans:
                    if debug:
                        print(f"Stopped at deleted orphan: {next_path}")
                    break
                current = next_path
            if debug and original != current:
                print(f"Resolved: {original} -> {current}")
            return current
        
        # Trace back from orphan path to original path
        def trace_original_path(orphan_path: str) -> str:
            """Trace an orphan path back to its original non-orphan name."""
            # Try direct lookup first  
            if orphan_path in reverse_rename_map:
                traced = reverse_rename_map[orphan_path]
                # If the traced path still contains orphans, recursively trace it
                if self._is_orphan_path(traced) or '/' in traced and any(
                    self._is_orphan_path(p) for p in traced.split('/')
                ):
                    return trace_original_path(traced)
                return traced
            
            # Handle paths with orphan components like "o257-106840-0/file.txt"
            parts = orphan_path.split('/')
            if len(parts) > 1 and self._is_orphan_path(parts[0]):
                # Trace the base orphan
                traced_base = trace_original_path(parts[0])
                if traced_base != parts[0]:
                    # Reconstruct with traced base
                    remaining = '/'.join(parts[1:])
                    return f"{traced_base}/{remaining}"
            
            return orphan_path  # Return as-is if can't trace back
        
        # Pre-analysis: identify truly deleted vs delete+recreate patterns
        unlinked_files = set()
        recreated_files = set()
        
        for cmd in commands:
            if 'path' in cmd:
                path = cmd['path']
                if cmd['command'] == 'unlink':
                    unlinked_files.add(path)
                elif cmd['command'] in ['mkfile', 'update_extent', 'truncate']:
                    recreated_files.add(path)
        
        truly_deleted = unlinked_files - recreated_files
        delete_recreate = unlinked_files & recreated_files
        
        if debug:
            print(f"Pre-analysis: {len(unlinked_files)} unlinked, {len(recreated_files)} recreated")
            print(f"Truly deleted: {len(truly_deleted)}, Delete+recreate: {len(delete_recreate)}")
        
        # First pass: collect all actions by path, preserving order
        path_actions = {}  # path -> list of (action, cmd, order)
        
        # SEPARATE TRACKING: symlinks need special handling because they start as orphans
        symlink_commands = {}  # original_path -> command
        for cmd in commands:
            if cmd.get('command') == 'symlink':
                symlink_commands[cmd['path']] = cmd
        
        order = 0
        for cmd in commands:
            if 'path' not in cmd:
                continue
                
            path = cmd['path']
            cmd_type = cmd['command']
            order += 1
            
            # Special handling for symlinks: resolve through rename chain first
            if cmd_type == 'symlink':
                final_path = resolve_final_path(path)
                is_orphan = self._is_orphan_path(final_path)
                if debug:
                    print(f"Symlink: {path} -> final: {final_path}, orphan: {is_orphan}")
                # Only include if final destination is not orphan
                if not is_orphan:
                    # Check if this symlink actually exists in the new snapshot
                    symlink_exists_in_new = (self.new_snapshot / final_path).exists()
                    
                    # Update command to show final path
                    updated_cmd = cmd.copy()
                    updated_cmd['path'] = final_path
                    if final_path not in path_actions:
                        path_actions[final_path] = []
                    
                    # Classify based on whether symlink exists in new snapshot
                    if symlink_exists_in_new:
                        path_actions[final_path].append(('modified', updated_cmd, order))
                        if debug:
                            print(f"  -> Added symlink (modified): {final_path}")
                    else:
                        # Check if this symlink actually existed in old snapshot
                        if not self._is_phantom_deletion(final_path):
                            path_actions[final_path].append(('deleted', updated_cmd, order))
                            if debug:
                                print(f"  -> Added symlink (deleted): {final_path}")
                        elif debug:
                            print(f"  -> Skipped phantom symlink deletion: {final_path}")
                elif debug:
                    print(f"  -> Skipped (orphan): {final_path}")
            
            # Modified/new files and directories (excluding symlinks handled above)
            elif cmd_type in ['mkfile', 'mkdir', 'truncate', 'update_extent']:
                # Skip orphan paths for modifications
                if self._is_orphan_path(path):
                    continue
                if path not in path_actions:
                    path_actions[path] = []
                path_actions[path].append(('modified', cmd, order))
            
            # Deleted files and directories  
            elif cmd_type in ['unlink', 'rmdir']:
                # For orphan paths, try to trace back to original path
                actual_path = path
                if self._is_orphan_path(path):
                    original = trace_original_path(path)
                    if original != path:
                        # This orphan was renamed from a real path
                        actual_path = original
                        if debug:
                            print(f"Traced orphan deletion: {path} -> {original}")
                    else:
                        # Pure orphan path with no traceable origin, skip
                        continue
                
                # Skip phantom deletions (files that never existed in old snapshot)
                if self._is_phantom_deletion(actual_path):
                    if debug:
                        print(f"Skipping phantom deletion: {actual_path}")
                    continue
                
                # Record the deletion using the original path
                if actual_path not in path_actions:
                    path_actions[actual_path] = []
                
                # Update the command to use the original path
                updated_cmd = cmd.copy()
                updated_cmd['path'] = actual_path
                path_actions[actual_path].append(('deleted', updated_cmd, order))
            
            # Renamed files - only track non-orphan sources with non-orphan finals
            elif cmd_type == 'rename':
                # Skip renames that involve symlinks (handled above)
                if path in symlink_commands:
                    continue
                    
                if not self._is_orphan_path(path):  # Real source path
                    # Check if this rename leads to a deleted orphan
                    direct_dest = cmd.get('path_to', '')
                    if direct_dest in deleted_orphans:
                        # This is a rename-to-delete pattern, skip it
                        if debug:
                            print(f"Skipping rename to deleted orphan: {path} -> {direct_dest}")
                        continue
                    
                    final_dest = resolve_final_path(path)
                    if not self._is_orphan_path(final_dest):  # Real destination
                        # Update the details to show final destination
                        updated_cmd = cmd.copy()
                        updated_cmd['path_to'] = final_dest
                        if path not in path_actions:
                            path_actions[path] = []
                        path_actions[path].append(('renamed', updated_cmd, order))
        
        # Second pass: resolve conflicts for each path
        changes = []
        for path, actions in path_actions.items():
            if not actions:
                # Skip paths with no valid actions (all were filtered out)
                continue
            elif len(actions) == 1:
                # Simple case - only one action
                action, cmd, _ = actions[0]
                changes.append({
                    'path': path,
                    'action': action,
                    'details': cmd
                })
            else:
                # Multiple actions - need to resolve net effect
                has_delete = any(action == 'deleted' for action, _, _ in actions)
                has_modify = any(action == 'modified' for action, _, _ in actions)
                has_rename = any(action == 'renamed' for action, _, _ in actions)
                
                if has_delete and (has_modify or has_rename):
                    # Special case: directory replaced with symlink
                    # Report both the deletion and the symlink creation
                    delete_cmd = None
                    symlink_cmd = None
                    
                    for action, cmd, order in actions:
                        if action == 'deleted' and cmd.get('command') == 'rmdir':
                            delete_cmd = (action, cmd, order)
                        elif action == 'modified' and cmd.get('command') == 'symlink':
                            symlink_cmd = (action, cmd, order)
                    
                    if delete_cmd and symlink_cmd:
                        # Report both directory deletion and symlink creation
                        changes.append({
                            'path': path,
                            'action': delete_cmd[0],
                            'details': delete_cmd[1]
                        })
                        changes.append({
                            'path': path,
                            'action': symlink_cmd[0],
                            'details': symlink_cmd[1]
                        })
                        if debug:
                            print(f"Resolved conflict for {path}: rmdir+symlink -> both reported")
                    else:
                        # Normal case: Delete followed by modify/rename = net effect is modified
                        # Use the last modify/rename action
                        last_modify = None
                        for action, cmd, order in actions:
                            if action in ['modified', 'renamed']:
                                if last_modify is None or order > last_modify[2]:
                                    last_modify = (action, cmd, order)
                        
                        if last_modify:
                            changes.append({
                                'path': path,
                                'action': last_modify[0],
                                'details': last_modify[1]
                            })
                            if debug:
                                print(f"Resolved conflict for {path}: delete+{last_modify[0]} -> {last_modify[0]}")
                elif has_rename and has_modify:
                    # Rename + modify = use rename (more structural change)
                    rename_action = None
                    for action, cmd, order in actions:
                        if action == 'renamed':
                            rename_action = (action, cmd, order)
                            break
                    
                    if rename_action:
                        changes.append({
                            'path': path,
                            'action': rename_action[0],
                            'details': rename_action[1]
                        })
                        if debug:
                            print(f"Resolved conflict for {path}: rename+modify -> rename")
                else:
                    # Use the last action in chronological order
                    last_action = max(actions, key=lambda x: x[2])
                    changes.append({
                        'path': path,
                        'action': last_action[0],
                        'details': last_action[1]
                    })
                    if debug:
                        print(f"Used last action for {path}: {last_action[0]}")
        
        return sorted(changes, key=lambda c: (c['action'], c['path']))


def get_btrfs_diff(old_snapshot: Path | str, 
                  new_snapshot: Path | str, debug: bool = False) -> str:
    """Get btrfs differences between two snapshots as JSON string."""
    parser = BtrfsParser(Path(old_snapshot), Path(new_snapshot))
    changes = parser.get_changes(debug=debug)
    return json.dumps(changes, indent=2)