# Development Environment for ytpi

This folder contains the devcontainer configuration for the ytpi project, providing a consistent development environment using Docker and VS Code.

## Quick Start

1. **Prerequisites:**
   - [VS Code](https://code.visualstudio.com/)
   - [Docker Desktop](https://www.docker.com/products/docker-desktop)
   - [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

2. **Open in devcontainer:**
   - Open this project in VS Code
   - When prompted, click "Reopen in Container" 
   - Or use Command Palette (Ctrl/Cmd+Shift+P) → "Dev Containers: Rebuild and Reopen in Container"

3. **Start development:**
   - The Flask app will be available at http://localhost:7434
   - Use F5 to start debugging or run `python app.py` in the terminal

## What's Included

### Development Tools
- Python 3.11 with pip
- ffmpeg (required by yt-dlp)
- Git and GitHub CLI
- Common development utilities (vim, nano, htop, tree, jq)

### Python Packages
- Flask and yt-dlp (from requirements.txt)
- Development tools: pylint, black, flake8, autopep8
- Testing framework: pytest, pytest-flask

### VS Code Extensions
- Python language support with debugging
- Code formatting and linting
- Test explorer integration
- Live server support

### Configuration
- **Port 7434** automatically forwarded for Flask app access
- **Persistent volume** for downloads directory
- **Python debugging** configured for Flask app
- **Code formatting** with Black
- **Linting** with pylint and flake8

## Project Structure

The devcontainer mounts your workspace to `/workspace` and creates the following structure:

```
/workspace/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── templates/          # Jinja2 templates
├── static/            # Static assets
├── downloads/         # Persistent download directory (volume)
└── .devcontainer/     # This devcontainer configuration
```

## Development Workflow

1. **Run the app:** Use F5 to start with debugging, or `python app.py` in terminal
2. **Access the app:** http://localhost:7434 (automatically forwarded)
3. **View downloads:** Files are saved in `downloads/` directory (persistent volume)
4. **Code formatting:** Save files to auto-format with Black
5. **Testing:** Use Test Explorer or run `pytest` in terminal

## Debugging

The devcontainer includes a pre-configured debugger:
- Use F5 to start debugging the Flask app
- Set breakpoints in your code
- Use the Debug Console for interactive debugging

## Persistent Data

Downloads are stored in a Docker volume named `ytpi-downloads` which persists across container rebuilds. This means your downloaded videos won't be lost when you recreate the devcontainer.

## Troubleshooting

### Container won't start
- Ensure Docker Desktop is running
- Try "Dev Containers: Rebuild Container (No Cache)" from Command Palette

### Port 7434 is unavailable
- Check if another service is using port 7434
- The devcontainer will automatically forward the port when the container starts

### Missing dependencies
- The postCreateCommand should install requirements automatically
- If needed, run `pip install -r requirements.txt` manually

### ffmpeg not found
- ffmpeg is installed in the container during build
- If issues persist, try rebuilding the container without cache