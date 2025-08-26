"""
Task runner for the bug bounty tool.
Handles YAML pipeline execution, dependency resolution, and concurrent task management.
"""

import asyncio
import subprocess
import signal
import psutil
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import os

from .config import config
from .db import Database, init_db
from .templating import materialize_env, render_task_command, validate_template_vars
from .utils import read_json, write_json, check_stop_flag, format_duration, console
from .constants import TaskStatus, RunStatus, EventLevel, TaskKind
from .notifier import TelegramNotifier


class Task:
    """Represents a single task in the pipeline."""
    
    def __init__(self, name: str, config_data: Dict[str, Any], task_number: int):
        self.name = name
        self.task_number = task_number
        self.description = config_data.get('desc', config_data.get('description', ''))
        self.cmd = config_data.get('cmd', '')
        self.kind = config_data.get('kind', TaskKind.SHELL.value)
        self.needs = config_data.get('needs', [])
        self.timeout = config_data.get('timeout')
        self.metadata = config_data.get('metadata', {})
        self.status = TaskStatus.PENDING
        self.start_time = None
        self.end_time = None
        self.return_code = None
        self.process = None
        self.task_id = None
    
    def is_ready(self, completed_tasks: Set[str]) -> bool:
        """Check if task dependencies are satisfied."""
        return all(dep in completed_tasks for dep in self.needs)
    
    def is_internal(self) -> bool:
        """Check if this is an internal task."""
        return self.kind.startswith('internal:')


