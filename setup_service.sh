#!/bin/bash

# Setup script for ytpi service on Raspberry Pi
# Run this script as the pi user

set -e

echo "Setting up ytpi service on Raspberry Pi..."

# Create app directory
YTPI_DIR="/home/pi/ytpi"
mkdir -p "$YTPI_DIR"
mkdir -p "$YTPI_DIR/downloads"

# Copy files (assuming you're running this from the ytpi directory)
cp app.py "$YTPI_DIR/"
cp requirements.txt "$YTPI_DIR/"
cp -r templates "$YTPI_DIR/" 2>/dev/null || echo "No templates directory found"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv "$YTPI_DIR/venv"
source "$YTPI_DIR/venv/bin/activate"

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r "$YTPI_DIR/requirements.txt"

# Install yt-dlp
echo "Installing yt-dlp..."
pip install yt-dlp

# Make sure downloads directory exists and is writable
chmod 755 "$YTPI_DIR/downloads"

# Copy service file and install it
echo "Installing systemd service..."
sudo cp ytpi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ytpi.service

echo "Setup complete!"
echo ""
echo "To start the service:"
echo "  sudo systemctl start ytpi"
echo ""
echo "To check service status:"
echo "  sudo systemctl status ytpi"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u ytpi -f"
echo ""
echo "The service will start automatically on boot."
echo "Your app will be available at http://your-pi-ip:7434"
