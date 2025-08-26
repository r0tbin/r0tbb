"""
Database operations for the bug bounty tool.
Handles SQLite database schema, connections, and operations.
"""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager

from .constants import TaskStatus, RunStatus, EventLevel


class Database:
    """SQLite database manager for runs, tasks, and events."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database tables if they don't exist."""
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target TEXT NOT NULL,
                    start_ts TEXT NOT NULL,
                    end_ts TEXT,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    total_tasks INTEGER DEFAULT 0,
                    completed_tasks INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}'
                );
                
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    start_ts TEXT,
                    end_ts TEXT,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    return_code INTEGER,
                    stdout_path TEXT,
                    stderr_path TEXT,
                    cmd TEXT,
                    timeout INTEGER,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (run_id) REFERENCES runs (id)
                );
                
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    task_name TEXT,
                    ts TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    FOREIGN KEY (run_id) REFERENCES runs (id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_runs_target ON runs(target);
                CREATE INDEX IF NOT EXISTS idx_tasks_run_id ON tasks(run_id);
                CREATE INDEX IF NOT EXISTS idx_events_run_id ON events(run_id);
                CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
            """)
    
    @contextmanager
    def get_connection(self):
        """Get a database connection with automatic commit/rollback."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def start_run(self, target: str, total_tasks: int = 0, metadata: Dict[str, Any] = None) -> int:
        """Start a new run and return the run ID."""
        now = datetime.now(timezone.utc).isoformat()
        metadata = metadata or {}
        
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO runs (target, start_ts, status, total_tasks, metadata) VALUES (?, ?, ?, ?, ?)",
                (target, now, RunStatus.RUNNING.value, total_tasks, json.dumps(metadata))
            )
            run_id = cursor.lastrowid
            
            # Log run start event
            self.log_event(run_id, None, EventLevel.INFO, f"Run started for target: {target}")
            
            return run_id
    
    def end_run(self, run_id: int, status: RunStatus, metadata: Dict[str, Any] = None):
        """End a run with the given status."""
        now = datetime.now(timezone.utc).isoformat()
        
        with self.get_connection() as conn:
            # Update run
            if metadata:
                conn.execute(
                    "UPDATE runs SET end_ts = ?, status = ?, metadata = ? WHERE id = ?",
                    (now, status.value, json.dumps(metadata), run_id)
                )
            else:
                conn.execute(
                    "UPDATE runs SET end_ts = ?, status = ? WHERE id = ?",
                    (now, status.value, run_id)
                )
            
            # Log run end event
            self.log_event(run_id, None, EventLevel.INFO, f"Run ended with status: {status.value}")
    
    def start_task(self, run_id: int, name: str, description: str = None, 
                   cmd: str = None, timeout: int = None, metadata: Dict[str, Any] = None) -> int:
        """Start a new task and return the task ID."""
        now = datetime.now(timezone.utc).isoformat()
        metadata = metadata or {}
        
        with self.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO tasks 
                   (run_id, name, description, start_ts, status, cmd, timeout, metadata) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, name, description, now, TaskStatus.RUNNING.value, 
                 cmd, timeout, json.dumps(metadata))
            )
            task_id = cursor.lastrowid
            
            # Log task start event
            self.log_event(run_id, name, EventLevel.INFO, f"Task started: {name}")
            
            return task_id
    
    def end_task(self, task_id: int, status: TaskStatus, return_code: int = None,
                 stdout_path: str = None, stderr_path: str = None, 
                 metadata: Dict[str, Any] = None):
        """End a task with the given status and results."""
        now = datetime.now(timezone.utc).isoformat()
        
        with self.get_connection() as conn:
            # Get task info for logging
            task_row = conn.execute("SELECT run_id, name FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not task_row:
                raise ValueError(f"Task {task_id} not found")
            
            run_id, task_name = task_row["run_id"], task_row["name"]
            
            # Update task
            update_fields = ["end_ts = ?", "status = ?"]
            values = [now, status.value]
            
            if return_code is not None:
                update_fields.append("return_code = ?")
                values.append(return_code)
            
            if stdout_path:
                update_fields.append("stdout_path = ?")
                values.append(stdout_path)
            
            if stderr_path:
                update_fields.append("stderr_path = ?")
                values.append(stderr_path)
            
            if metadata:
                update_fields.append("metadata = ?")
                values.append(json.dumps(metadata))
            
            values.append(task_id)
            
            conn.execute(
                f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?",
                values
            )
            
            # Update run progress
            if status == TaskStatus.DONE:
                conn.execute(
                    "UPDATE runs SET completed_tasks = completed_tasks + 1 WHERE id = ?",
                    (run_id,)
                )
            
            # Log task end event
            level = EventLevel.INFO if status == TaskStatus.DONE else EventLevel.ERROR
            self.log_event(run_id, task_name, level, 
                          f"Task ended: {task_name} with status {status.value}")
    
    def log_event(self, run_id: int, task_name: str = None, level: EventLevel = EventLevel.INFO,
                  message: str = "", metadata: Dict[str, Any] = None):
        """Log an event for the run."""
        now = datetime.now(timezone.utc).isoformat()
        metadata = metadata or {}
        
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO events (run_id, task_name, ts, level, message, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, task_name, now, level.value, message, json.dumps(metadata))
            )
    
    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Get run information by ID."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            return dict(row) if row else None
    
    def get_latest_run(self, target: str) -> Optional[Dict[str, Any]]:
        """Get the latest run for a target."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE target = ? ORDER BY start_ts DESC LIMIT 1",
                (target,)
            ).fetchone()
            return dict(row) if row else None
    
    def get_run_tasks(self, run_id: int) -> List[Dict[str, Any]]:
        """Get all tasks for a run."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE run_id = ? ORDER BY id",
                (run_id,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def get_run_events(self, run_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent events for a run."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE run_id = ? ORDER BY ts DESC LIMIT ?",
                (run_id, limit)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def get_task_by_name(self, run_id: int, task_name: str) -> Optional[Dict[str, Any]]:
        """Get task by name for a specific run."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE run_id = ? AND name = ?",
                (run_id, task_name)
            ).fetchone()
            return dict(row) if row else None


# Helper functions for common operations
def init_db(db_path: Path) -> Database:
    """Initialize and return a database instance."""
    return Database(db_path)


def start_run(db: Database, target: str, total_tasks: int = 0, metadata: Dict[str, Any] = None) -> int:
    """Start a new run."""
    return db.start_run(target, total_tasks, metadata)


def end_run(db: Database, run_id: int, status: RunStatus, metadata: Dict[str, Any] = None):
    """End a run."""
    db.end_run(run_id, status, metadata)