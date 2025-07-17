# YTPI - YouTube Downloader API

## Overview
YTPI is a Flask-based API that allows users to download YouTube videos using `yt-dlp`. It supports both single URL downloads and batch downloads via an array of URLs. The downloaded videos are stored in the `downloads/` directory.

## Features
- Restricts access to local clients based on IP address.
- Supports single and batch URL downloads.
- Provides job status updates via API.
- Embeds metadata into downloaded videos.

## Endpoints

### `/download` (POST)
**Description:** Enqueue a download job.

**Request Body:**
- Single URL:
  ```json
  {"url": "https://youtube.com/watch?v=example"}
  ```
- Multiple URLs:
  ```json
  {"urls": ["https://youtube.com/watch?v=example1", "https://youtube.com/watch?v=example2"]}
  ```

**Response:**
- Single URL:
  ```json
  {"job_id": "<job_id>"}
  ```
- Multiple URLs:
  ```json
  {"job_ids": ["<job_id1>", "<job_id2>"]}
  ```

### `/status` (GET)
**Description:** Render a dashboard showing the status of all jobs.

### `/api/status` (GET)
**Description:** Get the status of all jobs in JSON format.

**Response:**
```json
{
  "<job_id>": {
    "url": "<video_url>",
    "status": "queued|downloading|finished|error",
    "error": "<error_message_if_any>"
  }
}
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
