# Manual Installation Instructions for Raspberry Pi

If you prefer to set up the service manually instead of using the setup script:

## Step 1: Prepare the Environment

```bash
# Update your Pi
sudo apt update && sudo apt upgrade -y

# Install required system packages
sudo apt install python3-pip python3-venv -y

# Create the application directory
sudo mkdir -p /home/pi/ytpi
sudo chown pi:pi /home/pi/ytpi
cd /home/pi/ytpi
```

## Step 2: Set Up the Application

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install Flask yt-dlp

# Create downloads directory
mkdir -p downloads
```

## Step 3: Copy Your Files

Transfer your application files to `/home/pi/ytpi/`:
- `app.py`
- `templates/` directory (if you have dashboard templates)

## Step 4: Create the Service File

```bash
sudo nano /etc/systemd/system/ytpi.service
```

Paste the following content:

```ini
[Unit]
Description=YouTube Video Downloader Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/ytpi
Environment=PATH=/home/pi/ytpi/venv/bin
ExecStart=/home/pi/ytpi/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Step 5: Enable and Start the Service

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable ytpi.service

# Start the service
sudo systemctl start ytpi.service

# Check the service status
sudo systemctl status ytpi.service
```

## Step 6: Verify Installation

Your service should now be running on port 7434. You can:

1. Check the web interface: `http://your-pi-ip:7434/status`
2. Test the API with curl:
   ```bash
   curl -X POST http://your-pi-ip:7434/download \
     -H "Content-Type: application/json" \
     -d '{"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"}'
   ```

## Troubleshooting

- **View logs:** `sudo journalctl -u ytpi -f`
- **Restart service:** `sudo systemctl restart ytpi`
- **Check if port is in use:** `sudo netstat -tlnp | grep 7434`
