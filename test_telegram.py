#!/usr/bin/env python3
"""
Test script for Telegram bot integration.
Run this script to test if your Telegram bot is working correctly.
"""

import json
import sys
from datetime import datetime
from telegram_notifier import TelegramNotifier

def load_config():
    """Load configuration from config.json"""
    try:
        with open("config.json", "r") as config_file:
            config = json.load(config_file)
        return config
    except Exception as e:
        print(f"❌ Failed to load config.json: {e}")
        sys.exit(1)

def test_telegram_bot():
    """Test the Telegram bot functionality"""
    print("🧪 Testing Telegram Bot Integration...")
    print("=" * 50)
    
    # Load configuration
    config = load_config()
    telegram_config = config.get("telegram", {})
    
    # Check if Telegram is enabled
    if not telegram_config.get("enabled", False):
        print("⚠️ Telegram notifications are disabled in config.json")
        print("   Set 'enabled': true in the telegram section to enable")
        return False
    
    # Check if bot token and chat ID are configured
    bot_token = telegram_config.get("bot_token", "")
    chat_id = telegram_config.get("chat_id", "")
    
    if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
        print("❌ Bot token not configured!")
        print("   Please set your bot token in config.json")
        return False
    
    if not chat_id or chat_id == "YOUR_CHAT_ID_HERE":
        print("❌ Chat ID not configured!")
        print("   Please set your chat ID in config.json")
        return False
    
    # Initialize Telegram notifier
    telegram_notifier = TelegramNotifier(
        bot_token=bot_token,
        chat_id=chat_id,
        enabled=True,
        notification_settings=telegram_config.get("notifications", {})
    )
    
    print(f"📱 Bot Token: {bot_token[:10]}...")
    print(f"💬 Chat ID: {chat_id}")
    print()
    
    # Test connection
    print("🔄 Testing connection...")
    if telegram_notifier.test_connection():
        print("✅ Connection test successful!")
    else:
        print("❌ Connection test failed!")
        return False
    
    print()
    print("📤 Sending test notifications...")
    
    # Test different notification types
    test_notifications = [
        ("startup", "🚀 System startup test"),
        ("data_push", "📦 Data push test"),
        ("end_of_day", "🌅 End-of-day test"),
        ("errors", "❌ Error notification test"),
        ("device_status", "📱 Device status test")
    ]
    
    for notification_type, description in test_notifications:
        print(f"   Testing {description}...")
        
        if notification_type == "startup":
            success = telegram_notifier.send_message_sync(
                f"🧪 <b>Test: {description}</b>\n\n"
                f"📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"✅ <b>Status:</b> This is a test notification"
            )
        elif notification_type == "data_push":
            success = telegram_notifier.send_message_sync(
                f"🧪 <b>Test: {description}</b>\n\n"
                f"📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📊 <b>Records:</b> 5\n"
                f"✅ <b>Status:</b> Test data push successful"
            )
        elif notification_type == "end_of_day":
            success = telegram_notifier.send_message_sync(
                f"🧪 <b>Test: {description}</b>\n\n"
                f"📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📱 <b>Device:</b> 1\n"
                f"📊 <b>Records:</b> 10\n"
                f"✅ <b>Status:</b> Test end-of-day successful"
            )
        elif notification_type == "errors":
            success = telegram_notifier.send_message_sync(
                f"🧪 <b>Test: {description}</b>\n\n"
                f"📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"❌ <b>Error:</b> This is a test error message\n"
                f"🔧 <b>Type:</b> Test Error"
            )
        elif notification_type == "device_status":
            success = telegram_notifier.send_message_sync(
                f"🧪 <b>Test: {description}</b>\n\n"
                f"📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📱 <b>Device:</b> 1\n"
                f"✅ <b>Status:</b> Connected\n"
                f"📝 <b>Details:</b> Test connection successful"
            )
        
        if success:
            print(f"   ✅ {description} sent successfully")
        else:
            print(f"   ❌ {description} failed to send")
    
    print()
    print("🎉 Telegram bot test completed!")
    print("   Check your Telegram chat to see the test messages.")
    return True

def show_setup_instructions():
    """Show setup instructions for Telegram bot"""
    print("📋 Telegram Bot Setup Instructions")
    print("=" * 50)
    print()
    print("1. Create a Telegram Bot:")
    print("   - Open Telegram and search for @BotFather")
    print("   - Send /newbot command")
    print("   - Follow the instructions to create your bot")
    print("   - Copy the bot token provided")
    print()
    print("2. Get your Chat ID:")
    print("   - Start a chat with your bot")
    print("   - Send any message to the bot")
    print("   - Visit: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates")
    print("   - Find your chat ID in the response (look for 'chat':{'id': YOUR_CHAT_ID})")
    print()
    print("3. Update config.json:")
    print("   - Replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token")
    print("   - Replace 'YOUR_CHAT_ID_HERE' with your actual chat ID")
    print("   - Set 'enabled': true")
    print()
    print("4. Run this test script again:")
    print("   python test_telegram.py")
    print()

if __name__ == "__main__":
    print("🤖 Attendance ZTech - Telegram Bot Test")
    print("=" * 50)
    print()
    
    try:
        if test_telegram_bot():
            print("✅ All tests passed! Your Telegram bot is ready to use.")
        else:
            print("❌ Some tests failed. Please check the configuration.")
            print()
            show_setup_instructions()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        print()
        show_setup_instructions()
