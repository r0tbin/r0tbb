"""
Command Line Interface for the bug bounty tool.
Provides commands for initialization, execution, monitoring, and management.
"""

import typer
import shutil
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import sys
import time

from .config import config
from .summarizer import Summarizer
from .telegram_bot import BugBountyBot
from .notifier import get_notifier, create_notifier
from .utils import (
    read_json, print_status_table, print_panel, 
    format_timestamp, format_duration, create_zip_archive,
    file_lock, check_stop_flag, remove_stop_flag
)
from .constants import TASKS_YAML

app = typer.Typer(
    name="bugbounty",
    help="Bug Bounty Automation Tool by r0tbin",
    no_args_is_help=True
)

console = Console()


@app.command()
def init(
    target: str = typer.Argument(..., help="Target domain (e.g., example.com)"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing target directory")
):
    """
    Initialize a new target with directory structure and sample configuration.
    """
    console.print(f"🎯 Initializing target: [bold cyan]{target}[/bold cyan]")
    
    target_dir = config.target_dir(target)
    
    # Check if target already exists
    if target_dir.exists() and not force:
        console.print(f"[red]❌ Target directory already exists: {target_dir}[/red]")
        console.print("Use --force to overwrite")
        raise typer.Exit(1)
    
    try:
        # Create target structure
        config.ensure_target_structure(target)
        console.print(f"✅ Created directory structure in [cyan]{target_dir}[/cyan]")
        
        # Copy sample tasks.yaml
        tasks_file = config.tasks_yaml_path(target)
        sample_tasks = config.ROOT_DIR / "templates" / "tasks.sample.yaml"
        
        if sample_tasks.exists():
            shutil.copy2(sample_tasks, tasks_file)
            console.print(f"✅ Copied sample tasks configuration")
        else:
            # Create basic tasks.yaml
            basic_tasks = {
                'version': 1,
                'concurrency': 2,
                'vars': {
                    'TARGET': target,
                    'ROOT': '{ROOT}',
                    'OUT': '{OUT}'
                },
                'pipeline': [
                    {
                        'name': 'example_task',
                        'desc': 'Example task - replace with your tools',
                        'cmd': 'echo "Target: {TARGET}" > {OUT}/outputs/example.txt',
                        'timeout': 300
                    }
                ]
            }
            
            import yaml
            with open(tasks_file, 'w', encoding='utf-8') as f:
                yaml.dump(basic_tasks, f, default_flow_style=False, indent=2)
            
            console.print(f"✅ Created basic tasks configuration")
        
        # Create basic directory structure (no database needed)
        console.print(f"✅ Initialized database")
        
        console.print(f"\n🚀 Target [bold green]{target}[/bold green] initialized successfully!")
        console.print(f"📝 Edit [cyan]{tasks_file}[/cyan] to configure your pipeline")
        console.print(f"🏃 Run with: [bold]bb run {target}[/bold]")
        
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize target: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def run(
    target: str = typer.Argument(..., help="Target to run"),
    tasks: Optional[str] = typer.Option(None, "--tasks", "-t", help="Comma-separated list of specific tasks to run"),
    resume: bool = typer.Option(False, "--resume", "-r", help="Resume from previous run"),
    no_telegram: bool = typer.Option(False, "--no-telegram", help="Disable Telegram notifications"),
    concurrency: Optional[int] = typer.Option(None, "--concurrency", "-c", help="Override concurrency setting")
):
    """
    Run the bug bounty pipeline for a target.
    """
    console.print(f"🚀 Starting bug bounty run for: [bold cyan]{target}[/bold cyan]")
    
    target_dir = config.target_dir(target)
    
    if not target_dir.exists():
        console.print(f"[red]❌ Target not found: {target}[/red]")
        console.print(f"Initialize with: [bold]bb init {target}[/bold]")
        raise typer.Exit(1)
    
    # Check for lock
    lock_file = config.lock_file_path(target)
    
    try:
        with file_lock(lock_file, timeout=5):
            # Remove stop flag if exists
            remove_stop_flag(target_dir)
            
            # Parse task filter
            task_filter = None
            if tasks:
                task_filter = [t.strip() for t in tasks.split(',')]
                console.print(f"📋 Running specific tasks: {task_filter}")
            
            # Setup notifier
            notifier = None
            if not no_telegram and config.is_telegram_configured():
                notifier = get_notifier()
                if notifier and not notifier.test_connection():
                    console.print("[yellow]⚠️  Telegram connection failed, continuing without notifications[/yellow]")
                    notifier = None
            
            # Use improved runner with optional database
            from .runner import TaskRunner
            
            # Create runner without database to avoid SQLite lock issues
            runner = TaskRunner(target, notifier, use_database=False)
            
            if concurrency:
                runner.concurrency = concurrency
                console.print(f"🔧 Using concurrency: {concurrency}")
            
            # Run pipeline
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Running pipeline...", total=None)
                
                success = runner.run(resume=resume, task_filter=task_filter)
                
                progress.update(task, description="Pipeline completed")
            
            if success:
                console.print(f"[green]✅ Pipeline completed successfully for {target}[/green]")
                
                # Generate summary if not already done
                try:
                    summarizer = Summarizer(target)
                    summarizer.generate_summary()
                    console.print("📊 Analysis summary generated")
                except Exception as e:
                    console.print(f"[yellow]⚠️  Summary generation failed: {e}[/yellow]")
                
            else:
                console.print(f"[red]❌ Pipeline failed for {target}[/red]")
                raise typer.Exit(1)
    
    except Exception as e:
        console.print(f"[red]❌ Run failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def status(
    target: str = typer.Argument(..., help="Target to check"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed task status")
):
    """
    Show current status and progress for a target.
    """
    target_dir = config.target_dir(target)
    
    if not target_dir.exists():
        console.print(f"[red]❌ Target not found: {target}[/red]")
        raise typer.Exit(1)
    
    try:
        # Read progress data
        progress_data = read_json(config.progress_json_path(target))
        
        if not progress_data:
            console.print(f"[yellow]📊 No active run for {target}[/yellow]")
            return
        
        # Main status panel
        status_text = progress_data.get('status', 'UNKNOWN')
        status_emoji = {
            'PENDING': '⏳',
            'RUNNING': '🔄',
            'DONE': '✅',
            'ERROR': '❌',
            'CANCELLED': '🛑'
        }.get(status_text, '❓')
        
        total = progress_data.get('total', 0)
        done = progress_data.get('done', 0)
        
        status_content = f"Status: {status_emoji} {status_text}\n"
        
        if total > 0:
            percentage = (done / total) * 100
            progress_bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
            status_content += f"Progress: [{progress_bar}] {percentage:.1f}%\n"
            status_content += f"Tasks: {done}/{total}\n"
        
        current_task = progress_data.get('current_task')
        if current_task:
            status_content += f"Current: {current_task}\n"
        
        eta_seconds = progress_data.get('eta_seconds')
        if eta_seconds:
            eta_str = format_duration(eta_seconds)
            status_content += f"ETA: {eta_str}\n"
        
        started = progress_data.get('started')
        if started:
            status_content += f"Started: {format_timestamp(started)}\n"
        
        print_panel(status_content, title=f"🎯 {target} Status", style="blue")
        
        # Detailed task status (simple log-based)
        if detailed:
            try:
                task_logs_dir = target_dir / "logs" / "tareas"
                if task_logs_dir.exists():
                    log_files = [f for f in task_logs_dir.glob("*.log")]
                    if log_files:
                        console.print(f"\n📋 Found {len(log_files)} task logs:")
                        for log_file in sorted(log_files):
                            task_name = log_file.stem
                            console.print(f"  • {task_name}: {log_file}")
                    else:
                        console.print("\n📋 No detailed task logs found")
                else:
                    console.print("\n📋 No task logs directory found")
            except Exception as e:
                console.print(f"[yellow]⚠️ Could not read detailed logs: {e}[/yellow]")
    
    except Exception as e:
        console.print(f"[red]❌ Error getting status: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def summarize(
    target: str = typer.Argument(..., help="Target to summarize"),
    regenerate: bool = typer.Option(False, "--regenerate", "-r", help="Regenerate summary even if it exists")
):
    """
    Generate analysis summary and reports for a target.
    """
    target_dir = config.target_dir(target)
    
    if not target_dir.exists():
        console.print(f"[red]❌ Target not found: {target}[/red]")
        raise typer.Exit(1)
    
    try:
        console.print(f"📊 Generating summary for: [bold cyan]{target}[/bold cyan]")
        
        summarizer = Summarizer(target)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Analyzing results...", total=None)
            
            summary_data = summarizer.generate_summary()
            
            progress.update(task, description="Summary generated")
        
        # Display summary stats
        stats = summary_data.get('statistics', {})
        
        summary_content = f"Files Analyzed: {stats.get('total_files', 0)}\n"
        summary_content += f"Total Findings: {stats.get('total_findings', 0)}\n"
        summary_content += f"High Confidence: {stats.get('high_confidence_findings', 0)}\n"
        
        findings_by_severity = stats.get('findings_by_severity', {})
        summary_content += f"High Severity: {findings_by_severity.get('high', 0)}\n"
        summary_content += f"Medium Severity: {findings_by_severity.get('medium', 0)}\n"
        summary_content += f"Low Severity: {findings_by_severity.get('low', 0)}\n"
        
        print_panel(summary_content, title="📈 Analysis Summary", style="green")
        
        # Show report files
        reports_dir = config.reports_dir(target)
        report_files = []
        
        for file_path in reports_dir.glob("*"):
            if file_path.is_file():
                size_mb = file_path.stat().st_size / (1024 * 1024)
                report_files.append({
                    'File': file_path.name,
                    'Size (MB)': f"{size_mb:.2f}"
                })
        
        if report_files:
            print_status_table(report_files, "Generated Reports")
        
        console.print(f"[green]✅ Summary generated in {reports_dir}[/green]")
    
    except Exception as e:
        console.print(f"[red]❌ Error generating summary: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def zip(
    target: str = typer.Argument(..., help="Target to archive"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output ZIP file path")
):
    """
    Create a ZIP archive with results for a target.
    """
    target_dir = config.target_dir(target)
    
    if not target_dir.exists():
        console.print(f"[red]❌ Target not found: {target}[/red]")
        raise typer.Exit(1)
    
    try:
        if output:
            zip_path = Path(output)
        else:
            zip_path = config.reports_dir(target) / "results.zip"
        
        console.print(f"📦 Creating ZIP archive: [cyan]{zip_path}[/cyan]")
        
        # Exclude patterns
        exclude_patterns = [
            "*.tmp",
            "*.lock",
            "__pycache__/**",
            ".stop"
        ]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Creating archive...", total=None)
            
            create_zip_archive(target_dir, zip_path, exclude_patterns)
            
            progress.update(task, description="Archive created")
        
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        console.print(f"[green]✅ ZIP created: {zip_path} ({size_mb:.2f} MB)[/green]")
    
    except Exception as e:
        console.print(f"[red]❌ Error creating ZIP: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def bot():
    """
    Start the Telegram bot server for remote monitoring.
    """
    if not config.is_telegram_configured():
        console.print("[red]❌ Telegram not configured[/red]")
        console.print("Please set BOT_TOKEN and CHAT_ID in .env file")
        raise typer.Exit(1)
    
    try:
        console.print("🤖 Starting Telegram bot...")
        console.print(f"Chat ID: [cyan]{config.CHAT_ID}[/cyan]")
        console.print("Press [bold red]Ctrl+C[/bold red] to stop")
        
        bot = BugBountyBot()
        bot.run_sync()
    
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Bot stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]❌ Bot failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def list():
    """
    List all available targets.
    """
    work_dir = config.work_dir_path
    
    if not work_dir.exists():
        console.print("[yellow]📂 No targets found[/yellow]")
        return
    
    targets = [d.name for d in work_dir.iterdir() if d.is_dir()]
    
    if not targets:
        console.print("[yellow]📂 No targets found[/yellow]")
        return
    
    target_data = []
    
    for target in sorted(targets):
        # Check status
        progress_data = read_json(config.progress_json_path(target))
        status = "Inactive"
        
        if progress_data:
            status = progress_data.get('status', 'Unknown')
        
        # Check if there are results
        reports_dir = config.reports_dir(target)
        has_results = "No"
        if reports_dir.exists() and any(reports_dir.glob("*")):
            has_results = "Yes"
        
        target_data.append({
            'Target': target,
            'Status': status,
            'Has Results': has_results
        })
    
    print_status_table(target_data, "Available Targets")


@app.command()
def clean(
    target: str = typer.Argument(..., help="Target to clean"),
    logs: bool = typer.Option(False, "--logs", help="Clean log files"),
    outputs: bool = typer.Option(False, "--outputs", help="Clean output files"),
    reports: bool = typer.Option(False, "--reports", help="Clean report files"),
    all: bool = typer.Option(False, "--all", help="Clean everything")
):
    """
    Clean files for a target.
    """
    target_dir = config.target_dir(target)
    
    if not target_dir.exists():
        console.print(f"[red]❌ Target not found: {target}[/red]")
        raise typer.Exit(1)
    
    if not any([logs, outputs, reports, all]):
        console.print("[red]❌ Please specify what to clean (--logs, --outputs, --reports, or --all)[/red]")
        raise typer.Exit(1)
    
    try:
        cleaned = []
        
        if logs or all:
            logs_dir = config.logs_dir(target)
            if logs_dir.exists():
                shutil.rmtree(logs_dir)
                logs_dir.mkdir()
                cleaned.append("logs")
        
        if outputs or all:
            outputs_dir = config.outputs_dir(target)
            if outputs_dir.exists():
                shutil.rmtree(outputs_dir)
                config.ensure_target_structure(target)  # Recreate structure
                cleaned.append("outputs")
        
        if reports or all:
            reports_dir = config.reports_dir(target)
            if reports_dir.exists():
                shutil.rmtree(reports_dir)
                reports_dir.mkdir()
                cleaned.append("reports")
        
        if cleaned:
            console.print(f"[green]✅ Cleaned {', '.join(cleaned)} for {target}[/green]")
        else:
            console.print("[yellow]⚠️  Nothing to clean[/yellow]")
    
    except Exception as e:
        console.print(f"[red]❌ Error cleaning: {e}[/red]")
        raise typer.Exit(1)


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()