"""
Simple runner without database - just runs tasks and logs to files.
"""

import subprocess
import time
import yaml
from datetime import datetime
from pathlib import Path

def run_simple_pipeline(target_dir: Path):
    """Run pipeline without any database - just execute tasks."""
    
    tasks_file = target_dir / "tasks.yaml"
    logs_dir = target_dir / "logs"
    outputs_dir = target_dir / "outputs"
    
    # Ensure directories exist
    logs_dir.mkdir(exist_ok=True)
    outputs_dir.mkdir(exist_ok=True)
    
    # Load tasks
    with open(tasks_file, 'r') as f:
        config = yaml.safe_load(f)
    
    tasks = config.get('pipeline', [])
    variables = config.get('vars', {})
    
    print(f"🚀 Starting simple run with {len(tasks)} tasks")
    
    completed_tasks = set()
    
    for task in tasks:
        task_name = task['name']
        
        # Check dependencies
        needs = task.get('needs', [])
        if not all(dep in completed_tasks for dep in needs):
            print(f"⏳ Skipping {task_name} - dependencies not met")
            continue
        
        if task.get('kind') == 'internal:summarize':
            print(f"✅ Skipping {task_name} - internal task")
            completed_tasks.add(task_name)
            continue
        
        print(f"🔄 Running {task_name}")
        
        # Replace variables in command
        cmd = task['cmd']
        for var, value in variables.items():
            cmd = cmd.replace(f"{{{var}}}", str(value))
        
        # Log file
        log_file = logs_dir / f"{task_name}.log"
        
        try:
            # Run command
            start_time = time.time()
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=task.get('timeout', 300)
            )
            
            duration = time.time() - start_time
            
            # Write log
            with open(log_file, 'w') as f:
                f.write(f"Task: {task_name}\n")
                f.write(f"Command: {cmd}\n")
                f.write(f"Start: {datetime.now()}\n")
                f.write(f"Duration: {duration:.2f}s\n")
                f.write(f"Return code: {result.returncode}\n")
                f.write(f"\n--- STDOUT ---\n{result.stdout}\n")
                f.write(f"\n--- STDERR ---\n{result.stderr}\n")
            
            if result.returncode == 0:
                print(f"✅ {task_name} completed successfully")
                completed_tasks.add(task_name)
            else:
                print(f"❌ {task_name} failed with code {result.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"⏰ {task_name} timed out")
            return False
        except Exception as e:
            print(f"💥 {task_name} failed with exception: {e}")
            return False
    
    print(f"🎉 Pipeline completed successfully! ({len(completed_tasks)} tasks)")
    return True

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python simple_runner.py <target_dir>")
        sys.exit(1)
    
    target_dir = Path(sys.argv[1])
    success = run_simple_pipeline(target_dir)
    sys.exit(0 if success else 1)