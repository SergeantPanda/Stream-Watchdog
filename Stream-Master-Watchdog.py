# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of Stream Master Watchdog.
#
# Stream Master Watchdog is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Stream Master Watchdog is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Stream Master Watchdog. If not, see <https://www.gnu.org/licenses/>.


import subprocess
import re
import time
import os
import importlib
from threading import Thread

# Read environment variables
SERVER_URL = os.getenv("SERVER_URL")  # Default value if not provided
USER_AGENT = os.getenv("USER_AGENT", "Buffer Watchdog")  # Default to "Buffer Watchdog"
QUERY_INTERVAL = int(os.getenv("QUERY_INTERVAL", 5))  # Default to 5 seconds
BUFFER_SPEED_THRESHOLD = float(os.getenv("BUFFER_SPEED_THRESHOLD", 1.0))  # Default 1.0
BUFFER_TIME_THRESHOLD = int(os.getenv("BUFFER_TIME_THRESHOLD", 30))   # Default 30 seconds
BUFFER_EXTENSION_TIME = int(os.getenv("BUFFER_EXTENSION_TIME", 10))  # Default to 10 seconds
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "/usr/bin/ffmpeg")
MODULE = os.getenv("MODULE", "Stream_Master")

# Exit if SERVER_URL is not defined
if SERVER_URL is None:
    raise Exception (f"Error: SERVER_URL is not defined!")

# Import the required module dynamically
module_path = f"Modules.{MODULE}"
try:
    module = importlib.import_module(module_path)
    # Dynamically access the desired functions and variables
    get_running_streams = getattr(module, "get_running_streams")
    send_next_stream = getattr(module, "send_next_stream")
    stream_url_template = getattr(module, "stream_url_template")  
    print(f"Successfully imported functions from {module_path}")
except ModuleNotFoundError:
    raise Exception(f"Error: Module '{module_path}' not found. Ensure the MODULE environment variable is set correctly.")
except AttributeError as e:
    raise Exception(f"Error: Missing attributes in module '{module_path}'. {e}")

# Maintain running processes, speeds, and buffering timers with stream names
watchdog_processes = {}
watchdog_speeds = {}
watchdog_names = {}  # Store stream names
buffer_start_times = {}
action_triggered = set()
    
