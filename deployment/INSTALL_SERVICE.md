# Installing Movie Browser as a System Service

## Raspberry Pi / Linux (systemd) - Recommended

### Initial Setup

1. **Clone the repository**
   ```bash
   cd ~
   git clone git@github.com:phubbard/moviebrowser.git
   cd moviebrowser
   ```

2. **Set up Python environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   nano .env  # Add your TMDB_API_KEY
   ```

4. **Create logs directory**
   ```bash
   mkdir -p logs
   ```

5. **Test the app manually first**
   ```bash
   DEBUG=true python app.py
   # Visit http://your-pi-ip:5150
   # Press Ctrl+C when done testing
   ```

### Install as System Service

1. **Update the service file with your username** (if not using 'pi')
   ```bash
   nano deployment/moviebrowser.service
   # Change User=pi and paths if needed
   ```

2. **Copy the service file**
   ```bash
   sudo cp deployment/moviebrowser.service /etc/systemd/system/
   ```

3. **Enable and start the service**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable moviebrowser
   sudo systemctl start moviebrowser
   ```

4. **Check status**
   ```bash
   sudo systemctl status moviebrowser
   ```

5. **View logs**
   ```bash
   # Follow live logs
   sudo journalctl -u moviebrowser -f

   # Or view log files directly
   tail -f ~/moviebrowser/logs/moviebrowser.log
   tail -f ~/moviebrowser/logs/moviebrowser.error.log
   ```

### Managing the Service

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

**View recent logs:**
```bash
sudo journalctl -u moviebrowser -n 50
```

### Updating the App

```bash
cd ~/moviebrowser
git pull
sudo systemctl restart moviebrowser
```

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

## Linux (systemd)

1. **Copy the service file**
   ```bash
   sudo cp deployment/moviebrowser.service /etc/systemd/system/
   ```

2. **Edit the service file to update paths and user**
   ```bash
   sudo nano /etc/systemd/system/moviebrowser.service
   # Update User, WorkingDirectory, and ExecStart paths
   ```

3. **Enable and start the service**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable moviebrowser
   sudo systemctl start moviebrowser
   ```

4. **Check status**
   ```bash
   sudo systemctl status moviebrowser
   ```

5. **View logs**
   ```bash
   sudo journalctl -u moviebrowser -f
   ```

## Notes

- The service runs with `DEBUG=False` for production
- Logs are written to `logs/` directory
- Service restarts automatically if it crashes (KeepAlive/Restart=always)
- Make sure your `.env` file is properly configured before starting
