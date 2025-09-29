import asyncio
import logging
import json
import os
import sys
from multiprocessing import Process, Manager
from datetime import datetime
import time
from zk import ZK
import httpx
from pathlib import Path

# Create comprehensive logging setup
def setup_logging():
    """Setup comprehensive logging for Windows service environment"""
    # Create log directories
    log_dir = Path("C:/ProgramData/AttendanceZTech/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create desktop logs folder for easy access
    desktop_logs = Path(os.path.expanduser("~/Desktop/AttendanceZTech Logs"))
    desktop_logs.mkdir(exist_ok=True)
    
    # Main log file
    main_log = log_dir / "attendance.log"
    desktop_log = desktop_logs / "attendance.log"
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup root logger
    logger = logging.getLogger('AttendanceZTech')
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # File handler for main log
    file_handler = logging.FileHandler(main_log, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # File handler for desktop log (easy access)
    desktop_handler = logging.FileHandler(desktop_log, encoding='utf-8')
    desktop_handler.setLevel(logging.INFO)
    desktop_handler.setFormatter(formatter)
    logger.addHandler(desktop_handler)
    
    # Console handler (for debugging)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Also write to local log.txt for compatibility
    local_handler = logging.FileHandler("log.txt", encoding='utf-8')
    local_handler.setLevel(logging.INFO)
    local_handler.setFormatter(formatter)
    logger.addHandler(local_handler)
    
    return logger

# Setup logging first
logger = setup_logging()

# Write startup message to all logs
startup_msg = f"=== Attendance ZTech System Started ===\nTimestamp: {datetime.now()}\nPython Version: {sys.version}\nWorking Directory: {os.getcwd()}\n=====================================\n"
logger.info(startup_msg)

# Load configuration from JSON file
try:
    with open("config.json", "r") as config_file:
        config = json.load(config_file)
    logger.info("Configuration loaded successfully")
except Exception as e:
    logger.error(f"Failed to load config.json: {e}")
    sys.exit(1)

ENDPOINT = config["endpoint"]
BUFFER_LIMIT = config["buffer_limit"]
DEVICES = config["devices"]

logger.info(f"System configured with {len(DEVICES)} devices")
logger.info(f"Server endpoint: {ENDPOINT}")
logger.info(f"Buffer limit: {BUFFER_LIMIT}")

def log_device_status(device, status, details=""):
    """Log device connection status with details"""
    status_msg = f"Device {device['device_id']} ({device['ip_address']}:{device['port']}) - {status}"
    if details:
        status_msg += f" - {details}"
    logger.info(status_msg)

def push_to_server(attendance_buffer):
    """
    Push attendance data to the server.
    """
    if attendance_buffer:
        payload = {
            "Json": list(attendance_buffer)
        }
        logger.info(f"Pushing {len(attendance_buffer)} records to server at {ENDPOINT}")
        try:
            response = httpx.post(
                ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=50,
            )
            if response.status_code == 200:
                logger.info(f"✅ Successfully pushed {len(attendance_buffer)} records to server")
                attendance_buffer[:] = []
                return True
            else:
                logger.error(f"❌ Failed to push data. Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Error pushing data to server: {e}")
            return False
    return True

def fetch_end_of_day_logs(device):
    """
    Fetch current day's attendance logs from a device and push them to the server.
    """
    logger.info(f"🔄 Starting end-of-day log fetch for device {device['device_id']}")
    
    try:
        zk = ZK(
            device["ip_address"],
            port=device["port"],
            timeout=100,
            password=0,
            force_udp=False,
            ommit_ping=False,
        )
        
        log_device_status(device, "Connecting for end-of-day logs...")
        conn = zk.connect()
        
        if conn:
            conn.enable_device()
            log_device_status(device, "Connected successfully", "Fetching logs...")
            
            # Fetch all logs
            logs = conn.get_attendance()
            if logs:
                # Filter logs for the current date
                current_date = datetime.now().strftime("%Y-%m-%d")
                attendance_data = [
                    {
                        "device_id": device["device_id"],
                        "user_id": int(log.user_id),
                        "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "status": log.status,
                        "punch": log.punch,
                    }
                    for log in logs
                    if log.timestamp.strftime("%Y-%m-%d") == current_date
                ]

                logger.info(f"📊 Found {len(attendance_data)} attendance records for {current_date} from device {device['device_id']}")
                
                # Push data to the server
                if attendance_data:
                    if push_to_server(attendance_data):
                        logger.info(f"✅ End-of-day logs pushed successfully for device {device['device_id']}")
                    else:
                        logger.error(f"❌ Failed to push end-of-day logs for device {device['device_id']}")
                else:
                    logger.info(f"ℹ️ No logs for {current_date} found for device {device['device_id']}")
            else:
                logger.info(f"ℹ️ No attendance logs found for device {device['device_id']}")

        else:
            log_device_status(device, "Failed to connect", "Connection returned None")

    except Exception as e:
        log_device_status(device, "Error during end-of-day fetch", str(e))
        logger.error(f"❌ Error fetching end-of-day logs for {device['device_id']}: {e}")
    finally:
        try:
            if 'conn' in locals() and conn:
                conn.enable_device()
                conn.disconnect()
                log_device_status(device, "Disconnected after end-of-day fetch")
        except Exception as disconnect_error:
            logger.warning(f"⚠️ Failed to disconnect from {device['device_id']}: {disconnect_error}")

def end_of_day_task():
    """
    Fetch logs from all devices and push them to the server at the end of the day.
    """
    logger.info("🌅 Starting end-of-day log fetching for all devices...")
    for device in DEVICES:
        fetch_end_of_day_logs(device)
    logger.info("🌅 End-of-day log fetching completed for all devices")

def capture_real_time_logs(device, shared_buffer):
    """
    Capture real-time attendance logs from a device.
    """
    device_id = device['device_id']
    ip_address = device['ip_address']
    port = device['port']
    
    logger.info(f"🔄 Starting real-time log capture for device {device_id} ({ip_address}:{port})")
    
    try:
        zk = ZK(ip_address, port=port, timeout=50)
        log_device_status(device, "Connecting for real-time capture...")
        
        conn = zk.connect()
        if conn:
            conn.enable_device()
            log_device_status(device, "Connected successfully", "Real-time capture active")
            
            # Log device info
            try:
                device_info = conn.get_device_info()
                logger.info(f"📱 Device {device_id} Info: {device_info}")
            except:
                logger.info(f"📱 Device {device_id} connected (device info not available)")
            
            # Start live capture
            for attendance in conn.live_capture():
                if attendance:
                    log_entry = {
                        "device_id": device_id,
                        "user_id": int(attendance.user_id),
                        "timestamp": attendance.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "status": attendance.status,
                        "punch": attendance.punch,
                    }
                    
                    logger.info(f"👤 New attendance: User {attendance.user_id} at {log_entry['timestamp']} (Device: {device_id})")
                    shared_buffer.append(log_entry)

                    # Push to server if buffer exceeds the limit
                    if len(shared_buffer) >= BUFFER_LIMIT:
                        logger.info(f"📦 Buffer limit reached ({len(shared_buffer)} records), pushing to server...")
                        push_to_server(shared_buffer)

        else:
            log_device_status(device, "Failed to connect", "Connection returned None")

    except Exception as e:
        log_device_status(device, "Error during real-time capture", str(e))
        logger.error(f"❌ Error capturing real-time logs for device {device_id}: {e}")
    finally:
        try:
            if 'conn' in locals() and conn:
                conn.enable_device()
                conn.disconnect()
                log_device_status(device, "Disconnected from real-time capture")
        except Exception as disconnect_error:
            logger.warning(f"⚠️ Failed to disconnect from {device_id}: {disconnect_error}")

def reconnect_devices(shared_buffer):
    """
    Reconnect to devices and restart real-time log capture processes.
    """
    logger.info("🔄 Reconnecting to all devices...")
    processes = []
    
    for device in DEVICES:
        logger.info(f"🔄 Starting process for device {device['device_id']}")
        process = Process(target=capture_real_time_logs, args=(device, shared_buffer))
        process.start()
        processes.append(process)
        logger.info(f"✅ Process started for device {device['device_id']} (PID: {process.pid})")
    
    logger.info(f"✅ All {len(processes)} device processes started successfully")
    return processes

def main():
    """
    Main function to handle real-time logs and end-of-day logs.
    """
    logger.info("🚀 Starting Attendance ZTech System...")
    
    with Manager() as manager:
        shared_buffer = manager.list()
        logger.info("📦 Shared buffer initialized")
        
        processes = reconnect_devices(shared_buffer)
        logger.info("🔗 Initial device connections established")

        try:
            last_reconnect_time = time.time()
            logger.info("⏰ Starting main monitoring loop...")
            
            while True:
                now = datetime.now()

                # Check if it's time to reconnect (every 15 minutes)
                if time.time() - last_reconnect_time >= 15 * 60:
                    logger.info("🔄 Scheduled reconnection after 15 minutes...")
                    for process in processes:
                        process.terminate()
                    processes = reconnect_devices(shared_buffer)
                    last_reconnect_time = time.time()

                # Check if it's the end of the day (23:59)
                if now.hour == 23 and now.minute == 59 and now.second == 0:
                    logger.info("🌅 End of day detected, starting end-of-day task...")
                    end_of_day_task()
                    # Sleep for a minute to avoid multiple executions
                    time.sleep(60)
                
                # Sleep for a short interval
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("⏹️ Script terminated by user")
        except Exception as e:
            logger.error(f"❌ Unexpected error in main loop: {e}")
        finally:
            logger.info("🔄 Terminating all device processes...")
            for process in processes:
                process.terminate()
            logger.info("👋 Attendance ZTech System stopped")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("⏹️ Script terminated by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
