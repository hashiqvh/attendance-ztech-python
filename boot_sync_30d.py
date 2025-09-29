#!/usr/bin/env python3
"""
boot_sync_30d.py
Run on system startup: sync the last 30 days of attendance logs
to the API using sync_all.py logic.
"""

import subprocess
import datetime
import os
import sys
import json
import logging
from telegram_notifier import TelegramNotifier

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('BootSync30d')

def load_telegram_config():
    """Load Telegram configuration from config.json"""
    try:
        with open("config.json", "r") as config_file:
            config = json.load(config_file)
        return config.get("telegram", {})
    except Exception as e:
        logger.error(f"Failed to load config.json: {e}")
        return {}

def main():
    # Calculate date range
    to_date = datetime.date.today()
    from_date = to_date - datetime.timedelta(days=30)

    # Load Telegram configuration
    telegram_config = load_telegram_config()
    telegram_notifier = TelegramNotifier(
        bot_token=telegram_config.get("bot_token", ""),
        chat_id=telegram_config.get("chat_id", ""),
        enabled=telegram_config.get("enabled", False),
        notification_settings=telegram_config.get("notifications", {})
    )

    project_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(project_dir, "venv", "bin", "python")
    sync_script = os.path.join(project_dir, "sync_all.py")

    # Build command
    cmd = [
        venv_python,
        sync_script,
        "--from", from_date.isoformat(),
        "--to", to_date.isoformat(),
        "--log-level", "INFO"
    ]

    logger.info(f"Running 30-day boot sync: {from_date} -> {to_date}")
    print(f"Running 30-day boot sync: {from_date} -> {to_date}")
    sys.stdout.flush()

    # Send startup notification
    telegram_notifier.send_message_sync(
        f"🚀 <b>30-Day Boot Sync Started</b>\n\n"
        f"📅 <b>Date Range:</b> {from_date} → {to_date}\n"
        f"📊 <b>Duration:</b> 30 days\n"
        f"🔄 <b>Status:</b> Starting historical data synchronization..."
    )

    # Run sync_all.py as a subprocess
    start_time = datetime.datetime.now()
    try:
        logger.info("Starting 30-day boot sync process...")
        subprocess.check_call(cmd)
        
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        
        logger.info("Boot sync finished successfully.")
        print("Boot sync finished successfully.")
        
        # Send success notification
        telegram_notifier.send_message_sync(
            f"✅ <b>30-Day Boot Sync Completed</b>\n\n"
            f"📅 <b>Date Range:</b> {from_date} → {to_date}\n"
            f"⏱️ <b>Duration:</b> {duration.total_seconds():.1f} seconds\n"
            f"✅ <b>Status:</b> Historical data synchronization completed successfully"
        )
        
    except subprocess.CalledProcessError as e:
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        
        error_msg = f"Boot sync failed: {e}"
        logger.error(error_msg)
        print(error_msg)
        
        # Send error notification
        telegram_notifier.send_message_sync(
            f"❌ <b>30-Day Boot Sync Failed</b>\n\n"
            f"📅 <b>Date Range:</b> {from_date} → {to_date}\n"
            f"⏱️ <b>Duration:</b> {duration.total_seconds():.1f} seconds\n"
            f"❌ <b>Status:</b> Historical data synchronization failed\n"
            f"🔧 <b>Error:</b> {str(e)}"
        )
        
        sys.exit(1)
    except Exception as e:
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        
        error_msg = f"Unexpected error during boot sync: {e}"
        logger.error(error_msg)
        print(error_msg)
        
        # Send error notification
        telegram_notifier.send_message_sync(
            f"❌ <b>30-Day Boot Sync Error</b>\n\n"
            f"📅 <b>Date Range:</b> {from_date} → {to_date}\n"
            f"⏱️ <b>Duration:</b> {duration.total_seconds():.1f} seconds\n"
            f"❌ <b>Status:</b> Unexpected error occurred\n"
            f"🔧 <b>Error:</b> {str(e)}"
        )
        
        sys.exit(1)


if __name__ == "__main__":
    main()
