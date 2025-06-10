# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.05.13
# License: (c) HRDAG, 2025, GPL-2 or newer
#
# ------
# tests/conftest.py
"""Pytest configuration for btrfs-diff tests."""

import pytest


def pytest_addoption(parser):
    """Add custom command-line options."""
    parser.addoption(
        "--run-btrfs-tests",
        action="store_true",
        default=False,
        help="Run tests that require a btrfs filesystem and sudo access",
    )
    parser.addoption(
        "--btrfs-path",
        action="store",
        default="/tmp",
        help="Path to a btrfs filesystem for integration tests",
    )


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "btrfs_required: mark test as requiring btrfs filesystem and sudo",
    )


def pytest_collection_modifyitems(config, items):
    """Skip btrfs tests unless --run-btrfs-tests is passed."""
    if not config.getoption("--run-btrfs-tests"):
        skip_btrfs = pytest.mark.skip(
            reason="need --run-btrfs-tests option to run"
        )
        for item in items:
            if "btrfs_required" in item.keywords:
                item.add_marker(skip_btrfs)