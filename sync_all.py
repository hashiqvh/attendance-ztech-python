#!/usr/bin/env python3
import argparse
import logging
import json
from datetime import datetime
from typing import List, Iterable, Optional
import time

import httpx
from zk import ZK

# -----------------------------
# CLI
# -----------------------------
def parse_args():
    p = argparse.ArgumentParser(
        description="Full sync of all attendance logs from ZKTeco devices to API."
    )
    p.add_argument(
        "--from",
        dest="from_date",
        help="Start date (YYYY-MM-DD). If omitted, fetch all available logs.",
    )
    p.add_argument(
        "--to",
        dest="to_date",
        help="End date (YYYY-MM-DD). If omitted, up to now.",
    )
    p.add_argument(
        "--device-id",
        type=int,
        help="Only sync a specific device_id from config.json.",
    )
    p.add_argument(
        "--chunk",
        type=int,
        default=500,
        help="Batch size to push per request (default: 500).",
    )
    p.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Number of retries per HTTP batch (default: 3).",
    )
    p.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override log level for this run.",
    )
    return p.parse_args()


# -----------------------------
# Helpers
# -----------------------------
def load_config() -> dict:
    with open("config.json", "r") as f:
        return json.load(f)


def setup_logging(level_name: Optional[str], config: dict):
    level_str = level_name or config.get("log_level", "INFO")
    logging.basicConfig(
        level=getattr(logging, level_str.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_date(d: Optional[str]) -> Optional[datetime]:
    if not d:
        return None
    return datetime.strptime(d, "%Y-%m-%d")


def in_range(ts: datetime, start: Optional[datetime], end: Optional[datetime]) -> bool:
    if start and ts < start:
        return False
    if end and ts > end:
        return False
    return True


def chunked(iterable: List[dict], size: int):
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def push_batch(endpoint: str, batch: Iterable[dict], retries: int = 3, timeout: int = 60) -> bool:
    payload = {"Json": list(batch)}
    attempt = 0
    backoff = 2
    while attempt <= retries:
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(endpoint, json=payload, headers={"Content-Type": "application/json"})
            if resp.status_code == 200:
                logging.info(f"Pushed {len(payload['Json'])} records successfully.")
                return True
            else:
                logging.error(f"Push failed (status {resp.status_code}): {resp.text}")
        except Exception as e:
            logging.error(f"HTTP push error: {e}")
        attempt += 1
        if attempt <= retries:
            logging.info(f"Retrying in {backoff}s (attempt {attempt}/{retries})...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
    return False


def collect_device_logs(device: dict) -> List[dict]:
    """
    Fetch ALL logs from device using ZK SDK.
    Return as list of dicts (unfiltered).
    """
    zk = ZK(
        device["ip_address"],
        port=device.get("port", 4370),
        timeout=device.get("timeout", 100),
        password=device.get("password", 0),
        force_udp=device.get("force_udp", False),
        ommit_ping=device.get("ommit_ping", False),
    )
    conn = None
    try:
        logging.info(f"[{device['device_id']}] Connecting to device {device['ip_address']}...")
        conn = zk.connect()
        conn.enable_device()
        logging.info(f"[{device['device_id']}] Connected. Gathering logs...")

        logs = conn.get_attendance()
        if not logs:
            logging.info(f"[{device['device_id']}] No logs found.")
            return []

        out = []
        for log in logs:
            try:
                out.append(
                    {
                        "device_id": device["device_id"],
                        "user_id": int(log.user_id),
                        "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        "status": log.status,
                        "punch": log.punch,
                    }
                )
            except Exception as e:
                logging.warning(f"[{device['device_id']}] Skipping a malformed log: {e}")
        logging.info(f"[{device['device_id']}] Retrieved {len(out)} logs.")
        return out

    except Exception as e:
        logging.error(f"[{device['device_id']}] Error collecting logs: {e}")
        return []
    finally:
        if conn is not None:
            try:
                conn.enable_device()
                conn.disconnect()
                logging.info(f"[{device['device_id']}] Disconnected.")
            except Exception as e:
                logging.warning(f"[{device['device_id']}] Disconnect issue: {e}")


def main():
    args = parse_args()
    config = load_config()
    setup_logging(args.log_level, config)

    endpoint = config["endpoint"]
    devices = config["devices"]
    if args.device_id is not None:
        devices = [d for d in devices if d.get("device_id") == args.device_id]
        if not devices:
            logging.error(f"No device with device_id={args.device_id} found in config.json.")
            return

    start_dt = parse_date(args.from_date)
    end_dt = parse_date(args.to_date)
    chunk_size = max(1, args.chunk)

    total_pushed = 0
    for device in devices:
        # 1) Collect all logs
        raw_logs = collect_device_logs(device)
        if not raw_logs:
            continue

        # 2) Filter by date range if provided
        if start_dt or end_dt:
            filtered = []
            for rec in raw_logs:
                try:
                    ts = datetime.strptime(rec["timestamp"], "%Y-%m-%d %H:%M:%S")
                    if in_range(ts, start_dt, end_dt):
                        filtered.append(rec)
                except Exception as e:
                    logging.warning(f"[{device['device_id']}] Timestamp parse error, skipping record: {e}")
            logs = filtered
            logging.info(f"[{device['device_id']}] Filtered logs count: {len(logs)}")
        else:
            logs = raw_logs

        # 3) Sort by timestamp (optional but nice)
        try:
            logs.sort(key=lambda r: r["timestamp"])
        except Exception:
            pass

        # 4) Push in batches
        if not logs:
            logging.info(f"[{device['device_id']}] Nothing to push after filtering.")
            continue

        for i, batch in enumerate(chunked(logs, chunk_size), start=1):
            logging.info(f"[{device['device_id']}] Pushing batch {i} ({len(batch)} records)...")
            ok = push_batch(endpoint, batch, retries=args.retries)
            if not ok:
                logging.error(f"[{device['device_id']}] Aborting further batches due to repeated push failures.")
                break
            total_pushed += len(batch)

    logging.info(f"SYNC COMPLETE. Total records pushed: {total_pushed}")


if __name__ == "__main__":
    main()
