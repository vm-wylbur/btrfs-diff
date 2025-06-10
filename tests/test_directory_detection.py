# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.06.10
# License: (c) HRDAG, 2025, GPL-2 or newer
#
# ------
# tests/test_directory_detection.py

"""Unit tests for directory detection in btrfs-diff output."""

import json
from unittest.mock import Mock, patch
import pytest

from btrfs_diff.parser import BtrfsParser


class TestDirectoryDetection:
    """Test directory detection capabilities."""
    
    def test_directory_detection_field_missing(self):
        """Test that directory detection field is missing from output.
        
        This test documents the current bug: the btrfs-diff output doesn't
        include a reliable way to distinguish directories from files.
        """
        # Mock the parser to return a typical mkdir operation
        mock_parser = Mock(spec=BtrfsParser)
        mock_changes = [
            {
                'path': 'test_dir',
                'action': 'modified',
                'details': {
                    'command': 'mkdir',  # This is the internal command
                    'path': 'test_dir',
                    'size': None,
                    'inode': 12345
                }
            }
        ]
        mock_parser.get_changes.return_value = mock_changes
        
        changes = mock_parser.get_changes()
        directory_change = changes[0]
        
        # The bug: there's no reliable way to detect if this is a directory
        # from the output structure
        details = directory_change['details']
        
        # These assertions should fail with current implementation
        # because the directory detection information is not exposed
        assert 'is_directory' in details, "Directory detection field missing"
        assert details['is_directory'] is True, "Directory not properly detected"
    
    def test_file_vs_directory_distinction(self):
        """Test that files and directories can be distinguished in output."""
        # Mock changes that include both file and directory operations
        mock_changes = [
            {
                'path': 'test_file.txt',
                'action': 'modified', 
                'details': {
                    'command': 'mkfile',
                    'path': 'test_file.txt',
                    'size': 1024
                }
            },
            {
                'path': 'test_dir',
                'action': 'modified',
                'details': {
                    'command': 'mkdir', 
                    'path': 'test_dir',
                    'size': None
                }
            }
        ]
        
        # Extract directory and file changes
        file_change = mock_changes[0]
        dir_change = mock_changes[1]
        
        # The bug: both look identical in the output structure
        # We need a way to distinguish them
        file_details = file_change['details']
        dir_details = dir_change['details']
        
        # These should pass but currently fail due to missing directory detection
        assert 'is_directory' in file_details, "Missing is_directory field for file"
        assert 'is_directory' in dir_details, "Missing is_directory field for directory"
        assert file_details['is_directory'] is False, "File incorrectly marked as directory"
        assert dir_details['is_directory'] is True, "Directory not detected as directory"
    
    def test_command_field_not_exposed(self):
        """Test that raw btrfs command is not exposed in public API."""
        # This test documents that the raw btrfs command (mkdir/mkfile) 
        # is not reliably available in the details
        mock_changes = [
            {
                'path': 'test_dir',
                'action': 'modified',
                'details': {
                    'path': 'test_dir',
                    'size': None,
                    'inode': 12345
                    # Note: 'command' field is inconsistently available
                }
            }
        ]
        
        change = mock_changes[0]
        details = change['details']
        
        # The external code expects this to work but it doesn't reliably
        # This assertion should fail to demonstrate the bug
        assert details.get('command') == 'mkdir', "Raw command not available for directory detection"


if __name__ == "__main__":
    pytest.main([__file__])