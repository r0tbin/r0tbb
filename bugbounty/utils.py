"""
Utility functions for the bug bounty tool.
Handles file operations, locking, timing, and formatting.
"""

import json
import time
import gzip
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List
from contextlib import contextmanager
import tempfile
import os

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    # fcntl is not available on Windows
    HAS_FCNTL = False

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.panel import Panel


console = Console()


class FileLock:
    """Simple file-based locking mechanism."""
    
    def __init__(self, lock_file: Path, timeout: int = 30):
        self.lock_file = lock_file
        self.timeout = timeout
        self.fd = None
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
    
    def acquire(self):
        """Acquire the lock with timeout."""
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            try:
                # Use exclusive file creation for cross-platform locking
                self.fd = os.open(str(self.lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return
            except FileExistsError:
                time.sleep(0.1)
        
        raise TimeoutError(f"Could not acquire lock {self.lock_file} within {self.timeout} seconds")
    
    def release(self):
        """Release the lock."""
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
            try:
                os.unlink(self.lock_file)
            except FileNotFoundError:
                pass


@contextmanager
def file_lock(lock_file: Path, timeout: int = 30):
    """Context manager for file locking."""
    lock = FileLock(lock_file, timeout)
    try:
        lock.acquire()
        yield
    finally:
        lock.release()


def read_json(file_path: Path, default: Any = None) -> Any:
    """
    Read JSON file with error handling.
    
    Args:
        file_path: Path to JSON file
        default: Default value if file doesn't exist or is invalid
    
    Returns:
        Parsed JSON data or default value
    """
    try:
        if not file_path.exists():
            return default
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def write_json(file_path: Path, data: Any, ensure_parents: bool = True):
    """
    Write JSON file atomically.
    
    Args:
        file_path: Path to JSON file
        data: Data to write
        ensure_parents: Create parent directories if needed
    """
    if ensure_parents:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to temporary file first, then move
    temp_file = file_path.with_suffix('.tmp')
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Atomic move
        temp_file.replace(file_path)
    except Exception:
        # Clean up temp file on error
        if temp_file.exists():
            temp_file.unlink()
        raise


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def format_timestamp(timestamp: str) -> str:
    """
    Format ISO timestamp for display.
    
    Args:
        timestamp: ISO format timestamp
    
    Returns:
        Formatted timestamp string
    """
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, AttributeError):
        return timestamp


def calculate_eta(start_time: datetime, completed: int, total: int) -> Optional[int]:
    """
    Calculate estimated time to completion.
    
    Args:
        start_time: When the process started
        completed: Number of completed items
        total: Total number of items
    
    Returns:
        ETA in seconds, or None if cannot calculate
    """
    if completed <= 0 or total <= 0 or completed >= total:
        return None
    
    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    rate = completed / elapsed
    remaining = total - completed
    
    return int(remaining / rate) if rate > 0 else None


def create_progress_bar(description: str = "Processing"):
    """Create a rich progress bar."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    )


def print_status_table(data: List[Dict[str, str]], title: str = "Status"):
    """Print a formatted status table."""
    if not data:
        console.print(f"[yellow]No {title.lower()} data available[/yellow]")
        return
    
    table = Table(title=title, show_header=True, header_style="bold magenta")
    
    # Add columns based on first row
    if data:
        for key in data[0].keys():
            table.add_column(key.replace('_', ' ').title())
        
        # Add rows
        for row in data:
            table.add_row(*[str(v) for v in row.values()])
    
    console.print(table)


def print_panel(content: str, title: str = None, style: str = "blue"):
    """Print content in a panel."""
    console.print(Panel(content, title=title, border_style=style))


def tail_file(file_path: Path, lines: int = 100) -> List[str]:
    """
    Get the last N lines from a file.
    
    Args:
        file_path: Path to file
        lines: Number of lines to return
    
    Returns:
        List of lines
    """
    if not file_path.exists():
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            return all_lines[-lines:] if len(all_lines) > lines else all_lines
    except IOError:
        return []


def compress_file(source_path: Path, output_path: Path):
    """
    Compress a file using gzip.
    
    Args:
        source_path: Source file path
        output_path: Output compressed file path
    """
    with open(source_path, 'rb') as f_in:
        with gzip.open(output_path, 'wb') as f_out:
            f_out.writelines(f_in)


def create_zip_archive(source_dir: Path, output_path: Path, exclude_patterns: List[str] = None):
    """
    Create a ZIP archive from a directory.
    
    Args:
        source_dir: Source directory path
        output_path: Output ZIP file path
        exclude_patterns: File patterns to exclude
    """
    exclude_patterns = exclude_patterns or []
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in source_dir.rglob('*'):
            if file_path.is_file():
                # Check if file should be excluded
                should_exclude = False
                for pattern in exclude_patterns:
                    if file_path.match(pattern):
                        should_exclude = True
                        break
                
                if not should_exclude:
                    arcname = file_path.relative_to(source_dir)
                    zipf.write(file_path, arcname)


def check_stop_flag(target_dir: Path) -> bool:
    """
    Check if stop flag exists for a target.
    
    Args:
        target_dir: Target directory path
    
    Returns:
        True if stop flag exists
    """
    stop_flag = target_dir / ".stop"
    return stop_flag.exists()


def create_stop_flag(target_dir: Path):
    """
    Create stop flag for a target.
    
    Args:
        target_dir: Target directory path
    """
    stop_flag = target_dir / ".stop"
    stop_flag.touch()


def remove_stop_flag(target_dir: Path):
    """
    Remove stop flag for a target.
    
    Args:
        target_dir: Target directory path
    """
    stop_flag = target_dir / ".stop"
    if stop_flag.exists():
        stop_flag.unlink()


def safe_filename(filename: str) -> str:
    """
    Make a string safe for use as a filename.
    
    Args:
        filename: Original filename
    
    Returns:
        Safe filename
    """
    # Replace problematic characters
    safe_chars = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join(c if c in safe_chars else '_' for c in filename)


def get_file_size_mb(file_path: Path) -> float:
    """
    Get file size in MB.
    
    Args:
        file_path: File path
    
    Returns:
        File size in MB
    """
    try:
        return file_path.stat().st_size / (1024 * 1024)
    except (OSError, FileNotFoundError):
        return 0.0


def cleanup_old_files(directory: Path, max_age_days: int = 7, pattern: str = "*"):
    """
    Clean up old files in a directory.
    
    Args:
        directory: Directory to clean
        max_age_days: Maximum age in days
        pattern: File pattern to match
    """
    if not directory.exists():
        return
    
    cutoff_time = time.time() - (max_age_days * 24 * 3600)
    
    for file_path in directory.glob(pattern):
        if file_path.is_file():
            try:
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
            except (OSError, FileNotFoundError):
                pass