#!/bin/bash
# Install Movie Browser as a systemd service on Raspberry Pi / Linux

set -e

echo "=== Movie Browser Service Installer ==="
echo ""

# Get current user and home directory
CURRENT_USER=$(whoami)
HOME_DIR=$(eval echo ~$CURRENT_USER)
APP_DIR="$HOME_DIR/moviebrowser"

echo "Installing for user: $CURRENT_USER"
echo "App directory: $APP_DIR"
echo ""

# Check if we're in the right directory
if [ ! -f "app.py" ]; then
    echo "Error: Must run from moviebrowser directory"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Creating from .env.example..."
    cp .env.example .env
    echo "Please edit .env and add your TMDB_API_KEY, then run this script again."
    exit 1
fi

# Check if TMDB_API_KEY is set
if ! grep -q "^TMDB_API_KEY=.\+" .env; then
    echo "Error: TMDB_API_KEY not set in .env file"
    echo "Please edit .env and add your TMDB API key, then run this script again."
    exit 1
fi

# Create logs directory
mkdir -p logs

# Create systemd service file with correct paths
SERVICE_FILE="/tmp/moviebrowser.service"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Movie Browser (No-JS)
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/app.py
Restart=always
RestartSec=10

# Logging
StandardOutput=append:$APP_DIR/logs/moviebrowser.log
StandardError=append:$APP_DIR/logs/moviebrowser.error.log

[Install]
WantedBy=multi-user.target
EOF

echo "Installing systemd service..."
sudo cp "$SERVICE_FILE" /etc/systemd/system/moviebrowser.service
rm "$SERVICE_FILE"

echo "Reloading systemd..."
sudo systemctl daemon-reload

echo "Enabling service..."
sudo systemctl enable moviebrowser

echo "Starting service..."
sudo systemctl start moviebrowser

echo ""
echo "=== Installation Complete! ==="
echo ""
echo "Service status:"
sudo systemctl status moviebrowser --no-pager
echo ""
echo "Useful commands:"
echo "  View logs:     sudo journalctl -u moviebrowser -f"
echo "  Stop service:  sudo systemctl stop moviebrowser"
echo "  Start service: sudo systemctl start moviebrowser"
echo "  Restart:       sudo systemctl restart moviebrowser"
echo "  Disable:       sudo systemctl disable moviebrowser"
echo ""
echo "Access the app at: http://$(hostname -I | awk '{print $1}'):5150"
