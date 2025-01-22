# Real-Time Attendance Logger

This project captures real-time attendance logs from ZK devices and pushes the data to a server. It also fetches and processes end-of-day attendance logs. The configuration is managed using a JSON file.

---

## Features

- Captures real-time attendance logs from multiple devices.
- Pushes logs to a server endpoint in JSON format.
- Fetches end-of-day attendance logs.
- Automatically reconnects to devices every 15 minutes to ensure data capture.
- Configurable via `config.json`.

---

## Requirements

- **Python**: Version 3.8 or later
- **ZK SDK**: For device communication (`zk-python`)
- **Additional Libraries**: Listed in `requirements.txt`

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/attendance-logger.git
cd attendance-logger
```

### Step 2: Set Up a Virtual Environment

Create and activate a virtual environment to isolate the dependencies for this project.

#### On Linux / macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

#### On Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies

Install all required Python libraries:

```bash
pip install -r requirements.txt
```

### Step 4: Configure `config.json`

Create the `config.json` file in the project root directory using the following sample:

#### Sample `config.json`

```json
{
  "log_level": "INFO",
  "endpoint": "https://example.com/erp-api/sync/empAttSync.php",
  "buffer_limit": 3,
  "devices": [
    { "device_id": 1, "ip_address": "10.30.141.3", "port": 4370 },
    { "device_id": 2, "ip_address": "10.30.141.4", "port": 4370 },
    { "device_id": 3, "ip_address": "10.30.141.5", "port": 4370 }
  ]
}
```

#### Configuration Details:

- **`log_level`**: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
- **`endpoint`**: Server API endpoint for syncing attendance data.
- **`buffer_limit`**: Number of logs to collect before pushing to the server.
- **`devices`**: List of devices with:
  - `device_id`: Unique identifier for the device.
  - `ip_address`: IP address of the device.
  - `port`: Port for communication (default is `4370`).

---

## Usage

### Running the Script

1. Activate the virtual environment:

   ```bash
   source venv/bin/activate       # On Linux/macOS
   venv\Scripts\activate        # On Windows
   ```

2. Run the script:
   ```bash
   python main.py
   ```

---

## Logs

Logs are printed to the console with timestamps and log levels. Example:

```
2025-01-22 13:45:23 - INFO - Connecting to device 1...
2025-01-22 13:45:30 - INFO - Captured log: {'device_id': 1, 'user_id': 123, 'timestamp': '2025-01-22 13:45:30', 'status': 1, 'punch': 1}
2025-01-22 13:46:00 - INFO - Pushing 3 records to the server.
```

---

## Features in Detail

### Real-Time Log Capture

- Real-time logs are captured and stored in a shared buffer.
- Logs are pushed to the server when the buffer reaches the `buffer_limit`.

### End-of-Day Task

- The script fetches logs for the current day at the end of the day (`23:59`).
- Ensures all attendance data is pushed before the next day starts.

### Reconnection Mechanism

- Devices are reconnected every 15 minutes to handle disconnections.
- This ensures continuous data collection without manual intervention.

---

## Development and Testing

### Running Tests

Write and run unit tests for the script using the `unittest` module or your preferred testing framework.

### Modifying Configuration

Update the `config.json` file to:

- Add new devices.
- Change the endpoint URL.
- Adjust the buffer limit or logging level.

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

**Author:** [Hashiq V H]
