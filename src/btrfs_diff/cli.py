# Author: PB & Claude
# Maintainer: PB
# Original date: 2025.06.09
# License: (c) HRDAG, 2025, GPL-2 or newer
#
# ------
# btrfs-diff/src/btrfs_diff/cli.py

"""Command line interface for btrfs-diff."""

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich import print
from rich.console import Console
from rich.table import Table

from .parser import BtrfsParser, get_btrfs_diff
from .validator import (
    validate_deletions,
    validate_modifications,
    validate_symlinks_targeted
)

app = typer.Typer(help="Parse and analyze differences between btrfs snapshots")
console = Console()


@app.command()
def diff(
    old_snapshot: Path = typer.Argument(..., help="Path to old snapshot"),
    new_snapshot: Path = typer.Argument(..., help="Path to new snapshot"),
    output_format: str = typer.Option("json", "--format", "-f", 
                                     help="Output format: json, summary, table"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug output")
) -> None:
    """Get differences between two btrfs snapshots."""
    try:
        if debug:
            console.print(f"[blue]Analyzing snapshots:[/blue]")
            console.print(f"  Old: {old_snapshot}")
            console.print(f"  New: {new_snapshot}")
        
        parser = BtrfsParser(old_snapshot, new_snapshot)
        changes = parser.get_changes(debug=debug)
        
        if output_format == "json":
            print(json.dumps(changes, indent=2))
        elif output_format == "summary":
            _print_summary(changes)
        elif output_format == "table":
            _print_table(changes)
        else:
            typer.echo(f"Unknown format: {output_format}", err=True)
            raise typer.Exit(1)
            
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def validate(
    old_snapshot: Path = typer.Argument(..., help="Path to old snapshot"),
    new_snapshot: Path = typer.Argument(..., help="Path to new snapshot"),
    sample_size: int = typer.Option(10, "--sample", "-s", 
                                   help="Number of items to validate per type"),
    verbose: bool = typer.Option(False, "--verbose", "-v", 
                                help="Verbose output"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug output")
) -> None:
    """Validate btrfs diff results against actual filesystem changes."""
    try:
        if debug or verbose:
            console.print(f"[blue]Validating changes:[/blue]")
            console.print(f"  Old: {old_snapshot}")
            console.print(f"  New: {new_snapshot}")
            console.print(f"  Sample size: {sample_size}")
        
        # Get btrfs diff
        result = get_btrfs_diff(old_snapshot, new_snapshot, debug=debug)
        changes = json.loads(result)
        
        # Separate by type
        symlinks = [c for c in changes if c['details']['command'] == 'symlink']
        deletions = [c for c in changes if c['action'] == 'deleted']
        modifications = [c for c in changes if c['action'] == 'modified']
        
        if verbose:
            console.print(f"\n[yellow]Found changes:[/yellow]")
            console.print(f"  Symlinks: {len(symlinks)}")
            console.print(f"  Deletions: {len(deletions)}")
            console.print(f"  Modifications: {len(modifications)}")
        
        # Run validations
        results = {}
        
        if symlinks:
            results['symlinks'] = validate_symlinks_targeted(
                symlinks, new_snapshot, min(sample_size, len(symlinks)), 
                concise=not verbose
            )
        
        if deletions:
            results['deletions'] = validate_deletions(
                deletions, old_snapshot, new_snapshot, 
                min(sample_size, len(deletions)), concise=not verbose
            )
        
        if modifications:
            results['modifications'] = validate_modifications(
                modifications, old_snapshot, new_snapshot, 
                min(sample_size, len(modifications)), concise=not verbose
            )
        
        # Print results
        _print_validation_results(results, len(changes))
        
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def comprehensive(
    snapshot_root: Path = typer.Argument(..., 
                                        help="Root directory containing snapshots"),
    sample_size: int = typer.Option(1000, "--sample", "-s", 
                                   help="Sample size for validation"),
    pattern: str = typer.Option("data.2024*", "--pattern", "-p",
                               help="Snapshot name pattern to match")
) -> None:
    """Run comprehensive validation across multiple snapshot pairs."""
    try:
        # Get snapshots matching pattern
        snapshots = sorted([
            d for d in snapshot_root.iterdir() 
            if d.is_dir() and d.name.startswith(pattern.replace('*', ''))
        ])
        
        if len(snapshots) < 2:
            typer.echo(f"Need at least 2 snapshots matching {pattern}", err=True)
            raise typer.Exit(1)
        
        console.print(f"[blue]Running comprehensive validation:[/blue]")
        console.print(f"Found {len(snapshots)} snapshots")
        console.print(f"Sample size: {sample_size:,}")
        
        results = []
        
        # Test all consecutive pairs
        for i in range(len(snapshots) - 1):
            old_snap = snapshots[i]
            new_snap = snapshots[i + 1]
            
            console.print(f"\n[yellow]Processing:[/yellow] {old_snap.name} -> {new_snap.name}")
            
            # Get changes
            btrfs_result = get_btrfs_diff(old_snap, new_snap)
            changes = json.loads(btrfs_result)
            
            # Separate by type
            symlinks = [c for c in changes if c['details']['command'] == 'symlink']
            deletions = [c for c in changes if c['action'] == 'deleted']
            modifications = [c for c in changes if c['action'] == 'modified']
            
            # Run validations
            sym_result = validate_symlinks_targeted(symlinks, new_snap, 
                                                   min(sample_size, len(symlinks)), 
                                                   concise=True) if symlinks else None
            del_result = validate_deletions(deletions, old_snap, new_snap, 
                                          min(sample_size, len(deletions)), 
                                          concise=True) if deletions else None
            mod_result = validate_modifications(modifications, old_snap, new_snap, 
                                              min(sample_size, len(modifications)), 
                                              concise=True) if modifications else None
            
            results.append({
                'old_snap': old_snap.name,
                'new_snap': new_snap.name,
                'total_changes': len(changes),
                'symlinks': {'total': len(symlinks), 'result': sym_result},
                'deletions': {'total': len(deletions), 'result': del_result},
                'modifications': {'total': len(modifications), 'result': mod_result}
            })
        
        # Print comprehensive table
        _print_comprehensive_table(results)
        
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


def _print_summary(changes: list[dict]) -> None:
    """Print a summary of changes."""
    from collections import Counter
    
    by_action = Counter(c['action'] for c in changes)
    by_command = Counter(c['details']['command'] for c in changes)
    
    console.print(f"\n[bold]Summary of {len(changes)} changes:[/bold]")
    console.print(f"  Modified: {by_action.get('modified', 0)}")
    console.print(f"  Deleted: {by_action.get('deleted', 0)}")
    console.print(f"  Renamed: {by_action.get('renamed', 0)}")
    
    console.print(f"\n[bold]By command type:[/bold]")
    for cmd, count in by_command.most_common():
        console.print(f"  {cmd}: {count}")


def _print_table(changes: list[dict]) -> None:
    """Print changes in table format."""
    table = Table(title="Btrfs Changes")
    table.add_column("Action", style="cyan")
    table.add_column("Path", style="green")
    table.add_column("Command", style="yellow")
    table.add_column("Details", style="magenta")
    
    for change in changes[:50]:  # Limit to first 50
        details = ""
        if change['details'].get('path_to'):
            details = f"→ {change['details']['path_to']}"
        elif change['details'].get('path_link'):
            details = f"→ {change['details']['path_link']}"
        elif change['details'].get('size'):
            details = f"size: {change['details']['size']}"
            
        table.add_row(
            change['action'],
            change['path'][:60] + "..." if len(change['path']) > 60 else change['path'],
            change['details']['command'],
            details
        )
    
    if len(changes) > 50:
        table.add_row("...", f"({len(changes) - 50} more)", "", "")
    
    console.print(table)


def _print_validation_results(results: dict, total_changes: int) -> None:
    """Print validation results."""
    console.print(f"\n[bold]Validation Results ({total_changes} total changes):[/bold]")
    
    for change_type, result in results.items():
        console.print(f"\n[yellow]{change_type.title()}:[/yellow]")
        
        if change_type == 'symlinks':
            console.print(f"  Validated: {result.validated}")
            console.print(f"  Missing: {result.missing}")
            console.print(f"  Mismatched targets: {result.mismatched_targets}")
            accuracy = (result.validated / (result.validated + result.missing + result.mismatched_targets) * 100) if (result.validated + result.missing + result.mismatched_targets) > 0 else 0
            console.print(f"  Accuracy: {accuracy:.1f}%")
            
        elif change_type == 'deletions':
            console.print(f"  Actually deleted: {result.actually_deleted}")
            console.print(f"  Found in new: {result.found_in_new}")
            console.print(f"  Missing from old: {result.missing_from_old}")
            accuracy = (result.actually_deleted / (result.actually_deleted + result.found_in_new) * 100) if (result.actually_deleted + result.found_in_new) > 0 else 0
            console.print(f"  Accuracy: {accuracy:.1f}%")
            
        elif change_type == 'modifications':
            console.print(f"  File exists: {result.file_exists}")
            console.print(f"  File missing: {result.file_missing}")
            console.print(f"  Timing in range: {result.mtime_in_range}")
            console.print(f"  Timing out of range: {result.mtime_out_of_range}")
            accuracy = (result.file_exists / (result.file_exists + result.file_missing) * 100) if (result.file_exists + result.file_missing) > 0 else 0
            console.print(f"  Existence accuracy: {accuracy:.1f}%")


def _print_comprehensive_table(results: list[dict]) -> None:
    """Print comprehensive validation table."""
    table = Table(title="Comprehensive Validation Results")
    table.add_column("Snapshot Pair", style="cyan")
    table.add_column("Total", style="white")
    table.add_column("Symlinks", style="green")
    table.add_column("Deletions", style="red")
    table.add_column("Modifications", style="yellow")
    
    for r in results:
        pair = f"{r['old_snap'][-15:]} → {r['new_snap'][-15:]}"
        
        sym_str = "N/A"
        if r['symlinks']['result']:
            sym_ok = r['symlinks']['result'].validated
            sym_total = sym_ok + r['symlinks']['result'].missing + r['symlinks']['result'].mismatched_targets
            sym_str = f"{sym_ok}/{sym_total}" if sym_total > 0 else "0/0"
        
        del_str = "N/A"
        if r['deletions']['result']:
            del_ok = r['deletions']['result'].actually_deleted
            del_total = del_ok + r['deletions']['result'].found_in_new
            del_str = f"{del_ok}/{del_total}" if del_total > 0 else "0/0"
        
        mod_str = "N/A"
        if r['modifications']['result']:
            mod_ok = r['modifications']['result'].file_exists
            mod_total = mod_ok + r['modifications']['result'].file_missing
            mod_str = f"{mod_ok}/{mod_total}" if mod_total > 0 else "0/0"
        
        table.add_row(pair, str(r['total_changes']), sym_str, del_str, mod_str)
    
    console.print(table)


def main() -> None:
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()