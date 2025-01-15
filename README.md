# Stream Master Watchdog

Stream Master Watchdog is a Python script designed to monitor streams in the StreamMaster application. It ensures uninterrupted streaming by detecting buffering issues and automatically switching to the next stream if buffering persists for a configurable period.

## Features
- Monitors streams for buffering issues in real-time.
- Displays the current speed of each stream being monitored.
- Detects buffering below a configurable speed threshold.
- Automatically switches to the next stream after prolonged buffering.
- Logs relevant messages to the console, including buffering detection and resolution status.

## Requirements
- Python 3.8 or higher
- Dependencies:
  - `requests`
  - `re`
  - `subprocess`
  - `time`
  - `threading`

## Installation
1. Clone this repository:
   ```bash
   git clone https://github.com/SergeantPanda/StreamMaster-Watchdog.git
   cd StreamMaster-Watchdog
   ```
2. Install required Python dependencies:
   ```bash
   pip install requests
   ```
3. Ensure `ffmpeg` is installed and available on your system.

## Configuration
Update the following variables in the script to match your environment:

- `SERVERURL`: Base URL of your StreamMaster server (e.g., `http://localhost:7095`).
- `FFMPEG_PATH`: Path to your `ffmpeg` executable.
- `USER_AGENT`: Identifier used for the watchdog client.
- `QUERY_INTERVAL`: Interval (in seconds) to query the API for stream updates.
- `BUFFER_SPEED_THRESHOLD`: Speed threshold (default: `1.0x`) to detect buffering.
- `BUFFER_TIME_THRESHOLD`: Time (in seconds) to wait before switching streams when buffering.

## Usage
1. Start the script:
   ```bash
   python stream-master-watchdog.py
   ```
2. The script will:
   - Periodically query the StreamMaster API for active streams.
   - Monitor each stream's speed using FFmpeg.
   - Switch to the next stream if buffering persists.

## Docker Compose Example
You can deploy Stream Master Watchdog using Docker Compose for easier setup and management.
```yaml
version: "3.8"
services:
  streammasterwatchdog:
    image: sergeantpanda/streammasterwatchdog:latest
    container_name: streammasterwatchdog
    environment:
      - SERVERURL=http://localhost:7095
      - QUERY_INTERVAL=5
      - USER_AGENT=Buffer Watchdog
      - BUFFER_SPEED_THRESHOLD=1.0
      - BUFFER_TIME_THRESHOLD=30
    volumes:
      - ./logs:/logs
    restart: unless-stopped
```

## API Integration
The script uses the following StreamMaster APIs:

### Get Channel Metrics
- Endpoint: `/api/statistics/getchannelmetrics`
- Method: `GET`
- Purpose: Fetches the current active streams and client details.

### Move to Next Stream
- Endpoint: `/api/streaming/movetonextstream`
- Method: `PATCH`
- Payload:
  ```json
  {
    "smChannelId": <stream_id>
  }
  ```
- Purpose: Commands StreamMaster to switch to the next stream.

## Example Output
```
Started watchdog for stream 48
Stream 48 - Speed: 2.84x
Stream 48 - Speed: 0.90x
Buffering detected on stream 48 for 30 seconds.
Switched to the next stream successfully.
```

## Contributing
Contributions are welcome! Feel free to submit issues or pull requests to improve this script.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments
Special thanks to the Stream Master developer Senex for providing a robust API to enhance streaming experiences.
