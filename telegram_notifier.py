import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import httpx
import json

class TelegramNotifier:
    """
    Telegram bot notifier for attendance system status updates.
    """
    
    def __init__(self, bot_token: str, chat_id: str, enabled: bool = True, notification_settings: Optional[Dict[str, bool]] = None, system_name: str = "Attendance System"):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.notification_settings = notification_settings or {}
        self.system_name = system_name
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger('AttendanceZTech.Telegram')
        
    def is_notification_enabled(self, notification_type: str) -> bool:
        """Check if a specific notification type is enabled."""
        if not self.enabled:
            return False
        return self.notification_settings.get(notification_type, True)
    
    async def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message to Telegram.
        
        Args:
            message: The message to send
            parse_mode: Message parsing mode (HTML or Markdown)
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False
            
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                
                if response.status_code == 200:
                    self.logger.debug("Telegram message sent successfully")
                    return True
                else:
                    self.logger.error(f"Failed to send Telegram message. Status: {response.status_code}, Response: {response.text}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {e}")
            return False
    
    def send_message_sync(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Synchronous wrapper for send_message.
        """
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.send_message(message, parse_mode))
        except RuntimeError:
            # If no event loop is running, create a new one
            return asyncio.run(self.send_message(message, parse_mode))
    
    async def send_startup_notification(self, device_count: int, endpoint: str) -> bool:
        """Send startup notification."""
        if not self.is_notification_enabled("startup"):
            return False
            
        message = f"""
🚀 <b>{self.system_name} Started</b>

📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📱 <b>Devices:</b> {device_count}
🌐 <b>Endpoint:</b> {endpoint}

✅ System is now monitoring attendance devices
        """
        return await self.send_message(message.strip())
    
    async def send_end_of_day_notification(self, device_id: int, record_count: int, success: bool) -> bool:
        """Send end-of-day data push notification."""
        if not self.is_notification_enabled("end_of_day"):
            return False
            
        status_emoji = "✅" if success else "❌"
        status_text = "Successfully" if success else "Failed to"
        
        message = f"""
🌅 <b>{self.system_name} - End-of-Day Data Push</b>

📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📱 <b>Device:</b> {device_id}
📊 <b>Records:</b> {record_count}
{status_emoji} <b>Status:</b> {status_text} push data to server
        """
        return await self.send_message(message.strip())
    
    async def send_data_push_notification(self, record_count: int, success: bool, device_id: Optional[int] = None) -> bool:
        """Send data push notification."""
        if not self.is_notification_enabled("data_push"):
            return False
            
        status_emoji = "✅" if success else "❌"
        status_text = "Successfully" if success else "Failed to"
        device_info = f" (Device: {device_id})" if device_id else ""
        
        message = f"""
📦 <b>{self.system_name} - Data Push Notification</b>

📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📊 <b>Records:</b> {record_count}{device_info}
{status_emoji} <b>Status:</b> {status_text} push data to server
        """
        return await self.send_message(message.strip())
    
    async def send_error_notification(self, error_type: str, error_message: str, device_id: Optional[int] = None) -> bool:
        """Send error notification."""
        if not self.is_notification_enabled("errors"):
            return False
            
        device_info = f" (Device: {device_id})" if device_id else ""
        
        message = f"""
❌ <b>{self.system_name} - Error Alert</b>

📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔧 <b>Type:</b> {error_type}{device_info}
📝 <b>Message:</b> {error_message}
        """
        return await self.send_message(message.strip())
    
    async def send_device_status_notification(self, device_id: int, status: str, details: str = "") -> bool:
        """Send device status notification."""
        if not self.is_notification_enabled("device_status"):
            return False
            
        status_emoji = "✅" if "success" in status.lower() or "connected" in status.lower() else "⚠️"
        
        message = f"""
📱 <b>{self.system_name} - Device Status Update</b>

📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔧 <b>Device:</b> {device_id}
{status_emoji} <b>Status:</b> {status}
{f"📝 <b>Details:</b> {details}" if details else ""}
        """
        return await self.send_message(message.strip())
    
    async def send_daily_summary(self, total_records: int, successful_pushes: int, failed_pushes: int, devices_status: Dict[int, str]) -> bool:
        """Send daily summary notification."""
        if not self.is_notification_enabled("end_of_day"):
            return False
            
        success_rate = (successful_pushes / (successful_pushes + failed_pushes) * 100) if (successful_pushes + failed_pushes) > 0 else 0
        
        message = f"""
📊 <b>{self.system_name} - Daily Summary Report</b>

📅 <b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}
📈 <b>Total Records:</b> {total_records}
✅ <b>Successful Pushes:</b> {successful_pushes}
❌ <b>Failed Pushes:</b> {failed_pushes}
📊 <b>Success Rate:</b> {success_rate:.1f}%

📱 <b>Device Status:</b>
"""
        
        for device_id, status in devices_status.items():
            status_emoji = "✅" if "connected" in status.lower() else "❌"
            message += f"• Device {device_id}: {status_emoji} {status}\n"
        
        return await self.send_message(message.strip())
    
    def test_connection(self) -> bool:
        """Test Telegram bot connection."""
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False
            
        test_message = f"🧪 <b>{self.system_name} - Test Message</b>\n\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n✅ Telegram bot is working correctly!"
        return self.send_message_sync(test_message)
