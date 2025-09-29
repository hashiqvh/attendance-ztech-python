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

def main():
    # Calculate date range
    to_date = datetime.date.today()
    from_date = to_date - datetime.timedelta(days=30)

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

    print(f"Running 30-day boot sync: {from_date} -> {to_date}")
    sys.stdout.flush()

    # Run sync_all.py as a subprocess
    try:
        subprocess.check_call(cmd)
        print("Boot sync finished successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Boot sync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
