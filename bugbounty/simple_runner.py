"""
Simple runner that works WITHOUT database - just executes tasks and logs to files.
No SQLite, no locks, no bullshit. Just works.
"""

import subprocess
import threading
import time
import yaml
import json
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import Config
from .constants import *
from .templating import render, materialize_env
from .utils import read_json, write_json, check_stop_flag, format_duration, console
from .notifier import TelegramNotifier


class SimpleTaskRunner:
    """Simple task runner without database dependencies."""
    
    def __init__(self, target: str, target_dir: Path):
        self.target = target
        self.target_dir = target_dir
        self.tasks_file = target_dir / TASKS_FILE
        self.logs_dir = target_dir / LOGS_DIR_NAME
        self.outputs_dir = target_dir / OUTPUTS_DIR_NAME
        self.reports_dir = target_dir / REPORTS_DIR_NAME
        self.tmp_dir = target_dir / TMP_DIR_NAME
        self.progress_file = target_dir / PROGRESS_FILE
        self.stop_flag_file = target_dir / STOP_FLAG_FILE
        
        # Create directories
        for directory in [self.logs_dir, self.outputs_dir, self.reports_dir, self.tmp_dir]:
            directory.mkdir(exist_ok=True)
        
        # Task logs directory
        self.task_logs_dir = self.logs_dir / "tareas"
        self.task_logs_dir.mkdir(exist_ok=True)
        
        # Simple logging
        self.runner_log = self.logs_dir / "runner.log"
        
        # Execution state
        self.completed_tasks: Set[str] = set()
        self.failed_tasks: Set[str] = set()
        self.running_tasks: Set[str] = set()
        self.start_time = None
        self.executor = None
        self.stop_event = threading.Event()
        
        # Notifier
        self.notifier = None
        if Config.BOT_TOKEN and Config.CHAT_ID:
            try:
                self.notifier = TelegramNotifier()
            except Exception as e:
                self.log(f"Failed to initialize notifier: {e}")
    
    def log(self, message: str, level: str = "INFO"):
        """Log message to runner log file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp} [{level}] {message}\n"
        
        # Write to file
        with open(self.runner_log, "a", encoding="utf-8") as f:
            f.write(log_entry)
        
        # Print to console
        if level == "ERROR":
            console.print(f"❌ {message}", style="red")
        elif level == "WARNING":
            console.print(f"⚠️ {message}", style="yellow")
        else:
            console.print(f"ℹ️ {message}", style="blue")
    
    def load_tasks(self) -> Dict[str, Any]:
        """Load tasks from YAML file."""
        try:
            with open(self.tasks_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            self.log(f"Loaded {len(config.get('pipeline', []))} tasks from {self.tasks_file}")
            return config
        except Exception as e:
            self.log(f"Error loading tasks: {e}", "ERROR")
            raise
    
    def update_progress(self, current_task: str = "", total_tasks: int = 0):
        """Update progress JSON file."""
        progress_data = {
            "target": self.target,
            "status": "running" if not self.stop_event.is_set() else "stopped",
            "total": total_tasks,
            "completed": len(self.completed_tasks),
            "failed": len(self.failed_tasks),
            "current_task": current_task,
            "last_update": datetime.now().isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "elapsed_seconds": int((datetime.now() - self.start_time).total_seconds()) if self.start_time else 0
        }
        
        try:
            write_json(self.progress_file, progress_data)
        except Exception as e:
            self.log(f"Failed to update progress: {e}", "ERROR")
    
    def execute_task(self, task: Dict[str, Any], variables: Dict[str, str]) -> bool:
        """Execute a single task."""
        task_name = task['name']
        
        # Check if task should be skipped
        if task_name in self.completed_tasks:
            return True
        
        if task_name in self.failed_tasks:
            return False
        
        # Check dependencies
        needs = task.get('needs', [])
        for dep in needs:
            if dep not in self.completed_tasks:
                self.log(f"Task {task_name} waiting for dependency: {dep}", "WARNING")
                return False
        
        # Add to running tasks
        self.running_tasks.add(task_name)
        
        try:
            # Handle internal tasks
            if task.get('kind', '').startswith('internal:'):
                return self.execute_internal_task(task, variables)
            
            # Execute shell command
            return self.execute_shell_task(task, variables)
        
        finally:
            self.running_tasks.discard(task_name)
    
    def execute_shell_task(self, task: Dict[str, Any], variables: Dict[str, str]) -> bool:
        """Execute a shell command task."""
        task_name = task['name']
        task_desc = task.get('desc', task_name)
        cmd = task['cmd']
        timeout = task.get('timeout', Config.DEFAULT_TIMEOUT)
        
        # Render command with variables
        rendered_cmd = render(cmd, variables)
        
        self.log(f"Starting task: {task_name} - {task_desc}")
        self.log(f"Command: {rendered_cmd}")
        
        # Create task log file
        task_log_file = self.task_logs_dir / f"{task_name}.log"
        
        start_time = time.time()
        
        try:
            # Execute command
            with open(task_log_file, 'w', encoding='utf-8') as log_file:
                log_file.write(f"Task: {task_name}\n")
                log_file.write(f"Command: {rendered_cmd}\n")
                log_file.write(f"Started: {datetime.now()}\n")
                log_file.write("-" * 50 + "\n")
                
                process = subprocess.Popen(
                    rendered_cmd,
                    shell=True,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    cwd=self.target_dir,
                    text=True
                )
                
                # Wait for completion with timeout
                try:
                    process.wait(timeout=timeout)
                    exit_code = process.returncode
                except subprocess.TimeoutExpired:
                    process.kill()
                    exit_code = -1
                    log_file.write(f"\n[TIMEOUT] Task killed after {timeout}s\n")
            
            duration = time.time() - start_time
            
            if exit_code == 0:
                self.log(f"✅ Task {task_name} completed successfully in {format_duration(duration)}")
                self.completed_tasks.add(task_name)
                return True
            else:
                self.log(f"❌ Task {task_name} failed with exit code {exit_code} after {format_duration(duration)}", "ERROR")
                self.failed_tasks.add(task_name)
                return False
        
        except Exception as e:
            duration = time.time() - start_time
            self.log(f"❌ Task {task_name} failed with exception: {e} after {format_duration(duration)}", "ERROR")
            self.failed_tasks.add(task_name)
            return False
    
    def execute_internal_task(self, task: Dict[str, Any], variables: Dict[str, str]) -> bool:
        """Execute internal task (like summarize)."""
        task_name = task['name']
        kind = task.get('kind', '')
        
        self.log(f"Executing internal task: {task_name} ({kind})")
        
        if kind == "internal:summarize":
            try:
                from .summarizer import Summarizer
                summarizer = Summarizer(self.target_dir)
                summarizer.generate_summary()
                self.log(f"✅ Summary generated successfully")
                self.completed_tasks.add(task_name)
                return True
            except Exception as e:
                self.log(f"❌ Summary generation failed: {e}", "ERROR")
                self.failed_tasks.add(task_name)
                return False
        else:
            self.log(f"❌ Unknown internal task kind: {kind}", "ERROR")
            self.failed_tasks.add(task_name)
            return False
    
    def run(self) -> bool:
        """Run the complete pipeline."""
        try:
            # Load configuration
            config = self.load_tasks()
            tasks = config.get('pipeline', [])
            if not tasks:
                self.log("No tasks found in pipeline", "ERROR")
                return False
            
            # Setup variables
            base_vars = {
                'TARGET': self.target,
                'ROOT': str(self.target_dir),
                'OUT': str(self.outputs_dir),
                'LOGS': str(self.logs_dir),
                'REPORTS': str(self.reports_dir),
                'TMP': str(self.tmp_dir)
            }
            config_vars = config.get('vars', {})
            config_env = config.get('env', {})
            variables = materialize_env(base_vars, config_vars, config_env)
            
            self.start_time = datetime.now()
            
            # Send start notification
            if self.notifier:
                try:
                    self.notifier.send_text(f"🚀 Started bug bounty run for {self.target}\n📊 {len(tasks)} tasks to execute")
                except Exception as e:
                    self.log(f"Failed to send start notification: {e}", "WARNING")
            
            # Execute tasks in a simple loop
            max_attempts = len(tasks) * 3  # Prevent infinite loops
            attempt = 0
            
            while len(self.completed_tasks) + len(self.failed_tasks) < len(tasks) and attempt < max_attempts:
                attempt += 1
                
                # Check stop flag
                if check_stop_flag(self.stop_flag_file) or self.stop_event.is_set():
                    self.log("Stop flag detected, halting execution", "WARNING")
                    break
                
                progress_made = False
                
                for task in tasks:
                    task_name = task['name']
                    
                    # Skip if already processed
                    if task_name in self.completed_tasks or task_name in self.failed_tasks:
                        continue
                    
                    # Check dependencies
                    needs = task.get('needs', [])
                    deps_ready = all(dep in self.completed_tasks for dep in needs)
                    
                    if deps_ready:
                        self.update_progress(task_name, len(tasks))
                        success = self.execute_task(task, variables)
                        progress_made = True
                        
                        if not success:
                            self.log(f"Task {task_name} failed, continuing with other tasks", "WARNING")
                
                if not progress_made:
                    # Check if we have unresolvable dependencies
                    remaining_tasks = [t for t in tasks if t['name'] not in self.completed_tasks and t['name'] not in self.failed_tasks]
                    if remaining_tasks:
                        self.log("No progress made, checking for dependency issues", "WARNING")
                        for task in remaining_tasks:
                            needs = task.get('needs', [])
                            missing_deps = [dep for dep in needs if dep not in self.completed_tasks]
                            if missing_deps:
                                self.log(f"Task {task['name']} blocked by failed dependencies: {missing_deps}", "ERROR")
                                self.failed_tasks.add(task['name'])
                    break
            
            # Final status
            total_tasks = len(tasks)
            completed = len(self.completed_tasks)
            failed = len(self.failed_tasks)
            
            duration = time.time() - self.start_time.timestamp() if self.start_time else 0
            
            self.update_progress("", total_tasks)
            
            if failed == 0 and completed == total_tasks:
                self.log(f"✅ Pipeline completed successfully! {completed}/{total_tasks} tasks completed in {format_duration(duration)}")
                success = True
            else:
                self.log(f"❌ Pipeline completed with issues. {completed}/{total_tasks} completed, {failed} failed in {format_duration(duration)}", "ERROR")
                success = False
            
            # Send completion notification
            if self.notifier:
                try:
                    status_msg = "✅ SUCCESS" if success else "❌ FAILED"
                    self.notifier.send_text(f"{status_msg} Bug bounty run for {self.target}\n📊 {completed}/{total_tasks} completed, {failed} failed\n⏱️ Duration: {format_duration(duration)}")
                except Exception as e:
                    self.log(f"Failed to send completion notification: {e}", "WARNING")
            
            return success
        
        except Exception as e:
            self.log(f"Pipeline failed with exception: {e}", "ERROR")
            return False


def run_simple_pipeline(target_dir: Path, target: str) -> bool:
    """Simple entry point to run pipeline without database."""
    runner = SimpleTaskRunner(target, target_dir)
    return runner.run()