class TaskRunner:
    """Main task runner class."""
    
    def __init__(self, target: str, notifier: Optional[TelegramNotifier] = None):
        self.target = target
        self.target_dir = config.target_dir(target)
        self.db = init_db(config.run_db_path(target))
        self.notifier = notifier
        self.run_id = None
        self.tasks = {}
        self.variables = {}
        self.concurrency = config.CONCURRENCY
        self.executor = None
        self.stop_event = threading.Event()
        self.logger = self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging for the runner."""
        import logging
        
        log_path = config.runner_log_path(self.target)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger = logging.getLogger(f"runner_{self.target}")
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # File handler
        handler = logging.FileHandler(log_path, encoding='utf-8')
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    def load_tasks(self, tasks_file: Optional[Path] = None) -> bool:
        """
        Load tasks from YAML file.
        
        Args:
            tasks_file: Path to tasks.yaml file (optional)
        
        Returns:
            True if tasks loaded successfully
        """
        if tasks_file is None:
            tasks_file = config.tasks_yaml_path(self.target)
        
        if not tasks_file.exists():
            self.logger.error(f"Tasks file not found: {tasks_file}")
            return False
        
        try:
            with open(tasks_file, 'r', encoding='utf-8') as f:
                tasks_config = yaml.safe_load(f)
            
            # Extract configuration
            self.concurrency = tasks_config.get('concurrency', config.CONCURRENCY)
            custom_vars = tasks_config.get('vars', {})
            env_vars = tasks_config.get('env', {})
            
            # Materialize environment variables
            self.variables = materialize_env(self.target, custom_vars)
            self.variables.update(env_vars)
            
            # Load tasks
            pipeline = tasks_config.get('pipeline', [])
            self.tasks = {}
            
            for i, task_config in enumerate(pipeline):
                task_name = task_config.get('name')
                if not task_name:
                    self.logger.error(f"Task {i} missing name")
                    return False
                
                task = Task(task_name, task_config, i + 1)
                self.tasks[task_name] = task
            
            self.logger.info(f"Loaded {len(self.tasks)} tasks from {tasks_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading tasks: {e}")
            return False
    
    def validate_pipeline(self) -> List[str]:
        """
        Validate the task pipeline for dependency issues.
        
        Returns:
            List of validation errors
        """
        errors = []
        task_names = set(self.tasks.keys())
        
        for task_name, task in self.tasks.items():
            # Check dependencies exist
            for dep in task.needs:
                if dep not in task_names:
                    errors.append(f"Task '{task_name}' depends on unknown task '{dep}'")
            
            # Check for circular dependencies (simple check)
            visited = set()
            
            def check_circular(name, path):
                if name in path:
                    return f"Circular dependency detected: {' -> '.join(path + [name])}"
                if name in visited:
                    return None
                
                visited.add(name)
                if name in self.tasks:
                    for dep in self.tasks[name].needs:
                        result = check_circular(dep, path + [name])
                        if result:
                            return result
                return None
            
            circular_error = check_circular(task_name, [])
            if circular_error:
                errors.append(circular_error)
            
            # Validate command templates
            if not task.is_internal():
                missing_vars = validate_template_vars(task.cmd, self.variables)
                if missing_vars:
                    errors.append(f"Task '{task_name}' uses undefined variables: {missing_vars}")
        
        return errors
    
    def run(self, resume: bool = False, task_filter: Optional[List[str]] = None) -> bool:
        """
        Run the task pipeline.
        
        Args:
            resume: Resume from previous run
            task_filter: Only run specific tasks
        
        Returns:
            True if run completed successfully
        """
        try:
            # Setup
            config.ensure_target_structure(self.target)
            
            if not self.load_tasks():
                return False
            
            validation_errors = self.validate_pipeline()
            if validation_errors:
                for error in validation_errors:
                    self.logger.error(f"Validation error: {error}")
                return False
            
            # Filter tasks if specified
            if task_filter:
                filtered_tasks = {name: task for name, task in self.tasks.items() 
                                if name in task_filter}
                if not filtered_tasks:
                    self.logger.error(f"No tasks found matching filter: {task_filter}")
                    return False
                self.tasks = filtered_tasks
            
            # Start run
            self.run_id = self.db.start_run(
                self.target, 
                len(self.tasks),
                {"concurrency": self.concurrency, "task_filter": task_filter}
            )
            
            self.logger.info(f"Starting run {self.run_id} for target {self.target}")
            self._update_progress()
            
            if self.notifier:
                self.notifier.send_text(
                    f"🚀 Started bug bounty run for {self.target}\n"
                    f"Tasks: {len(self.tasks)}\n"
                    f"Concurrency: {self.concurrency}"
                )
            
            # Execute pipeline
            success = self._execute_pipeline()
            
            # End run
            final_status = RunStatus.DONE if success else RunStatus.ERROR
            self.db.end_run(self.run_id, final_status)
            
            self.logger.info(f"Run {self.run_id} completed with status: {final_status.value}")
            self._update_progress()
            
            if self.notifier:
                status_emoji = "✅" if success else "❌"
                self.notifier.send_text(
                    f"{status_emoji} Bug bounty run completed for {self.target}\n"
                    f"Status: {final_status.value}\n"
                    f"Tasks completed: {sum(1 for t in self.tasks.values() if t.status == TaskStatus.DONE)}/{len(self.tasks)}"
                )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Run failed with exception: {e}")
            if self.run_id:
                self.db.end_run(self.run_id, RunStatus.ERROR, {"error": str(e)})
            return False
    
    def _execute_pipeline(self) -> bool:
        """Execute the task pipeline with dependency resolution."""
        completed_tasks = set()
        running_tasks = {}
        failed_tasks = set()
        
        self.executor = ThreadPoolExecutor(max_workers=self.concurrency)
        
        try:
            while True:
                # Check for stop signal
                if check_stop_flag(self.target_dir) or self.stop_event.is_set():
                    self.logger.info("Stop signal received, cancelling remaining tasks")
                    self._cancel_running_tasks(running_tasks)
                    break
                
                # Find ready tasks
                ready_tasks = []
                for task_name, task in self.tasks.items():
                    if (task.status == TaskStatus.PENDING and 
                        task.is_ready(completed_tasks) and
                        task_name not in running_tasks):
                        ready_tasks.append(task)
                
                # Start ready tasks (up to concurrency limit)
                available_slots = self.concurrency - len(running_tasks)
                for task in ready_tasks[:available_slots]:
                    future = self.executor.submit(self._execute_task, task)
                    running_tasks[task.name] = (task, future)
                    task.status = TaskStatus.RUNNING
                    self.logger.info(f"Started task: {task.name}")
                
                # Check completed tasks
                completed_futures = []
                for task_name, (task, future) in running_tasks.items():
                    if future.done():
                        try:
                            success = future.result()
                            if success:
                                task.status = TaskStatus.DONE
                                completed_tasks.add(task_name)
                                self.logger.info(f"Task completed successfully: {task_name}")
                            else:
                                task.status = TaskStatus.ERROR
                                failed_tasks.add(task_name)
                                self.logger.error(f"Task failed: {task_name}")
                        except Exception as e:
                            task.status = TaskStatus.ERROR
                            failed_tasks.add(task_name)
                            self.logger.error(f"Task {task_name} failed with exception: {e}")
                        
                        completed_futures.append(task_name)
                        self._update_progress()
                
                # Remove completed tasks
                for task_name in completed_futures:
                    del running_tasks[task_name]
                
                # Check if we're done
                if not running_tasks and not ready_tasks:
                    break
                
                # Sleep briefly
                time.sleep(0.1)
        
        finally:
            self.executor.shutdown(wait=True)
        
        # Check final status
        total_tasks = len(self.tasks)
        completed_count = len(completed_tasks)
        failed_count = len(failed_tasks)
        
        self.logger.info(f"Pipeline completed: {completed_count}/{total_tasks} successful, {failed_count} failed")
        
        return failed_count == 0
    
    def _execute_task(self, task: Task) -> bool:
        """
        Execute a single task.
        
        Args:
            task: Task to execute
        
        Returns:
            True if task completed successfully
        """
        task.start_time = datetime.now(timezone.utc)
        
        # Start task in database
        task.task_id = self.db.start_task(
            self.run_id,
            task.name,
            task.description,
            task.cmd,
            task.timeout,
            task.metadata
        )
        
        try:
            if task.is_internal():
                return self._execute_internal_task(task)
            else:
                return self._execute_shell_task(task)
        
        except Exception as e:
            self.logger.error(f"Task {task.name} failed with exception: {e}")
            self.db.end_task(task.task_id, TaskStatus.ERROR, metadata={"error": str(e)})
            return False
        
        finally:
            task.end_time = datetime.now(timezone.utc)
    
    def _execute_shell_task(self, task: Task) -> bool:
        """Execute a shell command task."""
        # Render command
        cmd = render_task_command(task.cmd, self.variables)
        
        # Setup log files
        log_dir = config.logs_dir(self.target) / "tareas"
        log_dir.mkdir(exist_ok=True)
        
        stdout_path = log_dir / f"{task.task_number:02d}_{task.name}_stdout.log"
        stderr_path = log_dir / f"{task.task_number:02d}_{task.name}_stderr.log"
        
        self.logger.info(f"Executing task {task.name}: {cmd}")
        
        try:
            # Start process
            with open(stdout_path, 'w', encoding='utf-8') as stdout_f, \
                 open(stderr_path, 'w', encoding='utf-8') as stderr_f:
                
                # Determine shell based on OS
                if os.name == 'nt':  # Windows
                    process = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=stdout_f,
                        stderr=stderr_f,
                        env=self.variables,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    )
                else:  # Unix-like
                    process = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=stdout_f,
                        stderr=stderr_f,
                        env=self.variables,
                        preexec_fn=os.setsid
                    )
                
                task.process = process
                
                # Wait for completion with timeout
                timeout = task.timeout or config.DEFAULT_TIMEOUT
                try:
                    return_code = process.wait(timeout=timeout)
                    task.return_code = return_code
                    
                    # Update database
                    status = TaskStatus.DONE if return_code == 0 else TaskStatus.ERROR
                    self.db.end_task(
                        task.task_id,
                        status,
                        return_code,
                        str(stdout_path),
                        str(stderr_path)
                    )
                    
                    return return_code == 0
                
                except subprocess.TimeoutExpired:
                    self.logger.warning(f"Task {task.name} timed out after {timeout} seconds")
                    self._kill_process_tree(process)
                    self.db.end_task(task.task_id, TaskStatus.ERROR, -1, str(stdout_path), str(stderr_path))
                    return False
        
        except Exception as e:
            self.logger.error(f"Error executing task {task.name}: {e}")
            self.db.end_task(task.task_id, TaskStatus.ERROR, metadata={"error": str(e)})
            return False
    
    def _execute_internal_task(self, task: Task) -> bool:
        """Execute an internal task."""
        self.logger.info(f"Executing internal task {task.name}: {task.kind}")
        
        try:
            if task.kind == TaskKind.INTERNAL_SUMMARIZE.value:
                from .summarizer import Summarizer
                summarizer = Summarizer(self.target)
                summarizer.generate_summary()
                
            elif task.kind == TaskKind.INTERNAL_NOTIFY.value:
                if self.notifier:
                    self.notifier.send_text(f"📊 Task notification from {self.target}")
            
            self.db.end_task(task.task_id, TaskStatus.DONE)
            return True
        
        except Exception as e:
            self.logger.error(f"Internal task {task.name} failed: {e}")
            self.db.end_task(task.task_id, TaskStatus.ERROR, metadata={"error": str(e)})
            return False
    
    def _kill_process_tree(self, process):
        """Kill process and all its children."""
        try:
            if os.name == 'nt':  # Windows
                process.terminate()
                time.sleep(config.HARD_KILL_GRACE)
                if process.poll() is None:
                    process.kill()
            else:  # Unix-like
                # Kill process group
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                time.sleep(config.HARD_KILL_GRACE)
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        except (ProcessLookupError, PermissionError):
            pass
    
    def _cancel_running_tasks(self, running_tasks):
        """Cancel all running tasks."""
        for task_name, (task, future) in running_tasks.items():
            future.cancel()
            if task.process:
                self._kill_process_tree(task.process)
            task.status = TaskStatus.CANCELLED
            if task.task_id:
                self.db.end_task(task.task_id, TaskStatus.CANCELLED)
    
    def _update_progress(self):
        """Update progress.json file."""
        if not self.run_id:
            return
        
        run_info = self.db.get_run(self.run_id)
        if not run_info:
            return
        
        completed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.DONE)
        total = len(self.tasks)
        
        # Find current running task
        current_task = None
        for task in self.tasks.values():
            if task.status == TaskStatus.RUNNING:
                current_task = task.name
                break
        
        # Calculate ETA
        eta_seconds = None
        if run_info['start_ts'] and completed > 0:
            start_time = datetime.fromisoformat(run_info['start_ts'].replace('Z', '+00:00'))
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed > 0:
                rate = completed / elapsed
                remaining = total - completed
                eta_seconds = int(remaining / rate) if rate > 0 and remaining > 0 else None
        
        progress_data = {
            "target": self.target,
            "run_id": self.run_id,
            "started": run_info['start_ts'],
            "status": run_info['status'],
            "total": total,
            "done": completed,
            "current_task": current_task,
            "eta_seconds": eta_seconds,
            "last_update": datetime.now(timezone.utc).isoformat()
        }
        
        write_json(config.progress_json_path(self.target), progress_data)
    
    def stop(self):
        """Signal the runner to stop."""
        self.stop_event.set()
        # Also create stop flag file
        from .utils import create_stop_flag
        create_stop_flag(self.target_dir)