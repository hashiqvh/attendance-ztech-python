import asyncio
import logging
import json
import os
import sys
from multiprocessing import Process, Manager
from datetime import datetime, date, timedelta
import time
from zk import ZK
import httpx
from pathlib import Path
from socket import gethostbyname
import socket
import subprocess
from telegram_notifier import TelegramNotifier

# =========================
# Helpers: logging & setup
# =========================

def setup_logging():
    """Setup comprehensive logging for server/desktop-friendly environments."""
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Desktop logs only if Desktop exists (avoid headless errors)
    desktop_dir = Path(os.path.expanduser("~/Desktop"))
    desktop_logs = None
    if desktop_dir.exists():
        desktop_logs = desktop_dir / "AttendanceZTech Logs"
        desktop_logs.mkdir(exist_ok=True)

    main_log = log_dir / "attendance.log"
    desktop_log = (desktop_logs / "attendance.log") if desktop_logs else None

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger('AttendanceZTech')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fh = logging.FileHandler(main_log, encoding='utf-8')
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    if desktop_log:
        dh = logging.FileHandler(desktop_log, encoding='utf-8')
        dh.setLevel(logging.INFO)
        dh.setFormatter(formatter)
        logger.addHandler(dh)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    local = logging.FileHandler("log.txt", encoding='utf-8')
    local.setLevel(logging.INFO)
    local.setFormatter(formatter)
    logger.addHandler(local)

    return logger

logger = setup_logging()
logger.info(
    "=== Attendance ZTech System Started ===\n"
    f"Timestamp: {datetime.now()}\n"
    f"Python: {sys.version.split()[0]}\n"
    f"CWD: {os.getcwd()}\n"
    "======================================="
)

# =========================
# Config & Telegram
# =========================

def load_config():
    try:
        with open("config.json", "r") as f:
            cfg = json.load(f)
        return cfg
    except Exception as e:
        logger.error(f"Failed to load config.json: {e}")
        sys.exit(1)

config = load_config()
ENDPOINT = config["endpoint"]
BUFFER_LIMIT = int(config["buffer_limit"])
DEVICES = config["devices"]

telegram_config = config.get("telegram", {})
telegram_notifier = TelegramNotifier(
    bot_token=telegram_config.get("bot_token", ""),
    chat_id=telegram_config.get("chat_id", ""),
    enabled=telegram_config.get("enabled", False),
    notification_settings=telegram_config.get("notifications", {})
)

logger.info(f"Configured devices: {len(DEVICES)} | Endpoint: {ENDPOINT} | Buffer limit: {BUFFER_LIMIT} | Telegram: {'ENABLED' if telegram_notifier.enabled else 'DISABLED'}")

# =========================
# Network readiness helpers
# =========================

def wait_for_network(max_wait_s=120):
    """
    Wait until DNS & outbound connectivity work.
    """
    start = time.time()
    while time.time() - start < max_wait_s:
        try:
            # DNS check (telegram and a public host)
            gethostbyname("api.telegram.org")
            gethostbyname("google.com")
            # Outbound TCP check
            with socket.create_connection(("8.8.8.8", 53), timeout=3):
                return True
        except OSError:
            time.sleep(3)
    return False

