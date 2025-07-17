# YouTube Downloader API (ytpi)

A Flask-based web service for downloading YouTube videos using yt-dlp. Designed to run on Raspberry Pi with local network access only.

## Features

- Download single or multiple YouTube videos
- Queue-based processing
- Web dashboard to monitor downloads
- RESTful API
- Local network access only (security feature)
- Systemd service support for Raspberry Pi

## Installation on Raspberry Pi

1. **Transfer files to your Raspberry Pi:**
   ```bash
   # On your local machine, copy the project to your Pi
   scp -r ytpi/ pi@your-pi-ip:/home/pi/
   ```

2. **SSH into your Raspberry Pi:**
   ```bash
   ssh pi@your-pi-ip
   cd /home/pi/ytpi
   ```

3. **Run the setup script:**
   ```bash
   ./setup_service.sh
   ```

4. **Start the service:**
   ```bash
   sudo systemctl start ytpi
   ```

## Service Management

- **Start service:** `sudo systemctl start ytpi`
- **Stop service:** `sudo systemctl stop ytpi`
- **Restart service:** `sudo systemctl restart ytpi`
- **Check status:** `sudo systemctl status ytpi`
- **View logs:** `sudo journalctl -u ytpi -f`
- **Disable auto-start:** `sudo systemctl disable ytpi`

## API Usage

### Download Single Video
```bash
curl -X POST http://your-pi-ip:7434/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=VIDEO_ID"}'
```

### Download Multiple Videos
```bash
curl -X POST http://your-pi-ip:7434/download \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://youtube.com/watch?v=VIDEO1", "https://youtube.com/watch?v=VIDEO2"]}'
```

### Check Status
- Web dashboard: `http://your-pi-ip:7434/status`
- API endpoint: `http://your-pi-ip:7434/api/status`

## Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the app:**
   ```bash
   python app.py
   ```

The app will be available at `http://localhost:7434`

## Security

This service only accepts connections from local network addresses:
- 127.x.x.x (localhost)
- 192.168.x.x (private networks)
- 10.x.x.x (private networks)
- 172.16-31.x.x (private networks)

## File Structure

- `app.py` - Main Flask application
- `requirements.txt` - Python dependencies
- `ytpi.service` - Systemd service file
- `setup_service.sh` - Installation script for Raspberry Pi
- `templates/dashboard.html` - Web dashboard
- `downloads/` - Downloaded videos directory
```

## Installation

1. Clone the repository:
   ```bash
   git clone <repository_url>
   ```

2. Navigate to the project directory:
   ```bash
   cd ytpi
   ```

3. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Start the Flask server:
   ```bash
   python app.py
   ```

2. Access the API locally at `http://127.0.0.1:7434`.

## Notes
- Ensure `yt-dlp` is installed and accessible in your system's PATH.
- The `downloads/` directory is ignored by Git via `.gitignore`.

## License
This project is licensed under the MIT License.
