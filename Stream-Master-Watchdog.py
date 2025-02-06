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
SERVER_URL = os.getenv("SERVER_URL")  # No default value
USERNAME = os.getenv("USERNAME")  # No default value
PASSWORD = os.getenv("PASSWORD") # No default value
USER_AGENT = os.getenv("USER_AGENT", "Buffer Watchdog")  # Default to "Buffer Watchdog"
QUERY_INTERVAL = int(os.getenv("QUERY_INTERVAL", 5))  # Default to 5 seconds
BUFFER_SPEED_THRESHOLD = float(os.getenv("BUFFER_SPEED_THRESHOLD", 1.0))  # Default 1.0
BUFFER_TIME_THRESHOLD = int(os.getenv("BUFFER_TIME_THRESHOLD", 30))   # Default 30 seconds
BUFFER_EXTENSION_TIME = int(os.getenv("BUFFER_EXTENSION_TIME", 10))  # Default to 10 seconds
CUSTOM_COMMAND = os.getenv("CUSTOM_COMMAND", "") # Default is no command
CUSTOM_COMMAND_TIMEOUT = int(os.getenv("CUSTOM_COMMAND_TIMEOUT", 10))  # Default to 10 seconds
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "/usr/bin/ffmpeg") # Default to "/usr/bin/ffmpeg"
MODULE = os.getenv("MODULE", "Stream_Master") # Default to "Stream_Master"
   
# Maintain running processes, speeds, and buffering timers with stream names
watchdog_processes = {}
watchdog_speeds = {}
watchdog_names = {}  # Store stream names
buffer_start_times = {}
action_triggered = set()

def startup():
    # Exit if SERVER_URL is not defined
    if SERVER_URL is None:
        raise Exception (f"Error: SERVER_URL is not defined!")
    else:
        print(f"Using server URL: {SERVER_URL}")

    # Import the required module dynamically
    global get_running_streams, send_next_stream, stream_url_template, execute_and_monitor_command
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
    # Import Custom_Command module if CUSTOM_COMMAND is set
    if CUSTOM_COMMAND:
        Custom_Command_Path = f"Modules.Run_Custom_Command"
        try:
            from Modules.Run_Custom_Command import execute_and_monitor_command
            print(f"Successfully imported Run_Custom_Command module.")
        except ModuleNotFoundError:
            raise Exception(f"Error: Run_Custom_Command '{Custom_Command_Path}' not found. Ensure {Custom_Command_Path} exists.")
        except Exception as e:
            raise Exception(f"Error: Failed to import Run_Custom_Command module. {e}")
    # Startup configuration complete, start monitoring streams
    monitor_streams()
def get_version():
    try:
        with open("version.txt", "r") as file:
            return file.read().strip()
    except Exception as e:
        print(f"Unable to access version file! Error: {e}")
        return "Unknown"
    
def start_watchdog(stream_id, stream_name):
    """Start the FFmpeg watchdog process for a given stream ID."""
    #stream_url_template = f"{SERVER_URL}/v/0/{{id}}"
    video_url = stream_url_template(SERVER_URL).format(id=stream_id)
    ffmpeg_args = [
        FFMPEG_PATH,
        "-hide_banner",
        "-user_agent", USER_AGENT,       
        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-analyzeduration", "0",
        "-i", video_url,
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
    if process is not None:
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
    try:
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
                                # Run custom command if enabled
                                if CUSTOM_COMMAND:
                                    Thread(target=execute_and_monitor_command, args=(CUSTOM_COMMAND, 10), daemon=True).start()
                                if send_next_stream(stream_id, SERVER_URL, USERNAME, PASSWORD):
                                    stream_swtiched = True
                                    action_triggered.discard(stream_id)
                                    buffer_start_times[stream_id] = time.time() + BUFFER_EXTENSION_TIME
                                    # Update Streams to get new name
                                    current_streams, watchdog_names = get_running_streams(SERVER_URL, USERNAME, PASSWORD)
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
    except Exception as e:
        print(f"Error occured in ffmpeg process: {e}")
    finally:
        # Process has terminated, clean up if unexpected
        stream_name = watchdog_names.get(stream_id, "Unknown Stream")  # Default to "Unknown Stream" if not found
        if watchdog_processes.get(stream_id):
            stop_watchdog(stream_id, stream_name, False)

def monitor_streams():
    """Monitor and manage streams periodically."""
    while True:
        try:
            current_streams, watchdog_names = get_running_streams(SERVER_URL, USERNAME, PASSWORD)
            # Process each stream
            current_ids = {stream["id"] for stream in current_streams}
            for stream in current_streams:
                stream_id = stream["id"]
                stream_name = watchdog_names.get(stream_id, "Unknown Stream")
                clients = stream["clients"]
                # Add watchdog to unmonitored streams
                if stream_id not in watchdog_processes and USER_AGENT not in clients:
                    # Remove watchdog_speeds for stream_id if exists
                    watchdog_speeds.pop(stream_id, None)
                    start_watchdog(stream_id, stream_name)
                # Disconnect if watchdog is the only client
                elif USER_AGENT in clients and len(clients) == 1:
                    stop_watchdog(stream_id, stream_name, True)
                # Close FFMPEG process if running but API doesn't return it as a client
                elif (USER_AGENT not in clients) and (stream_id in watchdog_processes):
                    stop_watchdog(stream_id,stream_name,True)
            # Stop watchdogs for streams no longer running
            for stream_id in list(watchdog_processes):
                if stream_id not in current_ids:
                    stop_watchdog(stream_id, stream_name, True)
            # Display the current speed of each watchdog
            for stream_id, speed in watchdog_speeds.items():
                if watchdog_processes.get(stream_id) is not None:
                    stream_name = next((stream["name"] for stream in current_streams if stream["id"] == stream_id), "Unknown Stream")
                    print(f"Channel ID: {stream_id} - Current Speed: {speed}x - {stream_name}")
                else:
                    # Remove watchdog_speed if stream_id is no longer a running process
                    watchdog_speeds.pop(stream_id)
        except KeyboardInterrupt:
            print("Interrupted by user. Cleaning up...")
            for stream_id in list(watchdog_processes):
                stop_watchdog(stream_id, stream_name, True)
            break
        # Wait for the next query cycle
        time.sleep(QUERY_INTERVAL)

if __name__ == "__main__":
    print(f"Starting Stream Watchdog version: {get_version()}...")
    startup()