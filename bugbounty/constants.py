"""
Constants and enums for the bug bounty tool.
"""

from enum import Enum


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "PENDING"
    RUNNING = "RUNNING" 
    DONE = "DONE"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class RunStatus(Enum):
    """Run execution status."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class EventLevel(Enum):
    """Event logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class TaskKind(Enum):
    """Task execution types."""
    SHELL = "shell"
    INTERNAL_SUMMARIZE = "internal:summarize"
    INTERNAL_NOTIFY = "internal:notify"


# Default configuration values
DEFAULT_CONCURRENCY = 2
DEFAULT_TIMEOUT = 3600  # 1 hour
DEFAULT_HARD_KILL_GRACE = 10  # seconds

# File and directory names
TASKS_YAML = "tasks.yaml"
PROGRESS_JSON = "progress.json"
RUN_DB = "run.db"
LOGS_DIR = "logs"
OUTPUTS_DIR = "outputs"
REPORTS_DIR = "reports"
TMP_DIR = "tmp"

# Log file names
RUNNER_LOG = "runner.log"
TASKS_LOG_DIR = "tareas"

# Report file names
SUMMARY_MD = "summary.md"
SUMMARY_JSON = "summary.json"
RESULTS_ZIP = "results.zip"

# Lock and flag files
LOCK_FILE = ".lock"
STOP_FLAG = ".stop"

# Template variables
TEMPLATE_VARS = {
    "TARGET": "{TARGET}",
    "ROOT": "{ROOT}",
    "OUT": "{OUT}",
    "LOGS": "{LOGS}",
    "OUTPUTS": "{OUTPUTS}",
    "REPORTS": "{REPORTS}",
    "TMP": "{TMP}"
}