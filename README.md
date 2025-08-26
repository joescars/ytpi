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

## iOS Share Sheet Integration

You can send the current Safari page directly to ytpi using an iOS Shortcut from the Share Sheet.

### Option A: Simple Redirect Flow

- Create a Shortcut in the Shortcuts app.
- Actions:
  1) Get Details of Safari Web Page → URL
  2) URL → set to: `http://YOUR_PI_IP:7434/share?url={{Shortcut Input}}&category=Music%20Videos`
  3) Open URLs
- Use the Share Sheet → Send to ytpi.
- The server queues the job and redirects to `http://YOUR_PI_IP:7434/status?job=<id>`.

### Option B: In-Safari Confirmation Page

- Same as above, but use this URL so the app shows a small confirmation page and auto-redirects:

  `http://YOUR_PI_IP:7434/share?url={{Shortcut Input}}&category=Music%20Videos&redirect=0`

### Using POST (optional)

- If you prefer JSON POST, you can call the existing endpoint:
  - URL: `http://YOUR_PI_IP:7434/download`
  - Method: POST
  - Headers: `Content-Type: application/json`
  - JSON: `{ "url": Shortcut Input, "category": "Music Videos" }`

### Categories

- The `category` is optional. When provided, files are saved under `downloads/<category>/...`.

### Notes

- Your iPhone must be on the same LAN as the server (the app only allows local network clients).
- If you want a bit more protection, consider using a shared token in the query string and validate it.

## New Endpoints

### GET /share

Queue a single URL via query string. Useful for Shortcuts.

- Query params:
  - `url` (required): The video or playlist URL
  - `category` (optional): Subfolder name under `downloads`
  - `redirect` (optional, default `1`): `1|true|yes` → redirect to dashboard, otherwise return a friendly page (202)

- Examples:
  - `http://YOUR_PI_IP:7434/share?url=https://youtube.com/watch?v=abc123&category=Music%20Videos`
  - `http://YOUR_PI_IP:7434/share?url=https://youtube.com/watch?v=abc123&redirect=0`
