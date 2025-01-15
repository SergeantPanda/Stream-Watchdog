import subprocess
import requests
import re
import time
import os
import logging
import sys
from threading import Thread

# Logging
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logging.info("Stream Master Watchdog started")

# Configuration

# Read environment variables
SERVERURL = os.getenv("SERVERURL", "http://SERVERNAME:7095")  # Default value if not provided
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "/usr/bin/ffmpeg")
BUFFER_SPEED_THRESHOLD = float(os.getenv("BUFFERING_THRESHOLD", 1.0))  # Default 1.0
BUFFER_TIME_THRESHOLD = int(os.getenv("BUFFERING_TIME_LIMIT", 30))   # Default 30 seconds
API_URL = f"{SERVERURL}/api/statistics/getchannelmetrics"
NEXT_STREAM_API_URL = f"{SERVERURL}/api/streaming/movetonextstream"
STREAM_URL_TEMPLATE = f"{SERVERURL}/v/0/{{id}}"
USER_AGENT = os.getenv("USER_AGENT", "Buffer Watchdog")  # Default to "Buffer Watchdog"
QUERY_INTERVAL = int(os.getenv("QUERY_INTERVAL", 5))  # Default to 5 seconds


# Maintain running processes, speeds, and buffering timers
watchdog_processes = {}
watchdog_speeds = {}
buffer_start_times = {}
action_triggered = set()

def get_running_streams():
    """Fetch current running streams from the API."""
    try:
        response = requests.get(API_URL, headers={"accept": "application/json"})
        response.raise_for_status()
        streams = response.json()
        
        return [
            {
                "id": stream.get("id") or stream.get("Id"),  # Handle both "id" and "Id"
                "clients": [
                    client.get("clientUserAgent") or client.get("ClientUserAgent", "") 
                    for client in stream.get("clientStreams") or stream.get("ClientStreams", [])
                ],
            }
            for stream in streams if not stream.get("isFailed", False)
        ]
    except Exception as e:
        print(f"Error fetching streams: {e}")
        return []
    
def start_watchdog(stream_id):
    """Start the FFmpeg watchdog process for a given stream ID."""
    video_url = STREAM_URL_TEMPLATE.format(id=stream_id)
    ffmpeg_args = [
        FFMPEG_PATH,
        "-hide_banner",
        "-user_agent", USER_AGENT,
        "-i", video_url,
        "-map", "0",
        "-c", "copy",
        "-f", "null",
        "-",
    ]
    process = subprocess.Popen(
        ffmpeg_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    watchdog_processes[stream_id] = process

    # Start a thread to monitor speed from FFmpeg output
    Thread(target=monitor_ffmpeg_output, args=(stream_id, process), daemon=True).start()
    print(f"Started watchdog for stream {stream_id}")

def stop_watchdog(stream_id):
    """Stop the FFmpeg watchdog process for a given stream ID."""
    process = watchdog_processes.pop(stream_id, None)
    if process:
        process.terminate()
        process.wait()
        watchdog_speeds.pop(stream_id, None)
        buffer_start_times.pop(stream_id, None)
        action_triggered.discard(stream_id)
        print(f"Stopped watchdog for stream {stream_id}")

def monitor_ffmpeg_output(stream_id, process):
    """Monitor the FFmpeg output for speed and update global state."""
    speed_pattern = re.compile(r"speed=\s*(\d+\.?\d*)x")
    for line in process.stderr:
        match = speed_pattern.search(line)
        if match:
            speed = match.group(1)
            watchdog_speeds[stream_id] = float(speed)

            # Detect buffering: If speed drops below threshold, track it
            if float(speed) < BUFFER_SPEED_THRESHOLD:
                if stream_id not in buffer_start_times:
                    buffer_start_times[stream_id] = time.time()  # Start buffering timer
                    print(f"Buffering detected on stream {stream_id}.")
                else:
                    buffering_duration = time.time() - buffer_start_times[stream_id]
                    if buffering_duration >= BUFFER_TIME_THRESHOLD and stream_id not in action_triggered:
                        print(f"Buffering persisted on stream {stream_id} for {buffering_duration:.2f} seconds.")
                        handle_buffering(stream_id)
                        action_triggered.add(stream_id)
            else:
                if stream_id in buffer_start_times:
                    del buffer_start_times[stream_id]  # Reset buffering timer when speed improves
                    print(f"Buffering resolved on stream {stream_id}.")
                action_triggered.discard(stream_id)

def handle_buffering(stream_id):
    """Handle the buffering event by switching to the next stream."""
    try:
        payload = {"smChannelId": stream_id}
        response = requests.patch(
            NEXT_STREAM_API_URL,
            json=payload,
            headers={
                "accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        result = response.json()
        if not result.get("isError", True):
            print(f"Switched to the next stream for channel {stream_id}.")
        else:
            print(f"Failed to switch to the next stream for channel {stream_id}.")
    except Exception as e:
        print(f"Error switching to the next stream for channel {stream_id}: {e}")

def monitor_streams():
    """Monitor and manage streams periodically."""
    while True:
        try:
            current_streams = get_running_streams()

            # Process each stream
            current_ids = {stream["id"] for stream in current_streams}
            for stream in current_streams:
                stream_id = stream["id"]
                clients = stream["clients"]

                # Add watchdog to unmonitored streams
                if stream_id not in watchdog_processes and USER_AGENT not in clients:
                    start_watchdog(stream_id)

                # Disconnect if watchdog is the only client
                elif USER_AGENT in clients and len(clients) == 1:
                    stop_watchdog(stream_id)

            # Stop watchdogs for streams no longer running
            for stream_id in list(watchdog_processes):
                if stream_id not in current_ids:
                    stop_watchdog(stream_id)

            # Display the current speed of each watchdog
            for stream_id, speed in watchdog_speeds.items():
                print(f"Stream {stream_id} - Speed: {speed}x")

            # Wait for the next query cycle
            time.sleep(QUERY_INTERVAL)

        except KeyboardInterrupt:
            print("Interrupted by user. Cleaning up...")
            for stream_id in list(watchdog_processes):
                stop_watchdog(stream_id)
            break

if __name__ == "__main__":
    print("Starting stream watchdog monitor...")
    monitor_streams()
