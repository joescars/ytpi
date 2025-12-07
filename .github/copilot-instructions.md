# GitHub Copilot Instructions for ytpi

## Project Overview

ytpi (YouTube Downloader API) is a Flask-based web service designed to download YouTube videos using yt-dlp. It's designed to run on Raspberry Pi with local network access only for security.

**Key Features:**
- Download single or multiple YouTube videos
- Queue-based processing with background worker thread
- Web dashboard to monitor downloads
- RESTful API
- Local network access only (security feature)
- Support for playlists and individual videos
- Quality selection (max, 2160, 1440, 1080, 720, 480)
- Category-based file organization
- iOS Share Sheet integration

## Technology Stack

- **Backend:** Python 3.11+ with Flask
- **Video Processing:** yt-dlp with ffmpeg
- **Frontend:** HTML templates with Jinja2
- **Deployment:** 
  - Systemd service (native)
  - Docker/Docker Compose (containerized)
- **Target Platform:** Raspberry Pi (also supports x86/ARM64)

## Development Environment Setup

1. **Prerequisites:**
   - Python 3.11 or higher
   - ffmpeg (required by yt-dlp)
   - pip

2. **Local Development:**
   ```bash
   # Create virtual environment
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Run the application
   python app.py
   ```

3. **Docker Development:**
   ```bash
   # Build and run
   docker compose up -d --build
   
   # View logs
   docker compose logs -f
   
   # Stop
   docker compose down
   ```

## Project Structure

```
ytpi/
├── .github/
│   ├── workflows/          # CI/CD workflows
│   └── copilot-instructions.md
├── templates/              # Jinja2 HTML templates
│   ├── index.html         # Main form page
│   ├── dashboard.html     # Status dashboard
│   └── shared_success.html # iOS share confirmation
├── static/                 # Static assets (CSS, JS, images)
├── downloads/              # Video download directory (created at runtime)
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container image definition
├── docker-compose.yml    # Docker Compose configuration
├── .dockerignore         # Docker build exclusions
└── README.md             # Documentation

Archived/Legacy:
├── _archived/            # Old versions and deprecated code
```

## Code Architecture

### Main Application (app.py)

1. **Security Layer:**
   - `ALLOWED_PREFIXES`: Defines allowed network ranges (localhost, private networks)
   - `is_local()`: Validates client IP addresses
   - `@app.before_request`: Flask decorator enforcing local-only access

2. **Quality Validation:**
   - `ALLOWED_QUALITIES`: Set of valid quality values
   - `validate_quality()`: Ensures quality parameter is valid
   - `get_and_validate_quality()`: Extracts and validates quality from input

3. **Background Processing:**
   - `download_queue`: Thread-safe queue for pending downloads
   - `jobs`: Dictionary tracking job status and metadata
   - `worker()`: Background thread processing download queue
   - Uses subprocess.Popen for live output capture

4. **API Endpoints:**
   - `POST /download`: Queue video downloads (JSON or form data)
   - `GET /share`: Queue via query string (iOS Shortcut integration)
   - `GET /status`: Web dashboard
   - `GET /api/status`: JSON status of all jobs
   - `GET /job_output/<job_id>`: Live job output
   - `GET /`: Home page with download form

## Coding Standards and Conventions

### Python Style
- Follow PEP 8 style guidelines
- Use 4 spaces for indentation
- Keep functions focused and single-purpose
- Use descriptive variable names

### Security Requirements
- **CRITICAL:** Never expose this service to public internet
- Always validate and sanitize user inputs
- Maintain IP address restrictions in `ALLOWED_PREFIXES`
- Use parameter validation for quality, category, and URLs
- Never log sensitive information

### Error Handling
- Catch exceptions in worker thread to prevent crashes
- Store error messages in job dictionary
- Return appropriate HTTP status codes (400, 403, 404, 500)
- Provide user-friendly error messages

### Threading and Concurrency
- Use thread-safe queue for job management
- Single daemon worker thread processes downloads
- Jobs dictionary tracks all job states
- No shared mutable state between requests

## Testing

**Note:** This project currently has no automated test suite. When adding tests:

1. Use pytest as the testing framework
2. Create test files in a `tests/` directory
3. Name test files as `test_*.py`
4. Test key functionality:
   - IP address validation
   - Quality parameter validation
   - URL parsing and validation
   - Job queue management
   - API endpoint responses

## Build and Deployment

### Native Deployment (Raspberry Pi)
- Uses systemd service (`ytpi.service`)
- Managed via `setup_service.sh` script
- Virtual environment in `/home/runneruser/services/ytpi`

### Docker Deployment
```bash
# Build
docker build -t ytpi:latest .

# Run with volume mount
docker run --rm -p 7434:7434 -v ./downloads:/app/downloads ytpi:latest

# Or use docker-compose
docker compose up -d --build
```

### CI/CD Workflows
- `default.yml`: Deploys to Raspberry Pi via self-hosted runner
- `docker-workflow.yml`: Builds and runs Docker container
- Both triggered via `workflow_dispatch` (manual trigger)

## Key Dependencies

From `requirements.txt`:
- **Flask>=2.0**: Web framework
- **yt-dlp>=2023.1.6**: YouTube video downloader

Runtime dependency:
- **ffmpeg**: Required by yt-dlp for video processing

## Common Tasks

### Adding a New Endpoint
1. Define route with `@app.route()`
2. Add IP validation (automatically handled by `@app.before_request`)
3. Validate input parameters
4. Return appropriate response with status code
5. Update README.md with API documentation

### Modifying Download Logic
1. Locate the `worker()` function
2. Modify yt-dlp command arguments as needed
3. Ensure error handling remains robust
4. Test with both single videos and playlists

### Adding New Quality Options
1. Add to `ALLOWED_QUALITIES` set
2. Update format string logic in `worker()` function
3. Document in README.md

### Extending Network Access
1. **WARNING:** Only do this if you understand security implications
2. Add IP prefix to `ALLOWED_PREFIXES` tuple
3. Document the change and reason

## File Naming and Organization

- Templates: Use descriptive names (e.g., `dashboard.html`, `shared_success.html`)
- Static files: Organize by type in `static/` subdirectories
- Downloaded videos: Organized by category in `downloads/<category>/`
- Playlists: Stored in `downloads/<category>/<playlist_name>/`

## Important Notes

1. **Security First:** This application is designed for local network use only
2. **No External Dependencies:** Avoid adding unnecessary Python packages
3. **Minimal Changes:** Keep code simple and maintainable
4. **Raspberry Pi Focus:** Consider ARM compatibility for dependencies
5. **Background Processing:** Single worker thread is sufficient for typical use
6. **No Persistence:** Jobs dictionary is in-memory (cleared on restart)

## When Making Changes

1. **Test locally** before committing
2. **Verify IP restrictions** still work
3. **Check Docker build** if modifying dependencies
4. **Update README.md** if changing API or functionality
5. **Consider backward compatibility** with iOS Shortcuts
6. **Validate quality parameters** if modifying download logic

## Resources

- Flask Documentation: https://flask.palletsprojects.com/
- yt-dlp Documentation: https://github.com/yt-dlp/yt-dlp
- Docker Documentation: https://docs.docker.com/
