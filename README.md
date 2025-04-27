# Stream Watchdog

Stream Watchdog is a Python script designed to monitor streams in the StreamMaster application. It ensures uninterrupted streaming by detecting buffering issues and automatically switching to the next stream if buffering persists for a configurable period.

## Features
- Monitors streams for buffering issues in real-time.
- Displays the current speed of each stream being monitored.
- Detects buffering below a configurable speed threshold.
- Automatically switches to the next stream after prolonged buffering.
- Logs relevant messages to the console, including buffering detection and resolution status.

## Requirements
- FFMPEG
- Python 3.8 or higher
- Dependencies:
  - `requests`
  - `psutil`

## Installation
1. Clone this repository:
   ```bash
   git clone https://github.com/SergeantPanda/Stream-Watchdog.git
   cd Stream-Watchdog
   ```
2. Install required Python dependencies:
   ```bash
   pip install requests
   pip install psutil
   ```
3. Ensure `ffmpeg` is installed and available on your system.

## Configuration
Update the following variables in the script to match your environment:

- `SERVER_URL`: Base URL of your server (e.g., `http://Dispatcharr:9191`).
- `USERNAME`: # Username you use to login to the web ui. (Default: `none`)
- `PASSWORD`: # Password you use to login to the web ui. (Default: `none`)
- `USER_AGENT`: Identifier used for the watchdog client. (Default: `Buffer Watchdog`)
- `QUERY_INTERVAL`: Interval (in seconds) to query the API for stream updates. Setting this faster will not speed up buffer detection. (Default: `5`)
- `BUFFER_SPEED_THRESHOLD`: Speed threshold to detect buffering. (Default: `1.0`)
- `BUFFER_TIME_THRESHOLD`: Time (in seconds) to wait before switching streams when buffering. (Default: `30`)
- `BUFFER_EXTENSION_TIME`: Time (in seconds) to add to the buffer timeout after switching streams. (Default: `10`)
- `ERROR_THRESHOLD`: Number of errors before switching. (Default: `0` (disables error checking))
- `ERROR_SWITCH_COOLDOWN`: Time (in seconds) between stream switches if errors trigger the switch. (Default: `10`)
- `ERROR_RESET_TIME`: Time (in seconds) to wait before error count resets to 0. (Default: `20`)
- `CUSTOM_COMMAND`: Command that will run when buffering persists and a next stream is sent. (Default: `no command provided`)
- `CUSTOM_COMMAND_TIMEOUT`: Time (in seconds) to wait for a command before terminating it. (Default:`10`)
- `FFMPEG_PATH`: Path to your `ffmpeg` executable.
- `MODULE`: Module name to use. (Default: `Dispatcharr`) (Accepted Values: `Dispatcharr`,`Stream_Master`,`AIPTV`)

## Usage
1. Start the script:
   ```bash
   python Stream-Master-Watchdog.py
   ```
2. The script will:
   - Periodically query the StreamMaster API for active streams.
   - Monitor each stream's speed using FFmpeg.
   - Switch to the next stream if buffering persists.

## Docker Compose Example
You can deploy Stream Watchdog using Docker Compose for easier setup and management.
```yaml
version: "3.8"
services:
  streamwatchdog:
    image: sergeantpanda/streamwatchdog:latest
    container_name: StreamWatchdog
    environment:
      - SERVER_URL=http://Dispatcharr:9191
      - USERNAME= # Optional - Only needed if using authentication
      - PASSWORD= # Optional - Only needed if using authentication
      - QUERY_INTERVAL=5 # Optional
      - USER_AGENT=Buffer Watchdog # Optional
      - BUFFER_SPEED_THRESHOLD=1.0 # Optional
      - BUFFER_TIME_THRESHOLD=30 # Optional
      - BUFFER_EXTENSION_TIME=10 # Optional
      - ERROR_THRESHOLD=0 # Optional (value higher than 0 enables error checking)
      - CUSTOM_COMMAND=  # Optional - Don't use quotes around entire command
      - CUSTOM_COMMAND_TIMEOUT=10 # Optional
      - FFMPEG_PATH=/usr/bin/ffmpeg # Optional - Don't change unless you know what you're doing
      - MODULE=Stream_Master # Optional
      - TZ=US/Central # Optional
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
         max-size: "10m"
         max-file: "3"
```

## Example Output
```
Starting stream watchdog monitor...
Started watchdog for channel ID: 101 - Sports Channel
Started watchdog for channel ID: 102 - Movie Channel
Started watchdog for channel ID: 103 - News Channel
Channel ID: 101 - Current Speed: 1.2x - Sports Channel
Channel ID: 102 - Current Speed: 1.0x - Movie Channel
Channel ID: 103 - Current Speed: 0.8x - News Channel
Buffering detected on channel 103 - News Channel.
Channel ID: 103 - Current Speed: 0.6x - News Channel
Buffering persisted on channel 103 (News Channel) for 30.05 seconds.
Attempting to switch to the next stream for channel 103...
Switched to the next stream for channel 103. Added 10 seconds to buffer timer.
Channel ID: 101 - Current Speed: 1.2x - Sports Channel
Channel ID: 102 - Current Speed: 1.0x - Movie Channel
Channel ID: 103 - Current Speed: 1.1x - News Channel (New Stream)
Buffering resolved on channel 103 - News Channel.
```
## Contributing
Contributions are welcome! Feel free to submit issues or pull requests to improve this script.

## License
This project is licensed under the GNU General Public License v3.0. See the [LICENSE](./LICENSE) file for details.