def any_device_ping_ok(hosts, max_wait_s=60):
    """
    Wait until at least one device answers ping (best-effort; do not fail hard).
    """
    start = time.time()
    while time.time() - start < max_wait_s:
        for h in hosts:
            try:
                rc = subprocess.call(["ping", "-c", "1", "-W", "1", h],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if rc == 0:
                    return True
            except Exception:
                pass
        time.sleep(3)
    return False

def host_port_reachable(host, port, timeout=3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

# =========================
# Telegram (safe send)
# =========================

def tg_send_safe(html_text: str, retries=3, backoff_s=2):
    """
    Send a Telegram message, but don't crash if network/DNS is not ready.
    """
    if not telegram_notifier.enabled:
        return
    for i in range(retries):
        try:
            telegram_notifier.send_message_sync(html_text)
            return
        except Exception as e:
            logger.error(f"Telegram send failed (attempt {i+1}/{retries}): {e}")
            time.sleep(backoff_s * (i + 1))

# =========================
# Logging helpers
# =========================

def log_device_status(device, status, details=""):
    msg = f"Device {device['device_id']} ({device['ip_address']}:{device['port']}) - {status}"
    if details:
        msg += f" - {details}"
    logger.info(msg)

# =========================
# Push to server
# =========================

def push_to_server(attendance_buffer, device_id=None):
    """
    Push attendance data to the server.
    attendance_buffer can be a Manager().list() or a normal list.
    On success, it clears the buffer in-place ([:] = []) if it is mutable.
    """
    if not attendance_buffer:
        return True

    # Copy out to avoid holding shared list during IO
    if hasattr(attendance_buffer, "__iter__"):
        data_copy = list(attendance_buffer)
    else:
        data_copy = attendance_buffer

    payload = {"Json": data_copy}
    record_count = len(data_copy)

    logger.info(f"Pushing {record_count} records to {ENDPOINT}")
    try:
        with httpx.Client(timeout=50) as client:
            resp = client.post(ENDPOINT, json=payload, headers={"Content-Type": "application/json"})
        if resp.status_code == 200:
            logger.info(f"✅ Push success ({record_count} records)")
            tg_send_safe(
                f"✅ <b>Data Push Success</b>\n\n"
                f"🕒 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🧾 <b>Records:</b> {record_count}\n"
                f"✅ <b>Status:</b> Uploaded"
            )
            # Clear only after success
            try:
                if hasattr(attendance_buffer, "clear"):
                    attendance_buffer.clear()
                else:
                    attendance_buffer[:] = []
            except Exception:
                # fallback no-op if immutable
                pass
            return True
        else:
            logger.error(f"❌ Push failed HTTP {resp.status_code}: {resp.text[:500]}")
            tg_send_safe(
                f"❌ <b>Data Push Failed</b>\n\n"
                f"🕒 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🧾 <b>Records:</b> {record_count}\n"
                f"❌ <b>Status:</b> HTTP {resp.status_code}"
            )
            return False
    except Exception as e:
        logger.error(f"❌ Push error: {e}")
        tg_send_safe(
            f"❌ <b>Data Push Error</b>\n\n"
            f"🕒 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🧾 <b>Records:</b> {record_count}\n"
            f"❌ <b>Error:</b> {str(e)}"
        )
        return False

# =========================
# End-of-day collection
# =========================

def fetch_end_of_day_logs(device):
    """
    Fetch current day's attendance logs from a device and push them.
    Best-effort: logs errors but continues.
    """
    logger.info(f"🧹 Starting EoD fetch for device {device['device_id']}")

    try:
        zk = ZK(
            device["ip_address"],
            port=device["port"],
            timeout=100,
            password=0,
            force_udp=False,
            ommit_ping=False,
        )
        log_device_status(device, "Connecting for EoD logs...")
        conn = zk.connect()
        if not conn:
            log_device_status(device, "Failed to connect", "None returned")
            return

        try:
            conn.enable_device()
            log_device_status(device, "Connected", "Fetching logs...")
            logs = conn.get_attendance()
            if not logs:
                logger.info(f"ℹ️ No attendance logs found for device {device['device_id']}")
                return

            today = datetime.now().strftime("%Y-%m-%d")
            attendance_data = [
                {
                    "device_id": device["device_id"],
                    "user_id": int(log.user_id),
                    "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "status": log.status,
                    "punch": log.punch,
                }
                for log in logs
                if log.timestamp.strftime("%Y-%m-%d") == today
            ]

            logger.info(f"📊 EoD {device['device_id']}: {len(attendance_data)} records for {today}")
            if attendance_data:
                ok = push_to_server(attendance_data, device['device_id'])
                if ok:
                    logger.info(f"✅ EoD push OK for device {device['device_id']}")
                    tg_send_safe(
                        f"🧹 <b>End-of-Day Push</b>\n\n"
                        f"🕒 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"🖥️ <b>Device:</b> {device['device_id']}\n"
                        f"🧾 <b>Records:</b> {len(attendance_data)}\n"
                        f"✅ <b>Status:</b> Uploaded"
                    )
                else:
                    logger.error(f"❌ EoD push failed for device {device['device_id']}")
                    tg_send_safe(
                        f"❌ <b>EoD Push Failed</b>\n\n"
                        f"🖥️ <b>Device:</b> {device['device_id']}\n"
                        f"🧾 <b>Records:</b> {len(attendance_data)}"
                    )
            else:
                logger.info(f"ℹ️ No logs today for device {device['device_id']}")
                tg_send_safe(
                    f"ℹ️ <b>No EoD Data</b>\n\n"
                    f"🖥️ <b>Device:</b> {device['device_id']}\n"
                    f"🧾 <b>Records:</b> 0"
                )
        finally:
            try:
                conn.enable_device()
                conn.disconnect()
                log_device_status(device, "Disconnected after EoD")
            except Exception as de:
                logger.warning(f"⚠️ Disconnect failed {device['device_id']}: {de}")
    except Exception as e:
        log_device_status(device, "Error during EoD fetch", str(e))
        logger.error(f"❌ EoD error {device['device_id']}: {e}")

def end_of_day_task():
    logger.info("🧹 Starting EoD task for all devices...")
    tg_send_safe(
        f"🧹 <b>Starting End-of-Day</b>\n\n"
        f"🕒 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🖥️ <b>Devices:</b> {len(DEVICES)}"
    )
    ok, fail = 0, 0
    for d in DEVICES:
        try:
            fetch_end_of_day_logs(d)
            ok += 1
        except Exception as e:
            fail += 1
            logger.error(f"❌ EoD task error for device {d['device_id']}: {e}")
            tg_send_safe(
                f"❌ <b>Device Error (EoD)</b>\n\n"
                f"🖥️ <b>Device:</b> {d['device_id']}\n"
                f"❌ <b>Error:</b> {str(e)}"
            )
    tg_send_safe(
        f"🧹 <b>EoD Complete</b>\n\n"
        f"✅ <b>OK:</b> {ok}\n"
        f"❌ <b>Failed:</b> {fail}\n"
        f"🖥️ <b>Total:</b> {len(DEVICES)}"
    )
    logger.info("🧹 EoD task complete.")

# =========================
# Real-time capture
# =========================

def capture_real_time_logs(device, shared_buffer, periodic_flush_s=60):
    """
    Process: connect to device and stream logs into shared_buffer.
    Periodically flush to server even if BUFFER_LIMIT not reached.
    """
    device_id = device['device_id']
    ip_address = device['ip_address']
    port = device['port']

    logger.info(f"🔌 Starting RT capture for device {device_id} ({ip_address}:{port})")
    last_flush = time.time()

    try:
        zk = ZK(ip_address, port=port, timeout=50)
        log_device_status(device, "Connecting for RT capture...")
        conn = zk.connect()
        if not conn:
            log_device_status(device, "Failed to connect", "None returned")
            return

        try:
            conn.enable_device()
            log_device_status(device, "Connected", "Real-time capture active")

            # Optional: log device info
            try:
                info = conn.get_device_info()
                logger.info(f"ℹ️ Device {device_id} info: {info}")
            except Exception:
                logger.info(f"ℹ️ Device {device_id} connected (info unavailable)")

            for attendance in conn.live_capture():
                # live_capture can yield None; still tick periodic flush
                now = time.time()

                if attendance:
                    log_entry = {
                        "device_id": device_id,
                        "user_id": int(attendance.user_id),
                        "timestamp": attendance.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "status": attendance.status,
                        "punch": attendance.punch,
                    }
                    logger.info(f"🕘 New attendance: user {attendance.user_id} @ {log_entry['timestamp']} (Dev {device_id})")
                    shared_buffer.append(log_entry)

                    # size-based flush
                    if len(shared_buffer) >= BUFFER_LIMIT:
                        logger.info(f"📤 Buffer ≥ {BUFFER_LIMIT}, pushing...")
                        push_to_server(shared_buffer, device_id)

                # time-based flush
                if now - last_flush >= periodic_flush_s and len(shared_buffer) > 0:
                    logger.info(f"⏱️ Periodic flush ({len(shared_buffer)} recs)")
                    push_to_server(shared_buffer, device_id)
                    last_flush = now

        finally:
            try:
                conn.enable_device()
                conn.disconnect()
                log_device_status(device, "Disconnected from RT capture")
            except Exception as de:
                logging.warning(f"⚠️ Disconnect failed {device['device_id']}: {de}")

    except Exception as e:
        log_device_status(device, "Error during RT capture", str(e))
        logger.error(f"❌ RT capture error dev {device_id}: {e}")

# =========================
# Process orchestration
# =========================

def reconnect_devices(shared_buffer):
    """
    Spawn one process per device for RT capture.
    """
    logger.info("🔁 Spawning RT capture processes...")
    processes = []
    for d in DEVICES:
        logger.info(f"▶️ Starting process for device {d['device_id']}")
        p = Process(target=capture_real_time_logs, args=(d, shared_buffer))
        p.start()
        processes.append(p)
        logger.info(f"✅ Process started dev {d['device_id']} (PID {p.pid})")
    logger.info(f"✅ All {len(processes)} device processes started")
    return processes

def stop_processes(processes, join_timeout=5):
    for p in processes:
        try:
            p.terminate()
        except Exception:
            pass
    for p in processes:
        try:
            p.join(timeout=join_timeout)
        except Exception:
            pass

# =========================
# Main
# =========================

def main():
    logger.info("🚀 Boot checks: waiting for network/DNS...")
    if not wait_for_network(120):
        logger.warning("Network/DNS not ready after 120s; continuing anyway...")
    else:
        logger.info("✅ Network/DNS looks OK")

    device_hosts = [d["ip_address"] for d in DEVICES]
    logger.info("🔎 Waiting for at least one device to respond to ping...")
    if not any_device_ping_ok(device_hosts, 60):
        logger.warning("No devices responded to ping within 60s; continuing anyway...")
    else:
        logger.info("✅ Ping OK for at least one device")

    tg_send_safe(
        f"🚀 <b>Attendance ZTech Started</b>\n\n"
        f"🕒 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🖥️ <b>Devices:</b> {len(DEVICES)}\n"
        f"🌐 <b>Endpoint:</b> {ENDPOINT}\n"
        f"📦 <b>Buffer:</b> {BUFFER_LIMIT}"
    )

    with Manager() as manager:
        shared_buffer = manager.list()
        logger.info("🧺 Shared buffer ready")

        processes = reconnect_devices(shared_buffer)
        logger.info("🔗 Initial device connections done")

        last_reconnect = time.time()
        last_eod_run_date = None  # ensure EoD runs once/day

        try:
            logger.info("⏰ Entering main loop...")
            while True:
                now = datetime.now()

                # Scheduled reconnect every 15 minutes
                if time.time() - last_reconnect >= 15 * 60:
                    logger.info("🔁 Scheduled 15-min reconnect...")
                    stop_processes(processes)
                    processes = reconnect_devices(shared_buffer)
                    last_reconnect = time.time()

                # End-of-day at ~23:59 once per day
                if now.hour == 23 and now.minute == 59:
                    if last_eod_run_date != date.today():
                        logger.info("🧹 EoD window detected; running EoD task...")
                        try:
                            end_of_day_task()
                        except Exception as e:
                            logger.error(f"❌ EoD task error: {e}")
                        last_eod_run_date = date.today()
                        time.sleep(60)  # avoid multiple runs in the same minute

                # Periodic flush safeguard in main (in case device processes died)
                if len(shared_buffer) >= BUFFER_LIMIT:
                    logger.info("📤 Main loop flush due to size")
                    push_to_server(shared_buffer)

                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("⏹️ Terminated by user")
            tg_send_safe(
                f"⏹️ <b>System Shutdown</b>\n\n"
                f"🕒 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"📝 <b>Reason:</b> KeyboardInterrupt"
            )
        except Exception as e:
            logger.error(f"❌ Unexpected error in main loop: {e}")
            tg_send_safe(
                f"❌ <b>System Error</b>\n\n"
                f"🕒 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"❌ <b>Error:</b> {str(e)}"
            )
        finally:
            logger.info("🛑 Stopping device processes...")
            stop_processes(processes)

            # Final flush if anything pending
            if len(shared_buffer) > 0:
                logger.info(f"📤 Final flush of {len(shared_buffer)} records...")
                push_to_server(shared_buffer)

            logger.info("👋 Attendance ZTech stopped")
            tg_send_safe(
                f"👋 <b>System Stopped</b>\n\n"
                f"🕒 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🔌 <b>Status:</b> All processes terminated"
            )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("⏹️ Script terminated by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)