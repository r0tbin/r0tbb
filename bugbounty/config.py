"""
Configuration management for the bug bounty tool.
Handles environment variables, paths, and global settings.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from .constants import (
    DEFAULT_CONCURRENCY,
    DEFAULT_TIMEOUT,
    DEFAULT_HARD_KILL_GRACE,
    LOGS_DIR,
    OUTPUTS_DIR,
    REPORTS_DIR,
    TMP_DIR
)


class Config:
    """Global configuration manager."""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Telegram configuration
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        self.CHAT_ID = os.getenv("CHAT_ID")
        
        # Directory configuration
        self.ROOT_DIR = Path(os.getenv("ROOT_DIR", ".")).resolve()
        self.WORK_DIR = os.getenv("WORK_DIR", "bug-bounty")
        
        # Execution configuration
        self.CONCURRENCY = int(os.getenv("CONCURRENCY", DEFAULT_CONCURRENCY))
        self.DEFAULT_TIMEOUT = int(os.getenv("DEFAULT_TIMEOUT", DEFAULT_TIMEOUT))
        self.HARD_KILL_GRACE = int(os.getenv("HARD_KILL_GRACE", DEFAULT_HARD_KILL_GRACE))
        
        # Logging configuration
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.MAX_LOG_SIZE = os.getenv("MAX_LOG_SIZE", "50MB")
        
        # Validate required configuration
        self._validate()
    
    def _validate(self):
        """Validate required configuration values."""
        if not self.ROOT_DIR.exists():
            raise ValueError(f"Root directory does not exist: {self.ROOT_DIR}")
    
    @property
    def work_dir_path(self) -> Path:
        """Get the work directory path."""
        return self.ROOT_DIR / self.WORK_DIR
    
    def target_dir(self, target: str) -> Path:
        """Get the target directory path."""
        return self.work_dir_path / target
    
    def logs_dir(self, target: str) -> Path:
        """Get the logs directory for a target."""
        return self.target_dir(target) / LOGS_DIR
    
    def outputs_dir(self, target: str) -> Path:
        """Get the outputs directory for a target."""
        return self.target_dir(target) / OUTPUTS_DIR
    
    def reports_dir(self, target: str) -> Path:
        """Get the reports directory for a target."""
        return self.target_dir(target) / REPORTS_DIR
    
    def tmp_dir(self, target: str) -> Path:
        """Get the tmp directory for a target."""
        return self.target_dir(target) / TMP_DIR
    
    def tasks_yaml_path(self, target: str) -> Path:
        """Get the tasks.yaml file path for a target."""
        return self.target_dir(target) / "tasks.yaml"
    
    def progress_json_path(self, target: str) -> Path:
        """Get the progress.json file path for a target."""
        return self.target_dir(target) / "progress.json"
    
    def run_db_path(self, target: str) -> Path:
        """Get the run database path for a target."""
        return self.target_dir(target) / "run.db"
    
    def lock_file_path(self, target: str) -> Path:
        """Get the lock file path for a target."""
        return self.target_dir(target) / ".lock"
    
    def stop_flag_path(self, target: str) -> Path:
        """Get the stop flag file path for a target."""
        return self.target_dir(target) / ".stop"
    
    def runner_log_path(self, target: str) -> Path:
        """Get the runner log file path for a target."""
        return self.logs_dir(target) / "runner.log"
    
    def task_log_path(self, target: str, task_number: int, task_name: str) -> Path:
        """Get the task log file path for a specific task."""
        return self.logs_dir(target) / "tareas" / f"{task_number:02d}_{task_name}.log"
    
    def ensure_target_structure(self, target: str):
        """Ensure target directory structure exists."""
        target_path = self.target_dir(target)
        
        # Create main directories
        target_path.mkdir(parents=True, exist_ok=True)
        self.logs_dir(target).mkdir(exist_ok=True)
        (self.logs_dir(target) / "tareas").mkdir(exist_ok=True)
        self.outputs_dir(target).mkdir(exist_ok=True)
        self.reports_dir(target).mkdir(exist_ok=True)
        self.tmp_dir(target).mkdir(exist_ok=True)
        
        # Create output subdirectories
        output_subdirs = ["recon", "web", "endpoints", "scans", "artifacts"]
        for subdir in output_subdirs:
            (self.outputs_dir(target) / subdir).mkdir(exist_ok=True)
    
    def is_telegram_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.BOT_TOKEN and self.CHAT_ID)


# Global configuration instance
config = Config()