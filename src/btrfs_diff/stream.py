# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.06.09
# License: (c) HRDAG, 2025, GPL-2 or newer
#
# ------
# btrfs-diff/src/btrfs_diff/stream.py

"""Btrfs send stream parser.

Adapted from btrfs-snapshots-diff by Jean-Denis Girard.
"""

from collections import OrderedDict
from struct import unpack
from typing import Final


class BtrfsStream:
    """Btrfs send stream representation."""
    
    # From btrfs/send.h
    SEND_CMDS: Final = (
        'BTRFS_SEND_C_UNSPEC BTRFS_SEND_C_SUBVOL BTRFS_SEND_C_SNAPSHOT '
        'BTRFS_SEND_C_MKFILE BTRFS_SEND_C_MKDIR BTRFS_SEND_C_MKNOD '
        'BTRFS_SEND_C_MKFIFO BTRFS_SEND_C_MKSOCK BTRFS_SEND_C_SYMLINK '
        'BTRFS_SEND_C_RENAME BTRFS_SEND_C_LINK BTRFS_SEND_C_UNLINK '
        'BTRFS_SEND_C_RMDIR BTRFS_SEND_C_SET_XATTR '
        'BTRFS_SEND_C_REMOVE_XATTR BTRFS_SEND_C_WRITE BTRFS_SEND_C_CLONE '
        'BTRFS_SEND_C_TRUNCATE BTRFS_SEND_C_CHMOD BTRFS_SEND_C_CHOWN '
        'BTRFS_SEND_C_UTIMES BTRFS_SEND_C_END BTRFS_SEND_C_UPDATE_EXTENT'
    ).split()
    
    SEND_ATTRS: Final = (
        'BTRFS_SEND_A_UNSPEC BTRFS_SEND_A_UUID BTRFS_SEND_A_CTRANSID '
        'BTRFS_SEND_A_INO BTRFS_SEND_A_SIZE BTRFS_SEND_A_MODE '
        'BTRFS_SEND_A_UID BTRFS_SEND_A_GID BTRFS_SEND_A_RDEV '
        'BTRFS_SEND_A_CTIME BTRFS_SEND_A_MTIME BTRFS_SEND_A_ATIME '
        'BTRFS_SEND_A_OTIME BTRFS_SEND_A_XATTR_NAME '
        'BTRFS_SEND_A_XATTR_DATA BTRFS_SEND_A_PATH BTRFS_SEND_A_PATH_TO '
        'BTRFS_SEND_A_PATH_LINK BTRFS_SEND_A_FILE_OFFSET '
        'BTRFS_SEND_A_DATA BTRFS_SEND_A_CLONE_UUID '
        'BTRFS_SEND_A_CLONE_CTRANSID BTRFS_SEND_A_CLONE_PATH '
        'BTRFS_SEND_A_CLONE_OFFSET BTRFS_SEND_A_CLONE_LEN'
    ).split()
    
    # From btrfs/ioctl.h:#define BTRFS_UUID_SIZE 16
    BTRFS_UUID_SIZE: Final = 16
    
    # Headers length
    L_HEAD: Final = 10
    L_TLV: Final = 4
    
    def __init__(self, stream_data: bytes):
        self.stream = stream_data
        
        if len(self.stream) < 17:
            raise ValueError('Invalid stream length')
            
        magic, _, self.version = unpack('<12scI', self.stream[0:17])
        if magic != b'btrfs-stream':
            raise ValueError('Not a Btrfs stream!')
    
    def _tlv_get_string(self, attr_type: str, index: int) -> tuple[int, str]:
        attr, l_attr = unpack('<HH', 
                             self.stream[index:index + self.L_TLV])
        if self.SEND_ATTRS[attr] != attr_type:
            raise ValueError(f'Unexpected attribute {self.SEND_ATTRS[attr]}')
        ret, = unpack(f'<{l_attr}s', 
                     self.stream[index + self.L_TLV:
                                index + self.L_TLV + l_attr])
        return index + self.L_TLV + l_attr, ret.decode('utf8')
    
    def _tlv_get_u64(self, attr_type: str, index: int) -> tuple[int, int]:
        attr, l_attr = unpack('<HH', 
                             self.stream[index:index + self.L_TLV])
        if self.SEND_ATTRS[attr] != attr_type:
            raise ValueError(f'Unexpected attribute {self.SEND_ATTRS[attr]}')
        ret, = unpack('<Q', self.stream[index + self.L_TLV:
                                       index + self.L_TLV + l_attr])
        return index + self.L_TLV + l_attr, ret
    
    def decode(self) -> tuple[list[dict], dict[str, list[int]]]:
        """Decode commands + attributes from send stream."""
        offset = 17
        cmd_ref = 0
        commands = []
        paths = OrderedDict()
        
        while True:
            l_cmd, cmd, _ = unpack('<IHI', 
                                  self.stream[offset:offset + self.L_HEAD])
            try:
                command = self.SEND_CMDS[cmd]
            except IndexError:
                raise ValueError(f'Unknown command {cmd}') from None
                
            cmd_short = command[13:].lower()
            offset += self.L_HEAD
            
            if command == 'BTRFS_SEND_C_RENAME':
                offset2, path = self._tlv_get_string('BTRFS_SEND_A_PATH', 
                                                    offset)
                offset2, path_to = self._tlv_get_string(
                    'BTRFS_SEND_A_PATH_TO', offset2)
                paths.setdefault(path, []).append(cmd_ref)
                commands.append({
                    'command': cmd_short, 
                    'path': path, 
                    'path_to': path_to
                })
                
            elif command in ['BTRFS_SEND_C_MKFILE', 'BTRFS_SEND_C_MKDIR', 
                           'BTRFS_SEND_C_UNLINK', 'BTRFS_SEND_C_RMDIR']:
                offset2, path = self._tlv_get_string('BTRFS_SEND_A_PATH', 
                                                    offset)
                paths.setdefault(path, []).append(cmd_ref)
                commands.append({'command': cmd_short, 'path': path})
                
            elif command == 'BTRFS_SEND_C_SYMLINK':
                offset2, path = self._tlv_get_string('BTRFS_SEND_A_PATH', 
                                                    offset)
                offset2, ino = self._tlv_get_u64('BTRFS_SEND_A_INO', offset2)
                offset2, path_link = self._tlv_get_string(
                    'BTRFS_SEND_A_PATH_LINK', offset2)
                paths.setdefault(path, []).append(cmd_ref)
                commands.append({
                    'command': cmd_short, 
                    'path': path,
                    'inode': ino,
                    'path_link': path_link
                })
                
            elif command == 'BTRFS_SEND_C_TRUNCATE':
                offset2, path = self._tlv_get_string('BTRFS_SEND_A_PATH', 
                                                    offset)
                offset2, size = self._tlv_get_u64('BTRFS_SEND_A_SIZE', 
                                                offset2)
                paths.setdefault(path, []).append(cmd_ref)
                commands.append({
                    'command': cmd_short, 
                    'path': path, 
                    'size': size
                })
                
            elif command == 'BTRFS_SEND_C_UPDATE_EXTENT':
                offset2, path = self._tlv_get_string('BTRFS_SEND_A_PATH', 
                                                    offset)
                offset2, file_offset = self._tlv_get_u64(
                    'BTRFS_SEND_A_FILE_OFFSET', offset2)
                offset2, size = self._tlv_get_u64('BTRFS_SEND_A_SIZE', 
                                                offset2)
                paths.setdefault(path, []).append(cmd_ref)
                commands.append({
                    'command': cmd_short,
                    'path': path,
                    'file_offset': file_offset,
                    'size': size
                })
                
            elif command == 'BTRFS_SEND_C_END':
                commands.append({'command': cmd_short})
                break
                
            elif command == 'BTRFS_SEND_C_UNSPEC':
                commands.append({'command': cmd_short})
                
            # For now, skip other commands we don't need
            
            offset += l_cmd
            cmd_ref += 1
            
        return commands, paths