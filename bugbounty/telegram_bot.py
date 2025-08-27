"""
Telegram bot implementation for remote monitoring and control.
Handles bot commands for status, results, logs, and control.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.error import TelegramError

from .config import config
from .db import Database, init_db
from .utils import read_json, tail_file, format_timestamp, format_duration, create_stop_flag
from .summarizer import Summarizer
from .notifier import TelegramNotifier


class BugBountyBot:
    """Telegram bot for bug bounty tool monitoring."""
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or config.BOT_TOKEN
        self.chat_id = int(chat_id or config.CHAT_ID) if (chat_id or config.CHAT_ID) else None
        self.application = None
        self.logger = logging.getLogger(__name__)
        
        if not self.bot_token or not self.chat_id:
            raise ValueError("Bot token and chat ID must be configured")
    
    def is_authorized(self, update: Update) -> bool:
        """Check if user is authorized to use the bot."""
        return update.effective_chat.id == self.chat_id
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not self.is_authorized(update):
            return
        
        welcome_message = (
            "🎯 **Bug Bounty Tool Bot**\n\n"
            "Available commands:\n"
            "• `/status <target>` - Show progress\n"
            "• `/resultados <target>` - Get results summary\n"
            "• `/tail <target> [task]` - Show recent logs\n"
            "• `/stop <target>` - Stop execution\n"
            "• `/top <target>` - Show top findings\n"
            "• `/list` - List available targets\n"
            "• `/help` - Show this help\n\n"
            "Created by **r0tbin** 🚀"
        )
        
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        if not self.is_authorized(update):
            return
        
        await self.start_command(update, context)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        if not self.is_authorized(update):
            return
        
        if not context.args:
            await update.message.reply_text("❌ Please specify a target: `/status <target>`", parse_mode='Markdown')
            return
        
        target = context.args[0]
        target_dir = config.target_dir(target)
        
        if not target_dir.exists():
            await update.message.reply_text(f"❌ Target `{target}` not found", parse_mode='Markdown')
            return
        
        try:
            # Read progress.json
            progress_data = read_json(config.progress_json_path(target))
            
            if not progress_data:
                await update.message.reply_text(f"📊 No active run for `{target}`", parse_mode='Markdown')
                return
            
            # Format progress message
            message = f"🎯 **{target}** Status\n\n"
            
            status = progress_data.get('status', 'UNKNOWN')
            status_emoji = {
                'PENDING': '⏳',
                'RUNNING': '🔄',
                'DONE': '✅',
                'ERROR': '❌',
                'CANCELLED': '🛑'
            }.get(status, '❓')
            
            message += f"**Status:** {status_emoji} {status}\n"
            
            # Progress bar
            total = progress_data.get('total', 0)
            done = progress_data.get('done', 0)
            if total > 0:
                percentage = (done / total) * 100
                progress_bar = self._create_progress_bar(percentage)
                message += f"**Progress:** {progress_bar} {percentage:.1f}%\n"
                message += f"**Tasks:** {done}/{total}\n"
            
            # Current task
            current_task = progress_data.get('current_task')
            if current_task:
                message += f"**Current:** `{current_task}`\n"
            
            # ETA
            eta_seconds = progress_data.get('eta_seconds')
            if eta_seconds:
                eta_str = format_duration(eta_seconds)
                message += f"**ETA:** {eta_str}\n"
            
            # Started time
            started = progress_data.get('started')
            if started:
                message += f"**Started:** {format_timestamp(started)}\n"
            
            # Last update
            last_update = progress_data.get('last_update')
            if last_update:
                message += f"**Updated:** {format_timestamp(last_update)}\n"
            
            await update.message.reply_text(message, parse_mode='Markdown')
        
        except Exception as e:
            self.logger.error(f"Error getting status for {target}: {e}")
            await update.message.reply_text(f"❌ Error getting status: {str(e)}", parse_mode='Markdown')
    
    async def resultados_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resultados command."""
        if not self.is_authorized(update):
            return
        
        if not context.args:
            await update.message.reply_text("❌ Please specify a target: `/resultados <target>`", parse_mode='Markdown')
            return
        
        target = context.args[0]
        target_dir = config.target_dir(target)
        
        if not target_dir.exists():
            await update.message.reply_text(f"❌ Target `{target}` not found", parse_mode='Markdown')
            return
        
        try:
            reports_dir = config.reports_dir(target)
            
            # Check for summary files
            summary_md = reports_dir / "summary.md"
            summary_json = reports_dir / "summary.json"
            results_zip = reports_dir / "results.zip"
            
            if summary_md.exists():
                # Send summary as file
                await update.message.reply_document(
                    document=open(summary_md, 'rb'),
                    filename=f"{target}_summary.md",
                    caption=f"📊 Summary report for {target}"
                )
            
            if results_zip.exists():
                # Send ZIP file
                await update.message.reply_document(
                    document=open(results_zip, 'rb'),
                    filename=f"{target}_results.zip",
                    caption=f"📦 Complete results for {target}"
                )
            
            if summary_json.exists():
                # Send quick stats
                summary_data = read_json(summary_json)
                if summary_data:
                    stats = summary_data.get('statistics', {})
                    message = f"📈 **{target}** Quick Stats\n\n"
                    message += f"**Files:** {stats.get('total_files', 0)}\n"
                    message += f"**Findings:** {stats.get('total_findings', 0)}\n"
                    message += f"**High Severity:** {stats.get('findings_by_severity', {}).get('high', 0)}\n"
                    message += f"**High Confidence:** {stats.get('high_confidence_findings', 0)}\n"
                    
                    await update.message.reply_text(message, parse_mode='Markdown')
            
            if not any([summary_md.exists(), summary_json.exists(), results_zip.exists()]):
                await update.message.reply_text(f"❌ No results found for `{target}`", parse_mode='Markdown')
        
        except Exception as e:
            self.logger.error(f"Error getting results for {target}: {e}")
            await update.message.reply_text(f"❌ Error getting results: {str(e)}", parse_mode='Markdown')
    
    async def tail_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /tail command."""
        if not self.is_authorized(update):
            return
        
        if not context.args:
            await update.message.reply_text("❌ Please specify a target: `/tail <target> [task_name]`", parse_mode='Markdown')
            return
        
        target = context.args[0]
        task_name = context.args[1] if len(context.args) > 1 else None
        
        target_dir = config.target_dir(target)
        if not target_dir.exists():
            await update.message.reply_text(f"❌ Target `{target}` not found", parse_mode='Markdown')
            return
        
        try:
            if task_name:
                # Look for task log file
                logs_dir = config.logs_dir(target) / "tareas"
                task_logs = list(logs_dir.glob(f"*_{task_name}_stdout.log"))
                
                if not task_logs:
                    await update.message.reply_text(f"❌ No logs found for task `{task_name}`", parse_mode='Markdown')
                    return
                
                log_file = task_logs[0]
            else:
                # Use runner log
                log_file = config.runner_log_path(target)
            
            if not log_file.exists():
                await update.message.reply_text(f"❌ Log file not found", parse_mode='Markdown')
                return
            
            # Get last 50 lines
            lines = tail_file(log_file, 50)
            
            if not lines:
                await update.message.reply_text(f"📄 Log file is empty", parse_mode='Markdown')
                return
            
            # Format and send log content
            log_content = ''.join(lines)
            
            # Truncate if too long
            if len(log_content) > 4000:
                log_content = log_content[-4000:] + "\n... (truncated)"
            
            message = f"📄 **{target}** Logs"
            if task_name:
                message += f" ({task_name})"
            message += "\n\n```\n" + log_content + "\n```"
            
            await update.message.reply_text(message, parse_mode='Markdown')
        
        except Exception as e:
            self.logger.error(f"Error getting logs for {target}: {e}")
            await update.message.reply_text(f"❌ Error getting logs: {str(e)}", parse_mode='Markdown')
    
    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command."""
        if not self.is_authorized(update):
            return
        
        if not context.args:
            await update.message.reply_text("❌ Please specify a target: `/stop <target>`", parse_mode='Markdown')
            return
        
        target = context.args[0]
        target_dir = config.target_dir(target)
        
        if not target_dir.exists():
            await update.message.reply_text(f"❌ Target `{target}` not found", parse_mode='Markdown')
            return
        
        try:
            # Create stop flag
            create_stop_flag(target_dir)
            
            await update.message.reply_text(
                f"🛑 Stop signal sent for `{target}`\n"
                f"The runner will stop after current tasks complete.",
                parse_mode='Markdown'
            )
        
        except Exception as e:
            self.logger.error(f"Error stopping {target}: {e}")
            await update.message.reply_text(f"❌ Error sending stop signal: {str(e)}", parse_mode='Markdown')
    
    async def top_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /top command."""
        if not self.is_authorized(update):
            return
        
        if not context.args:
            await update.message.reply_text("❌ Please specify a target: `/top <target>`", parse_mode='Markdown')
            return
        
        target = context.args[0]
        target_dir = config.target_dir(target)
        
        if not target_dir.exists():
            await update.message.reply_text(f"❌ Target `{target}` not found", parse_mode='Markdown')
            return
        
        try:
            # Load summary data
            summary_json = config.reports_dir(target) / "summary.json"
            
            if not summary_json.exists():
                await update.message.reply_text(f"❌ No analysis results found for `{target}`", parse_mode='Markdown')
                return
            
            summary_data = read_json(summary_json)
            if not summary_data:
                await update.message.reply_text(f"❌ Could not load analysis results", parse_mode='Markdown')
                return
            
            top_findings = summary_data.get('top_findings', [])
            
            if not top_findings:
                await update.message.reply_text(f"📊 No findings for `{target}`", parse_mode='Markdown')
                return
            
            # Format top findings
            message = f"🎯 **{target}** Top Findings\n\n"
            
            for i, finding in enumerate(top_findings[:5], 1):
                severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(finding['severity'], "⚪")
                confidence_emoji = {"high": "💯", "medium": "🎯", "low": "🤔"}.get(finding['confidence'], "❓")
                
                message += f"{i}. {severity_emoji} {confidence_emoji} **{finding['rule_description']}**\n"
                message += f"   📁 `{finding['file_path']}`\n"
                
                if finding['line_number']:
                    message += f"   📍 Line {finding['line_number']}\n"
                
                if finding['match_text']:
                    match_preview = finding['match_text'][:50]
                    if len(finding['match_text']) > 50:
                        match_preview += "..."
                    message += f"   🔍 `{match_preview}`\n"
                
                message += "\n"
            
            if len(top_findings) > 5:
                message += f"... and {len(top_findings) - 5} more findings\n"
                message += f"Use `/resultados {target}` for complete report"
            
            await update.message.reply_text(message, parse_mode='Markdown')
        
        except Exception as e:
            self.logger.error(f"Error getting top findings for {target}: {e}")
            await update.message.reply_text(f"❌ Error getting findings: {str(e)}", parse_mode='Markdown')
    
    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list command."""
        if not self.is_authorized(update):
            return
        
        try:
            work_dir = config.work_dir_path
            
            if not work_dir.exists():
                await update.message.reply_text("📂 No targets found", parse_mode='Markdown')
                return
            
            targets = [d.name for d in work_dir.iterdir() if d.is_dir()]
            
            if not targets:
                await update.message.reply_text("📂 No targets found", parse_mode='Markdown')
                return
            
            message = "📂 **Available Targets:**\n\n"
            
            for target in sorted(targets):
                # Check if target has active run
                progress_data = read_json(config.progress_json_path(target))
                status = "💤"
                
                if progress_data:
                    status_str = progress_data.get('status', 'UNKNOWN')
                    status = {
                        'RUNNING': '🔄',
                        'DONE': '✅',
                        'ERROR': '❌',
                        'CANCELLED': '🛑'
                    }.get(status_str, '❓')
                
                message += f"• {status} `{target}`\n"
            
            await update.message.reply_text(message, parse_mode='Markdown')
        
        except Exception as e:
            self.logger.error(f"Error listing targets: {e}")
            await update.message.reply_text(f"❌ Error listing targets: {str(e)}", parse_mode='Markdown')
    
    async def unauthorized_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages from unauthorized users."""
        await update.message.reply_text("❌ Unauthorized access")
    
    def _create_progress_bar(self, percentage: float, length: int = 10) -> str:
        """Create a text progress bar."""
        filled = int(length * percentage / 100)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}]"
    
    def setup_handlers(self):
        """Setup command handlers."""
        if not self.application:
            return
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("resultados", self.resultados_command))
        self.application.add_handler(CommandHandler("tail", self.tail_command))
        self.application.add_handler(CommandHandler("stop", self.stop_command))
        self.application.add_handler(CommandHandler("top", self.top_command))
        self.application.add_handler(CommandHandler("list", self.list_command))
        
        # Unauthorized message handler
        self.application.add_handler(
            MessageHandler(filters.ALL, self.unauthorized_handler)
        )
    
    async def run(self):
        """Run the bot."""
        try:
            # Create application
            self.application = Application.builder().token(self.bot_token).build()
            
            # Setup handlers
            self.setup_handlers()
            
            self.logger.info("Starting Telegram bot...")
            
            # Initialize and start the application
            await self.application.initialize()
            await self.application.start()
            
            # Start polling
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
            # Keep running
            await self.application.updater.idle()
        
        except Exception as e:
            self.logger.error(f"Bot error: {e}")
            raise
        finally:
            if self.application:
                await self.application.stop()
                await self.application.shutdown()
    
    def run_sync(self):
        """Run the bot synchronously."""
        try:
            # Use new event loop to avoid conflicts
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.run())
            finally:
                loop.close()
        except KeyboardInterrupt:
            self.logger.info("Bot stopped by user")
        except Exception as e:
            self.logger.error(f"Bot failed: {e}")
            raise


def main():
    """Main entry point for bot."""
    # Setup logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    try:
        bot = BugBountyBot()
        bot.run_sync()
    except Exception as e:
        print(f"Failed to start bot: {e}")


if __name__ == "__main__":
    main()