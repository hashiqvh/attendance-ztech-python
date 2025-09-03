import asyncio
import logging
import json
from multiprocessing import Process, Manager
from datetime import datetime
import time
from zk import ZK
import httpx

# Load configuration from JSON file
with open("config.json", "r") as config_file:
    config = json.load(config_file)

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.get("log_level", "INFO")),
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

ENDPOINT = config["endpoint"]
BUFFER_LIMIT = config["buffer_limit"]
DEVICES = config["devices"]


def push_to_server(attendance_buffer):
    """
    Push attendance data to the server.
    """
    if attendance_buffer:
        payload = {
            "Json": list(attendance_buffer)
        }  # Convert ListProxy to a standard list
        logging.info(f"Pushing {len(attendance_buffer)} records to the server.")
        try:
            response = httpx.post(
                ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=50,
            )
            if response.status_code == 200:
                logging.info("Data successfully pushed to the server.")
                # Clear the shared buffer by reassigning it to an empty list
                attendance_buffer[:] = []  # Modify the ListProxy object in place
                return True
            else:
                logging.error(
                    f"Failed to push data. Status Code: {response.status_code}, Response: {response.text}"
                )
                return False
        except Exception as e:
            logging.error(f"Error while pushing data: {e}")
            return False


def fetch_end_of_day_logs(device):
    """
    Fetch current day's attendance logs from a device and push them to the server.
    """
    zk = ZK(
        device["ip_address"],
        port=device["port"],
        timeout=100,
        password=0,
        force_udp=False,
        ommit_ping=False,
    )
    try:
        logging.info(f"Connecting to {device['device_id']} for end-of-day logs...")
        conn = zk.connect()
        conn.enable_device()
        logging.info(f"Connected to {device['device_id']}.")

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

            # Push data to the server
            if attendance_data:
                if push_to_server(attendance_data):
                    logging.info(
                        f"Current day's logs pushed successfully for {device['device_id']}."
                    )
            else:
                logging.info(
                    f"No logs for the current date found for {device['device_id']}."
                )
        else:
            logging.info(f"No attendance logs found for {device['device_id']}.")

    except Exception as e:
        logging.error(f"Error fetching logs for {device['device_id']}: {e}")
    finally:
        try:
            conn.enable_device()
            conn.disconnect()
            logging.info(
                f"Disconnected from {device['device_id']} after fetching logs."
            )
        except Exception as disconnect_error:
            logging.warning(
                f"Failed to disconnect from {device['device_id']}: {disconnect_error}"
            )


def end_of_day_task():
    """
    Fetch logs from all devices and push them to the server at the end of the day.
    """
    logging.info("Starting end-of-day log fetching...")
    for device in DEVICES:
        fetch_end_of_day_logs(device)
    logging.info("End-of-day log fetching completed.")


def capture_real_time_logs(device, shared_buffer):
    """
    Capture real-time attendance logs from a device.
    """
    zk = ZK(device["ip_address"], port=device["port"], timeout=50)
    try:
        logging.info(f"Connecting to device {device['device_id']}...")
        conn = zk.connect()
        conn.enable_device()
        logging.info(f"Connected to device {device['device_id']}.")

        for attendance in conn.live_capture():
            if attendance:
                log_entry = {
                    "device_id": device["device_id"],
                    "user_id": int(attendance.user_id),
                    "timestamp": attendance.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "status": attendance.status,
                    "punch": attendance.punch,
                }
                logging.info(f"Captured log: {log_entry}")
                shared_buffer.append(log_entry)

                # Push to server if buffer exceeds the limit
                if len(shared_buffer) >= BUFFER_LIMIT:
                    push_to_server(shared_buffer)

    except Exception as e:
        logging.error(f"Error capturing logs for device {device['device_id']}: {e}")
    finally:
        try:
            conn.enable_device()
            conn.disconnect()
            logging.info(f"Disconnected from device {device['device_id']}.")
        except Exception as disconnect_error:
            logging.warning(
                f"Failed to disconnect from device {device['device_id']}: {disconnect_error}"
            )


def reconnect_devices(shared_buffer):
    """
    Reconnect to devices and restart real-time log capture processes.
    """
    logging.info("Reconnecting to devices...")
    processes = []
    for device in DEVICES:
        process = Process(target=capture_real_time_logs, args=(device, shared_buffer))
        process.start()
        processes.append(process)
    return processes


def main():
    """
    Main function to handle real-time logs and end-of-day logs.
    """
    with Manager() as manager:
        shared_buffer = manager.list()  # Shared buffer for all processes
        processes = reconnect_devices(shared_buffer)  # Initial connection

        try:
            last_reconnect_time = time.time()  # Track last reconnect time
            while True:
                now = datetime.now()

                # Check if it's time to reconnect (every 15 minutes)
                if time.time() - last_reconnect_time >= 15 * 60:
                    logging.info("Reconnecting to devices after 15 minutes...")
                    for process in processes:
                        process.terminate()  # Terminate old processes
                    processes = reconnect_devices(shared_buffer)  # Restart processes
                    last_reconnect_time = time.time()  # Reset reconnect timer

                # Check if it's the end of the day (23:59)
                if now.hour == 23 and now.minute == 59 and now.second == 0:
                    end_of_day_task()
                    # Sleep for a minute to avoid multiple executions
                    asyncio.sleep(60)
        except KeyboardInterrupt:
            logging.info("Script terminated by user.")
        finally:
            for process in processes:
                process.terminate()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Script terminated by user.")
