"""
File-based database replacement to avoid SQLite lock issues.
Uses JSON files instead of SQLite for state management.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from threading import Lock

class FileBasedDB:
    """File-based database using JSON files instead of SQLite."""
    
    def __init__(self, target_dir: Path):
        self.target_dir = target_dir
        self.runs_file = target_dir / "runs.json"
        self.tasks_file = target_dir / "tasks.json"
        self.events_file = target_dir / "events.json"
        self.lock = Lock()
        
        # Ensure files exist
        for file_path in [self.runs_file, self.tasks_file, self.events_file]:
            if not file_path.exists():
                self._write_json(file_path, [])
    
    def _write_json(self, file_path: Path, data: Any):
        """Write data to JSON file with atomic operation."""
        temp_file = file_path.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        temp_file.replace(file_path)
    
    def _read_json(self, file_path: Path) -> Any:
        """Read data from JSON file."""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def start_run(self, target: str, total_tasks: int = 0, metadata: Dict[str, Any] = None) -> int:
        """Start a new run and return the run ID."""
        with self.lock:
            runs = self._read_json(self.runs_file)
            run_id = len(runs) + 1
            
            new_run = {
                "id": run_id,
                "target": target,
                "start_ts": datetime.now(timezone.utc).isoformat(),
                "end_ts": None,
                "status": "RUNNING",
                "total_tasks": total_tasks,
                "completed_tasks": 0,
                "metadata": metadata or {}
            }
            
            runs.append(new_run)
            self._write_json(self.runs_file, runs)
            return run_id
    
    def end_run(self, run_id: int, status: str, metadata: Dict[str, Any] = None):
        """End a run."""
        with self.lock:
            runs = self._read_json(self.runs_file)
            for run in runs:
                if run["id"] == run_id:
                    run["end_ts"] = datetime.now(timezone.utc).isoformat()
                    run["status"] = status
                    if metadata:
                        run["metadata"].update(metadata)
                    break
            self._write_json(self.runs_file, runs)
    
    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Get run by ID."""
        runs = self._read_json(self.runs_file)
        for run in runs:
            if run["id"] == run_id:
                return run
        return None
    
    def start_task(self, run_id: int, name: str, description: str = None, cmd: str = None, timeout: int = None) -> int:
        """Start a task and return task ID."""
        with self.lock:
            tasks = self._read_json(self.tasks_file)
            task_id = len(tasks) + 1
            
            new_task = {
                "id": task_id,
                "run_id": run_id,
                "name": name,
                "description": description,
                "start_ts": datetime.now(timezone.utc).isoformat(),
                "end_ts": None,
                "status": "RUNNING",
                "return_code": None,
                "stdout_path": None,
                "stderr_path": None,
                "cmd": cmd,
                "timeout": timeout,
                "metadata": {}
            }
            
            tasks.append(new_task)
            self._write_json(self.tasks_file, tasks)
            return task_id
    
    def end_task(self, task_id: int, status: str, return_code: int = None, stdout_path: str = None, stderr_path: str = None, metadata: Dict[str, Any] = None):
        """End a task."""
        with self.lock:
            tasks = self._read_json(self.tasks_file)
            for task in tasks:
                if task["id"] == task_id:
                    task["end_ts"] = datetime.now(timezone.utc).isoformat()
                    task["status"] = status
                    if return_code is not None:
                        task["return_code"] = return_code
                    if stdout_path:
                        task["stdout_path"] = stdout_path
                    if stderr_path:
                        task["stderr_path"] = stderr_path
                    if metadata:
                        task["metadata"].update(metadata)
                    break
            self._write_json(self.tasks_file, tasks)
    
    def log_event(self, run_id: int, task_name: str = None, level: str = "INFO", message: str = "", metadata: Dict[str, Any] = None):
        """Log an event."""
        with self.lock:
            events = self._read_json(self.events_file)
            
            new_event = {
                "id": len(events) + 1,
                "run_id": run_id,
                "task_id": None,
                "task_name": task_name,
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "message": message,
                "metadata": metadata or {}
            }
            
            events.append(new_event)
            # Keep only last 1000 events to avoid huge files
            if len(events) > 1000:
                events = events[-1000:]
            
            self._write_json(self.events_file, events)