def start_watchdog(stream_id, stream_name):
    """Start the FFmpeg watchdog process for a given stream ID."""
    #stream_url_template = f"{SERVER_URL}/v/0/{{id}}"
    video_url = stream_url_template(SERVER_URL).format(id=stream_id)
    ffmpeg_args = [
        FFMPEG_PATH,
        "-hide_banner",
        "-user_agent", USER_AGENT,
        "-i", video_url,
        "-fflags", "nobuffer",
        "-analyzeduration", "0",
        "-probesize", "32",
        "-map", "0",
        "-c", "copy",
        "-f", "null",
        "-",
    ]
    process = subprocess.Popen(
        ffmpeg_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    watchdog_processes[stream_id] = process
    watchdog_names[stream_id] = stream_name  # Store the stream name

    # Start a thread to monitor speed from FFmpeg output
    Thread(target=monitor_ffmpeg_output, args=(stream_id, process, watchdog_names), daemon=True).start()
    print(f"Started watchdog for channel ID: {stream_id} - {stream_name}")

def stop_watchdog(stream_id, stream_name="", expected_stop=True):
    """Stop the FFmpeg watchdog process for a given stream ID."""
    process = watchdog_processes.pop(stream_id, None)
    # Check if process exited
    if process.poll() is None:
        process.terminate()
        process.wait()
    watchdog_speeds.pop(stream_id, None)
    buffer_start_times.pop(stream_id, None)
    action_triggered.discard(stream_id)
    # Remove the stream name entry from watchdog_names
    if stream_id in watchdog_names:
        del watchdog_names[stream_id]  # Remove from the dictionary
    if expected_stop:
        print(f"Stopped watchdog for channel ID: {stream_id} - {stream_name}")
    else:
        print(f"Watchdog process ended unexpectedly for channel ID: {stream_id} - {stream_name}")

def monitor_ffmpeg_output(stream_id, process, watchdog_names):
    """Monitor the FFmpeg output for speed and update global state."""   
    speed_pattern = re.compile(r"speed=\s*(\d+\.?\d*)x")
    stream_swtiched = False

    while process.poll() is None:  # Continue looping while the process is running
        for line in process.stderr:
            match = speed_pattern.search(line)
            if match:
                speed = match.group(1)
                watchdog_speeds[stream_id] = float(speed)
                # Get the current stream name from the global watchdog_names dictionary
                stream_name = watchdog_names.get(stream_id, "Unknown Stream")  # Default to "Unknown Stream" if not found
                # Detect buffering: If speed drops below threshold, track it
                if float(speed) < BUFFER_SPEED_THRESHOLD:
                    if stream_id not in buffer_start_times:
                        buffer_start_times[stream_id] = time.time()  # Start buffering timer
                        print(f"Buffering detected on channel {stream_id} - {stream_name}.")                        
                    else:
                        buffering_duration = time.time() - buffer_start_times[stream_id]
                        if buffering_duration >= BUFFER_TIME_THRESHOLD and stream_id not in action_triggered:
                            if stream_swtiched:
                                buffering_duration += BUFFER_EXTENSION_TIME
                                print(f"Buffering persisted on channel {stream_id} ({stream_name}) for {buffering_duration:.2f} seconds.")
                            else:
                                print(f"Buffering persisted on channel {stream_id} ({stream_name}) for {buffering_duration:.2f} seconds.")
                            action_triggered.add(stream_id)
                            if send_next_stream(stream_id, SERVER_URL):
                                stream_swtiched = True
                                action_triggered.discard(stream_id)
                                buffer_start_times[stream_id] = time.time() + BUFFER_EXTENSION_TIME
                                # Update Streams to get new name
                                current_streams, watchdog_names = get_running_streams(SERVER_URL)
                                # Get the current stream name from watchdog_names
                                new_stream_name = watchdog_names.get(stream_id, "Unknown Stream")
                                print(f"Switched to the next stream for channel {stream_id} - {new_stream_name}. Added {BUFFER_EXTENSION_TIME} seconds to buffer timer.")
                            else:
                                print(f"Failed to switch to the next stream for channel {stream_id}.")
                else:
                    if stream_id in buffer_start_times:
                        del buffer_start_times[stream_id]  # Reset buffering timer when speed improves
                        # Get the current stream name from the global watchdog_names dictionary
                        stream_name = watchdog_names.get(stream_id, "Unknown Stream")  # Default to "Unknown Stream" if not found
                        print(f"Buffering resolved on channel {stream_id} - {stream_name}.")
                        stream_swtiched = False
                    action_triggered.discard(stream_id)

    # Process has terminated, clean up if unexpected
    stream_name = watchdog_names.get(stream_id, "Unknown Stream")  # Default to "Unknown Stream" if not found
    if watchdog_processes.get(stream_id):
        stop_watchdog(stream_id, stream_name, False)

def monitor_streams():
    """Monitor and manage streams periodically."""
    while True:
        try:
            current_streams, watchdog_names = get_running_streams(SERVER_URL)

            # Process each stream
            current_ids = {stream["id"] for stream in current_streams}
            for stream in current_streams:
                stream_id = stream["id"]
                stream_name = watchdog_names.get(stream_id, "Unknown Stream")
                clients = stream["clients"]

                # Add watchdog to unmonitored streams
                if stream_id not in watchdog_processes and USER_AGENT not in clients:
                    start_watchdog(stream_id, stream_name)

                # Disconnect if watchdog is the only client
                elif USER_AGENT in clients and len(clients) == 1:
                    stop_watchdog(stream_id, stream_name, True)


            # Stop watchdogs for streams no longer running
            for stream_id in list(watchdog_processes):
                if stream_id not in current_ids:
                    stop_watchdog(stream_id, stream_name, True)

            # Display the current speed of each watchdog
            for stream_id, speed in watchdog_speeds.items():
                stream_name = next((stream["name"] for stream in current_streams if stream["id"] == stream_id), "Unknown Stream")
                print(f"Channel ID: {stream_id} - Current Speed: {speed}x - {stream_name}")


            # Wait for the next query cycle
            time.sleep(QUERY_INTERVAL)

        except KeyboardInterrupt:
            print("Interrupted by user. Cleaning up...")
            for stream_id in list(watchdog_processes):
                stop_watchdog(stream_id, stream_name, True)
            break

if __name__ == "__main__":
    print("Starting stream watchdog monitor...")
    monitor_streams()