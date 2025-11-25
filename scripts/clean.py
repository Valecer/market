#!/usr/bin/env python3
"""
Project cleanup script - Removes cache files, coverage reports, and build artifacts.

Usage:
    python clean.py          # Dry run (shows what would be deleted)
    python clean.py --yes    # Actually delete files
    python clean.py --help   # Show help
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import List, Tuple


# Patterns to match files/directories to delete
PATTERNS_TO_DELETE = [
    # Python cache
    ("__pycache__", "dir"),
    ("*.pyc", "file"),
    ("*.pyo", "file"),
    ("*.pyd", "file"),
    ("*.py[cod]", "file"),
    ("*$py.class", "file"),
    
    # Coverage
    (".coverage", "file"),
    (".coverage.*", "file"),
    ("htmlcov", "dir"),
    ("coverage", "dir"),
    (".coverage_html", "dir"),
    
    # Testing
    (".pytest_cache", "dir"),
    (".mypy_cache", "dir"),
    (".ruff_cache", "dir"),
    (".tox", "dir"),
    (".hypothesis", "dir"),
    (".noseids", "file"),
    
    # Build artifacts
    ("dist", "dir"),
    ("build", "dir"),
    ("*.egg-info", "dir"),
    (".eggs", "dir"),
    ("*.egg", "file"),
    
    # IDE
    (".vscode", "dir"),
    (".idea", "dir"),
    ("*.swp", "file"),
    ("*.swo", "file"),
    ("*~", "file"),
    
    # OS
    (".DS_Store", "file"),
    ("Thumbs.db", "file"),
    ("Desktop.ini", "file"),
    
    # Temporary files
    ("*.tmp", "file"),
    ("*.temp", "file"),
    ("*.log", "file"),
    ("tmp", "dir"),
    ("temp", "dir"),
    
    # Other
    (".Python", "file"),
    ("pip-log.txt", "file"),
    ("pip-delete-this-directory.txt", "file"),
]


def find_items_to_delete(root: Path) -> Tuple[List[Path], List[Path]]:
    """Find all files and directories matching deletion patterns."""
    files_to_delete = []
    dirs_to_delete = []
    
    # Directories to skip (don't traverse into these)
    skip_dirs = {".git", "node_modules", "venv", ".venv", "env", ".env"}
    
    def should_skip(path: Path) -> bool:
        """Check if path should be skipped."""
        # Skip git directory
        if ".git" in path.parts:
            return True
        # Skip virtual environments
        if any(skip in path.parts for skip in skip_dirs):
            return True
        return False
    
    def matches_pattern(path: Path, pattern: str, item_type: str) -> bool:
        """Check if path matches a pattern."""
        name = path.name
        
        # Exact match
        if pattern == name:
            return True
        
        # Wildcard patterns
        if "*" in pattern:
            import fnmatch
            if fnmatch.fnmatch(name, pattern):
                return True
        
        return False
    
    # Walk through directory tree
    for root_path, dirs, files in os.walk(root):
        root_path = Path(root_path)
        
        # Skip certain directories
        if should_skip(root_path):
            dirs[:] = []  # Don't traverse into skipped dirs
            continue
        
        # Check files
        for file in files:
            file_path = root_path / file
            for pattern, item_type in PATTERNS_TO_DELETE:
                if item_type == "file" and matches_pattern(file_path, pattern, item_type):
                    files_to_delete.append(file_path)
                    break
        
        # Check directories (modify dirs list in place to skip traversal)
        dirs_to_check = list(dirs)
        for dir_name in dirs_to_check:
            dir_path = root_path / dir_name
            for pattern, item_type in PATTERNS_TO_DELETE:
                if item_type == "dir" and matches_pattern(dir_path, pattern, item_type):
                    dirs_to_delete.append(dir_path)
                    if dir_name in dirs:
                        dirs.remove(dir_name)  # Don't traverse into it
                    break
    
    # Remove duplicates and sort
    files_to_delete = sorted(set(files_to_delete))
    dirs_to_delete = sorted(set(dirs_to_delete))
    
    # Sort dirs by depth (deepest first) to avoid deleting parent before child
    dirs_to_delete.sort(key=lambda p: len(p.parts), reverse=True)
    
    return files_to_delete, dirs_to_delete


def format_size(size: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def calculate_total_size(items: List[Path]) -> int:
    """Calculate total size of files/directories."""
    total = 0
    for item in items:
        try:
            if item.is_file():
                total += item.stat().st_size
            elif item.is_dir():
                for root, dirs, files in os.walk(item):
                    for file in files:
                        try:
                            total += (Path(root) / file).stat().st_size
                        except (OSError, PermissionError):
                            pass
        except (OSError, PermissionError):
            pass
    return total


def delete_items(files: List[Path], dirs: List[Path], dry_run: bool = True) -> None:
    """Delete files and directories."""
    if not files and not dirs:
        print("✅ No files or directories to delete.")
        return
    
    print(f"\n📊 Summary:")
    print(f"   Files to delete: {len(files)}")
    print(f"   Directories to delete: {len(dirs)}")
    
    total_size = calculate_total_size(files + dirs)
    print(f"   Total size: {format_size(total_size)}")
    
    if dry_run:
        print("\n🔍 DRY RUN - No files will be deleted.")
        print("\nFiles to delete:")
        for file in files[:20]:  # Show first 20
            print(f"   {file}")
        if len(files) > 20:
            print(f"   ... and {len(files) - 20} more files")
        
        print("\nDirectories to delete:")
        for dir_path in dirs[:20]:  # Show first 20
            print(f"   {dir_path}")
        if len(dirs) > 20:
            print(f"   ... and {len(dirs) - 20} more directories")
        return
    
    # Actually delete
    print("\n🗑️  Deleting files and directories...")
    
    deleted_files = 0
    deleted_dirs = 0
    errors = []
    
    # Delete files
    for file_path in files:
        try:
            file_path.unlink()
            deleted_files += 1
        except (OSError, PermissionError) as e:
            errors.append((file_path, str(e)))
    
    # Delete directories
    for dir_path in dirs:
        try:
            shutil.rmtree(dir_path)
            deleted_dirs += 1
        except (OSError, PermissionError) as e:
            errors.append((dir_path, str(e)))
    
    print(f"\n✅ Deletion complete!")
    print(f"   Files deleted: {deleted_files}/{len(files)}")
    print(f"   Directories deleted: {deleted_dirs}/{len(dirs)}")
    
    if errors:
        print(f"\n⚠️  Errors ({len(errors)}):")
        for item, error in errors[:10]:
            print(f"   {item}: {error}")
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more errors")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean project of cache files, coverage reports, and build artifacts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python clean.py              # Dry run (shows what would be deleted)
  python clean.py --yes        # Actually delete files
  python clean.py -y           # Short form
        """
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Actually delete files (default is dry run)"
    )
    parser.add_argument(
        "--root",
        type=str,
        default=".",
        help="Root directory to clean (default: current directory)"
    )
    
    args = parser.parse_args()
    
    root = Path(args.root).resolve()
    
    if not root.exists():
        print(f"❌ Error: Root directory does not exist: {root}")
        sys.exit(1)
    
    print(f"🧹 Project Cleanup Script")
    print(f"   Root directory: {root}")
    print(f"   Mode: {'DELETE' if args.yes else 'DRY RUN'}")
    
    # Find items to delete
    print("\n🔍 Scanning for files and directories to delete...")
    files, dirs = find_items_to_delete(root)
    
    # Delete (or show what would be deleted)
    delete_items(files, dirs, dry_run=not args.yes)
    
    if not args.yes:
        print("\n💡 Tip: Run with --yes to actually delete files")


if __name__ == "__main__":
    main()

