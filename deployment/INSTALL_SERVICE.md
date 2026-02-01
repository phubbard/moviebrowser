# Installing Movie Browser as a System Service

## Raspberry Pi / Linux (systemd) - Recommended

### Quick Install (Automated)

1. **Clone the repository**
   ```bash
   git clone https://github.com/phubbard/moviebrowser.git
   cd moviebrowser
   ```

2. **Set up Python environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   nano .env  # Add your TMDB_API_KEY
   ```

4. **Run the automated installer**
   ```bash
   ./deployment/install-service.sh
   ```

That's it! The installer will:
- Auto-detect your username and app directory
- Detect your virtual environment (`.venv` or `venv`)
- Create the logs directory
- Generate and install the systemd service file
- Enable and start the service
- Show you the service status

The app will be accessible at `http://your-pi-ip:5150`

### Manual Install (Advanced)

If you prefer to install manually or customize the setup:

1. **Follow steps 1-3 from Quick Install above**

2. **Test the app manually first**
   ```bash
   DEBUG=true python app.py
   # Visit http://your-pi-ip:5150
   # Press Ctrl+C when done testing
   ```

3. **Edit the service file if needed**
   ```bash
   nano deployment/moviebrowser.service
   # Update User, paths, or other settings
   ```

4. **Copy the service file**
   ```bash
   sudo cp deployment/moviebrowser.service /etc/systemd/system/
   ```

5. **Enable and start the service**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable moviebrowser
   sudo systemctl start moviebrowser
   ```

6. **Check status**
   ```bash
   sudo systemctl status moviebrowser
   ```

### Managing the Service

**View logs:**
```bash
# Follow live logs
sudo journalctl -u moviebrowser -f

# Or view log files directly
tail -f logs/moviebrowser.log
tail -f logs/moviebrowser.error.log

# View recent logs
sudo journalctl -u moviebrowser -n 50
```

**Stop the service:**
```bash
sudo systemctl stop moviebrowser
```

**Restart the service:**
```bash
sudo systemctl restart moviebrowser
```

**Disable autostart:**
```bash
sudo systemctl disable moviebrowser
```

### Updating the App

```bash
cd moviebrowser  # or wherever you installed it
git pull
sudo systemctl restart moviebrowser
```

### Troubleshooting

**Service won't start:**
```bash
# Check the service status for errors
sudo systemctl status moviebrowser

# View detailed logs
sudo journalctl -u moviebrowser -n 100

# Verify your .env file has TMDB_API_KEY set
grep TMDB_API_KEY .env

# Test running manually
source .venv/bin/activate
DEBUG=true python app.py
```

**Can't access from other devices:**
- Make sure `DEBUG=false` in your `.env` file (production mode binds to 0.0.0.0)
- Check your firewall: `sudo ufw allow 5150` (if using ufw)
- Verify the service is running: `sudo systemctl status moviebrowser`

## macOS (launchd) - For Development

1. **Copy the plist file to LaunchAgents**
   ```bash
   cp com.phubbard.moviebrowser.plist ~/Library/LaunchAgents/
   ```

2. **Load the service**
   ```bash
   launchctl load ~/Library/LaunchAgents/com.phubbard.moviebrowser.plist
   ```

3. **Check if it's running**
   ```bash
   launchctl list | grep moviebrowser
   ```

4. **View logs**
   ```bash
   tail -f ~/code/movielist/logs/moviebrowser.log
   tail -f ~/code/movielist/logs/moviebrowser.error.log
   ```

### Managing the Service

**Stop the service:**
```bash
launchctl unload ~/Library/LaunchAgents/com.phubbard.moviebrowser.plist
```

**Restart the service:**
```bash
launchctl unload ~/Library/LaunchAgents/com.phubbard.moviebrowser.plist
launchctl load ~/Library/LaunchAgents/com.phubbard.moviebrowser.plist
```

**Remove the service:**
```bash
launchctl unload ~/Library/LaunchAgents/com.phubbard.moviebrowser.plist
rm ~/Library/LaunchAgents/com.phubbard.moviebrowser.plist
```

## Other Linux Systems

The installation process is the same as Raspberry Pi. Just use the automated installer:

```bash
./deployment/install-service.sh
```

The script automatically detects:
- Your username (even if run with sudo)
- Your app directory location
- Your virtual environment (`.venv` or `venv`)
- Loads environment variables from `.env`

## Important Notes

- **Production mode**: Set `DEBUG=false` in `.env` for production (enables network access via 0.0.0.0)
- **Development mode**: Set `DEBUG=true` for local development (binds to 127.0.0.1 only)
- **Logs**: Written to `logs/` directory and viewable via `journalctl`
- **Auto-restart**: Service automatically restarts if it crashes
- **Virtual environment**: Supports both `.venv` and `venv` naming conventions
- **Environment variables**: Loaded automatically from `.env` file by the service
