"""
Notification system for Telegram integration.
Handles sending messages, files, and status updates to Telegram.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Union
from telegram import Bot, InputFile
from telegram.error import TelegramError
import io

from .config import config


class TelegramNotifier:
    """Telegram notification sender."""
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or config.BOT_TOKEN
        self.chat_id = chat_id or config.CHAT_ID
        self.bot = None
        self.logger = logging.getLogger(__name__)
        
        if self.bot_token and self.chat_id:
            self.bot = Bot(token=self.bot_token)
        else:
            self.logger.warning("Telegram not configured - notifications disabled")
    
    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.bot_token and self.chat_id and self.bot)
    
    def send_text(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """
        Send a text message to Telegram.
        
        Args:
            message: Message text
            parse_mode: Parse mode (Markdown, HTML, or None)
        
        Returns:
            True if message sent successfully
        """
        if not self.is_configured():
            self.logger.debug(f"Telegram not configured, would send: {message}")
            return False
        
        try:
            # Run async function in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self.bot.send_message(
                        chat_id=self.chat_id,
                        text=message,
                        parse_mode=parse_mode
                    )
                )
                return True
            finally:
                loop.close()
        
        except TelegramError as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending Telegram message: {e}")
            return False
    
    def send_file(self, file_path: Path, caption: str = None) -> bool:
        """
        Send a file to Telegram.
        
        Args:
            file_path: Path to file
            caption: Optional caption
        
        Returns:
            True if file sent successfully
        """
        if not self.is_configured():
            self.logger.debug(f"Telegram not configured, would send file: {file_path}")
            return False
        
        if not file_path.exists():
            self.logger.error(f"File not found: {file_path}")
            return False
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                with open(file_path, 'rb') as f:
                    result = loop.run_until_complete(
                        self.bot.send_document(
                            chat_id=self.chat_id,
                            document=f,
                            filename=file_path.name,
                            caption=caption
                        )
                    )
                return True
            finally:
                loop.close()
        
        except TelegramError as e:
            self.logger.error(f"Failed to send Telegram file: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending Telegram file: {e}")
            return False
    
    def send_zip(self, zip_path: Path, caption: str = None) -> bool:
        """
        Send a ZIP file to Telegram.
        
        Args:
            zip_path: Path to ZIP file
            caption: Optional caption
        
        Returns:
            True if ZIP sent successfully
        """
        return self.send_file(zip_path, caption)
    
    def send_text_as_file(self, text: str, filename: str, caption: str = None) -> bool:
        """
        Send text content as a file to Telegram.
        
        Args:
            text: Text content
            filename: Filename for the attachment
            caption: Optional caption
        
        Returns:
            True if sent successfully
        """
        if not self.is_configured():
            self.logger.debug(f"Telegram not configured, would send text file: {filename}")
            return False
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Create file-like object from text
                text_file = io.BytesIO(text.encode('utf-8'))
                text_file.name = filename
                
                result = loop.run_until_complete(
                    self.bot.send_document(
                        chat_id=self.chat_id,
                        document=text_file,
                        filename=filename,
                        caption=caption
                    )
                )
                return True
            finally:
                loop.close()
        
        except TelegramError as e:
            self.logger.error(f"Failed to send text as Telegram file: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending text as Telegram file: {e}")
            return False
    
    def send_progress(self, target: str, completed: int, total: int, 
                     current_task: str = None, eta_seconds: int = None) -> bool:
        """
        Send progress update to Telegram.
        
        Args:
            target: Target name
            completed: Number of completed tasks
            total: Total number of tasks
            current_task: Currently running task
            eta_seconds: Estimated time to completion
        
        Returns:
            True if message sent successfully
        """
        percentage = (completed / total * 100) if total > 0 else 0
        progress_bar = self._create_progress_bar(percentage)
        
        message = f"🎯 **{target}** Progress Update\n\n"
        message += f"{progress_bar} {percentage:.1f}%\n"
        message += f"Tasks: {completed}/{total}\n"
        
        if current_task:
            message += f"Current: `{current_task}`\n"
        
        if eta_seconds:
            eta_str = self._format_duration(eta_seconds)
            message += f"ETA: {eta_str}\n"
        
        return self.send_text(message)
    
    def send_completion_summary(self, target: str, success: bool, 
                              completed: int, total: int, duration_seconds: int) -> bool:
        """
        Send completion summary to Telegram.
        
        Args:
            target: Target name
            success: Whether run completed successfully
            completed: Number of completed tasks
            total: Total number of tasks
            duration_seconds: Total run duration
        
        Returns:
            True if message sent successfully
        """
        status_emoji = "✅" if success else "❌"
        status_text = "Completed" if success else "Failed"
        
        message = f"{status_emoji} **{target}** {status_text}\n\n"
        message += f"Tasks: {completed}/{total}\n"
        message += f"Duration: {self._format_duration(duration_seconds)}\n"
        
        if not success:
            failed_count = total - completed
            message += f"Failed tasks: {failed_count}\n"
        
        return self.send_text(message)
    
    def send_error(self, target: str, error_message: str) -> bool:
        """
        Send error notification to Telegram.
        
        Args:
            target: Target name
            error_message: Error description
        
        Returns:
            True if message sent successfully
        """
        message = f"🚨 **{target}** Error\n\n"
        message += f"```\n{error_message}\n```"
        
        return self.send_text(message)
    
    def _create_progress_bar(self, percentage: float, length: int = 10) -> str:
        """Create a text progress bar."""
        filled = int(length * percentage / 100)
        bar = "█" * filled + "░" * (length - filled)
        return f"[{bar}]"
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    def test_connection(self) -> bool:
        """
        Test Telegram connection.
        
        Returns:
            True if connection successful
        """
        if not self.is_configured():
            return False
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self.bot.get_me())
                self.logger.info(f"Telegram bot connected: @{result.username}")
                return True
            finally:
                loop.close()
        
        except Exception as e:
            self.logger.error(f"Telegram connection test failed: {e}")
            return False


# Global notifier instance
_notifier_instance = None


def get_notifier() -> Optional[TelegramNotifier]:
    """Get global notifier instance."""
    global _notifier_instance
    if _notifier_instance is None and config.is_telegram_configured():
        _notifier_instance = TelegramNotifier()
    return _notifier_instance


def create_notifier(bot_token: str = None, chat_id: str = None) -> TelegramNotifier:
    """Create a new notifier instance."""
    return TelegramNotifier(bot_token, chat_id)