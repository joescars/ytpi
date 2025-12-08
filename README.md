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
# Basic download (max quality, no category)
curl -X POST http://your-pi-ip:7434/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=VIDEO_ID"}'

# With category and quality
curl -X POST http://your-pi-ip:7434/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=VIDEO_ID", "category": "Music Videos", "quality": "1080"}'
```

### Download Multiple Videos

```bash
curl -X POST http://your-pi-ip:7434/download \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://youtube.com/watch?v=VIDEO1", "https://youtube.com/watch?v=VIDEO2"], "quality": "720"}'
```

### Check Status

- Web dashboard: `http://your-pi-ip:7434/status`
- API endpoint: `http://your-pi-ip:7434/api/status`

### Quality Options

Valid quality values:
- `max` - Best available quality (default)
- `2160` - 4K (2160p)
- `1440` - 2K (1440p)
- `1080` - Full HD (1080p)
- `720` - HD (720p)
- `480` - Standard (480p)

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

## Containerization

You can run this application in Docker without modifying `app.py`.

### Build Image

```powershell
docker build -t ytpi:latest .
```

### Run Container (bind mount downloads for persistence)

```powershell
mkdir downloads 2>$null
docker run --rm -p 7434:7434 -v "${PWD}/downloads:/app/downloads" ytpi:latest
```

Access at: `http://localhost:7434`

### Using docker-compose

```powershell
docker compose up -d --build
```

### Production Notes

- The image installs `ffmpeg` (needed by `yt-dlp`).
- A volume at `/app/downloads` persists your files.
- Multiple containers do not share the in-memory queue (`jobs`). For scaling, use an external queue (e.g., Redis) and refactor accordingly.
- For a production WSGI server without changing code, you may add `waitress` to `requirements.txt` and change the container command to:

   ```bash
   waitress-serve --listen=0.0.0.0:7434 app:app
   ```

### Cleanup

```powershell
docker compose down
```

### Optional Enhancements (future)

- Environment variable for allowed IP prefixes
- Health endpoint (`/healthz`)
- Structured logging
- External persistence for job history

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

You can easily download YouTube videos directly from Safari or any app on your iPhone/iPad by sharing the URL to ytpi. This integration uses iOS Shortcuts and works seamlessly with the Share Sheet.

### Quick Setup (Recommended)

This is the simplest setup that uses default settings (max quality, no category organization):

1. **Open the Shortcuts app** on your iPhone/iPad
2. **Create a new Shortcut** (tap the + button)
3. **Name your shortcut** (e.g., "Download to ytpi" or "Save Video")
4. **Add these actions:**
   - Tap "Add Action" → Search for "Get Details of Safari Web Page"
   - Select "URL" from the dropdown
   - Tap "+" again → Search for "URL"
   - In the URL field, enter: `http://YOUR_PI_IP:7434/share?url=`
   - Tap after the `=` and select "Safari Web Page URL" from the Variables menu
   - Tap "+" again → Search for "Open URLs"
   - Select "URL" as the input
5. **Configure sharing:**
   - Tap the settings icon (⚙️) at the bottom of the shortcut
   - Enable "Show in Share Sheet"
   - Under "Share Sheet Types," enable "URLs" and "Safari Web Pages"
6. **Save the shortcut**

**Usage:** When you're on a YouTube page in Safari (or any app), tap the Share button, scroll down to find your "Download to ytpi" shortcut, and tap it. The video will be queued for download at max quality in your downloads folder.

### Setup with Category Organization (Optional)

If you want to organize downloads into categories (e.g., "Music Videos", "Tutorials", etc.):

Follow the same steps as above, but in step 4, use this URL instead:
```
http://YOUR_PI_IP:7434/share?url=SAFARI_WEB_PAGE_URL&category=YOUR_CATEGORY
```
Replace `YOUR_CATEGORY` with your desired folder name (e.g., `Music%20Videos` for "Music Videos").

**Note:** Use `%20` for spaces in category names, or use hyphens like `Music-Videos`.

### Advanced Options

#### Option A: Auto-redirect to Dashboard
The default behavior redirects you to the status dashboard after queuing the download:
```
http://YOUR_PI_IP:7434/share?url=SAFARI_WEB_PAGE_URL
```

#### Option B: Show Confirmation Page
To see a simple confirmation page in Safari instead of redirecting:
```
http://YOUR_PI_IP:7434/share?url=SAFARI_WEB_PAGE_URL&redirect=0
```

#### Option C: Specify Video Quality
To download at a specific quality instead of max quality:
```
http://YOUR_PI_IP:7434/share?url=SAFARI_WEB_PAGE_URL&quality=1080
```
Valid quality values: `max`, `2160` (4K), `1440` (2K), `1080` (Full HD), `720` (HD), `480`

#### Using POST Method (Advanced)
If you prefer using the POST endpoint:
- URL: `http://YOUR_PI_IP:7434/download`
- Method: POST
- Headers: `Content-Type: application/json`
- Body: `{"url": "SAFARI_WEB_PAGE_URL"}`

### Important Notes

- **Network Requirement:** Your iPhone/iPad must be on the same local network (LAN) as your ytpi server. The app only accepts connections from local network addresses for security.
- **Replace YOUR_PI_IP:** Make sure to replace `YOUR_PI_IP` with your actual server IP address (e.g., `192.168.1.100`)
- **Default Settings:** When no category or quality is specified, videos are saved to the root downloads folder at max quality
- **Works with Playlists:** You can share YouTube playlist URLs the same way - the entire playlist will be downloaded

## API Endpoints

### GET /share

Queue a single URL via query string. Optimized for iOS Shortcuts and Share Sheet integration.

**Query Parameters:**
- `url` (required): The YouTube video or playlist URL
- `category` (optional): Subfolder name under `downloads/`. If not specified, files are saved to the root downloads folder
- `quality` (optional, default `max`): Video quality. Valid values: `max`, `2160`, `1440`, `1080`, `720`, `480`
- `redirect` (optional, default `1`): Controls redirect behavior
  - `1`, `true`, or `yes`: Redirects to the status dashboard
  - `0`, `false`, or `no`: Shows a friendly confirmation page

**Examples:**
```bash
# Basic usage with defaults (max quality, no category)
http://YOUR_PI_IP:7434/share?url=https://youtube.com/watch?v=abc123

# With category organization
http://YOUR_PI_IP:7434/share?url=https://youtube.com/watch?v=abc123&category=Music%20Videos

# With specific quality
http://YOUR_PI_IP:7434/share?url=https://youtube.com/watch?v=abc123&quality=1080

# Show confirmation page instead of redirecting
http://YOUR_PI_IP:7434/share?url=https://youtube.com/watch?v=abc123&redirect=0

# All options combined
http://YOUR_PI_IP:7434/share?url=https://youtube.com/watch?v=abc123&category=Tutorials&quality=720&redirect=0
```

**Response:**
- With redirect: HTTP 302 redirect to `/status?job=<job_id>`
- Without redirect: HTTP 202 with HTML confirmation page
