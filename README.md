# Attendance ZTech System for Windows

A comprehensive attendance management system that connects to ZKTeco devices and syncs attendance data to a server.

## 🚀 Quick Start

### 1. Install Python
- Download Python 3.7+ from [python.org](https://www.python.org/downloads/)
- **Important**: Check "Add Python to PATH" during installation

### 2. Install the System
- Right-click `install_service.bat` and select "Run as administrator"
- The script will automatically:
  - Install Python dependencies
  - Set up Windows service
  - Create desktop shortcuts
  - Start the system

## 📁 System Files

- `main.py` - Main attendance system
- `config.json` - Device and server configuration
- `windows_service.py` - Windows service wrapper
- `install_service.bat` - Installation script
- `view_logs.bat` - Log viewer and device status
- `requirements.txt` - Python dependencies

## 🔧 Configuration

Edit `config.json` to configure your devices and server:

```json
{
  "endpoint": "http://your-server.com/api/attendance",
  "buffer_limit": 100,
  "devices": [
    {
      "device_id": "Device001",
      "ip_address": "192.168.1.100",
      "port": 4370
    }
  ],
  "log_level": "INFO"
}
```

## 📊 Monitoring and Logs

### View Logs and Device Status
- Double-click "View Logs" desktop shortcut, or
- Run `C:\Program Files\AttendanceZTech\view_logs.bat`

### Log Locations
- **System logs**: `C:\ProgramData\AttendanceZTech\logs\`
- **Desktop logs**: `Desktop\AttendanceZTech Logs\`
- **Local log**: `log.txt` (in program directory)

### What You Can Monitor
1. **Device Connection Status** - See if devices are connected
2. **Recent Attendance Logs** - View latest attendance records
3. **System Service Status** - Check if service is running
4. **Live Log Monitor** - Real-time log viewing
5. **All Logs** - Comprehensive log review

## 🔄 Windows Service

The system runs as a Windows service that:
- Starts automatically on Windows boot
- Restarts automatically if it crashes
- Runs in the background
- Logs all activities

### Service Management
```cmd
# Start service
net start AttendanceZTechService

# Stop service
net stop AttendanceZTechService

# Check status
sc query AttendanceZTechService
```

## 📱 Desktop Shortcuts

After installation, you'll have:
- **Attendance ZTech** - Start the system manually
- **View Logs** - Check logs and device status

## 🚨 Troubleshooting

### System Won't Start
1. Check if Python is installed: `python --version`
2. Run `install_service.bat` as administrator
3. Check Windows Event Viewer for errors

### Can't See Logs
1. Check `Desktop\AttendanceZTech Logs\` folder
2. Run `view_logs.bat` to see all logs
3. Check Windows service status

### Device Connection Issues
1. Verify device IP and port in `config.json`
2. Check network connectivity
3. Ensure device is powered on and accessible

### Service Issues
1. Run as administrator
2. Check Windows Event Viewer
3. Reinstall service: `python windows_service.py remove` then reinstall

## 📋 System Features

- **Real-time attendance capture** from ZKTeco devices
- **Automatic data synchronization** to server
- **End-of-day log fetching** for complete data
- **Automatic reconnection** every 15 minutes
- **Comprehensive logging** with multiple outputs
- **Windows service** for reliability
- **Auto-startup** on system boot
- **Easy log viewing** with dedicated tools

## 🔍 Log Types

- **Service logs** - Windows service operations
- **Attendance logs** - Device connection and attendance data
- **Error logs** - Connection issues and errors
- **System logs** - General system information

## 📞 Support

If you encounter issues:
1. Check the logs using `view_logs.bat`
2. Verify Python and dependencies are installed
3. Ensure you're running as administrator
4. Check Windows Event Viewer for system errors

## 🆕 Updates

To update the system:
1. Replace the files in your installation folder
2. Run `install_service.bat` again as administrator
3. The service will be updated automatically
