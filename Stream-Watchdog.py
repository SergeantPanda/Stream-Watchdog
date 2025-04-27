# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of Stream Watchdog.
#
# Stream Watchdog is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Stream Watchdog is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Stream Watchdog. If not, see <https://www.gnu.org/licenses/>.

import subprocess
import re
import time
import os
import importlib
import psutil
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
ERROR_THRESHOLD = int(os.getenv("ERROR_THRESHOLD", 0))  # Number of errors before switching, Default 0 (disables error checking)
ERROR_SWITCH_COOLDOWN = int(os.getenv("ERROR_SWITCH_COOLDOWN", 10))  # Default 10 seconds
ERROR_RESET_TIME = int(os.getenv("ERROR_RESET_TIME", 20)) # Default 20 seconds
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
    if ERROR_THRESHOLD:
        print(f"Stream error detection enabled!")
    else:
        print(f"Stream error detection disabled! If you want to enable it, set ERROR_THRESHOLD environmental variable.")
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
    global watchdog_names
    video_url = stream_url_template(SERVER_URL).format(id=stream_id)
    if ERROR_THRESHOLD:
        ffmpeg_args = [
            FFMPEG_PATH,
            "-hide_banner",
            "-user_agent", USER_AGENT,
            "-fflags", "+nobuffer+discardcorrupt",
            "-flags", "low_delay",
            "-rtbufsize", "10M",
            "-i", video_url,
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-max_muxing_queue_size", "512",
            "-f", "null",
            "null",
        ]
    else:
        ffmpeg_args = [
            FFMPEG_PATH,
            "-hide_banner",
            "-user_agent", USER_AGENT,
            "-fflags", "+nobuffer+discardcorrupt",
            "-flags", "low_delay",
            "-rtbufsize", "10M",
            "-i", video_url,
            "-c", "copy",
            "-f", "null",
            "null",
        ]
    process = subprocess.Popen(
        ffmpeg_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    watchdog_processes[stream_id] = process
    watchdog_names[stream_id] = stream_name  # Store the stream name
    # Start a thread to monitor speed from FFmpeg output
    Thread(target=monitor_ffmpeg_output, args=(stream_id, process), daemon=True).start()
    print(f"Started watchdog for channel ID: {stream_id} - {stream_name}")


def stop_watchdog(stream_id, stream_name="", expected_stop=True):
    """Stop the FFmpeg watchdog process for a given stream ID."""
    process = watchdog_processes.pop(stream_id, None)
    # Check if process exited
    if process is not None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)  # Wait up to 5 seconds
            except subprocess.TimeoutExpired:
                print(f"⚠️ FFmpeg process {stream_id} did not terminate in time. Forcing stop.")
                process.kill()  # Forcefully kill the process
                process.wait()  # Ensure cleanup
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

def monitor_ffmpeg_output(stream_id, process):
    """Monitor FFmpeg output for speed and errors, with cooldown before switching streams."""
    global watchdog_names
    # Regular expression to capture the speed value from FFmpeg output
    speed_pattern = re.compile(r"speed=\s*(\d+\.?\d*)x")
    # Define error patterns
    ERROR_PATTERNS = [
        re.compile(r"corrupt decoded frame"),
        re.compile(r"error while decoding"),
        re.compile(r"Invalid data found when processing input"),
        re.compile(r"Reference \d+ >= \d+"),
        re.compile(r"concealing \d+ DC, \d+ AC, \d+ MV errors"),
    ]
    # Variables to track stream switching and errors
    stream_switched = False  # Ensures only one switch per buffering instance
    error_count = 0  # Tracks the number of FFmpeg errors
    error_start_time = None  # Records the start time of error occurrences
    last_switch_time = 0  # Tracks the last time a stream was switched
    continue_read = True
    try:
        while process.poll() is None:  # While FFmpeg is running
            for line in iter(process.stderr.readline, ''):
                if continue_read is False:
                    break
                line = line.strip()
                stream_name = watchdog_names.get(stream_id, "Unknown Stream")
                # Check for speed issues (buffering)
                speed_match = speed_pattern.search(line)
                if speed_match:
                    speed = float(speed_match.group(1))
                    watchdog_speeds[stream_id] = speed  # Store current speed
                    #stream_name = watchdog_names.get(stream_id, "Unknown Stream")

                    # Detect buffering if speed drops below threshold
                    if speed < BUFFER_SPEED_THRESHOLD:
                        if stream_id not in buffer_start_times:
                            buffer_start_times[stream_id] = time.time()
                            stream_name = watchdog_names.get(stream_id, "Unknown Stream")
                            print(f"⚠️ Buffering detected on channel {stream_id} - {stream_name}.")

                        # Calculate how long buffering has persisted
                        buffering_duration = time.time() - buffer_start_times[stream_id]

                        # If buffering persists beyond the defined threshold, consider switching
                        if buffering_duration >= BUFFER_TIME_THRESHOLD:
                            # Ensure we don’t switch too frequently
                            if not stream_switched or (time.time() - last_switch_time > BUFFER_TIME_THRESHOLD + BUFFER_EXTENSION_TIME):
                                stream_name = watchdog_names.get(stream_id, "Unknown Stream")

                                # Determine how long buffering has occurred (before or after switching)
                                if stream_switched:
                                    stream_buffering_duration = time.time() - last_switch_time
                                else:
                                    stream_buffering_duration = buffering_duration
                                print(f"⏳ Buffering persisted on channel {stream_id} ({stream_name}) for {stream_buffering_duration:.2f} seconds (total buffering time: {buffering_duration:.2f} seconds).")
                                # Run custom command if enabled
                                if CUSTOM_COMMAND:
                                    Thread(target=execute_and_monitor_command, args=(CUSTOM_COMMAND, 10), daemon=True).start()
                                # Attempt to switch to the next available stream
                                if send_next_stream(stream_id, SERVER_URL, USERNAME, PASSWORD):
                                    # Update watchdog names to reflect new stream name
                                    current_streams, watchdog_names = get_running_streams(SERVER_URL, USERNAME, PASSWORD)
                                    stream_switched = True
                                    last_switch_time = time.time()  # Update last switch time
                                    stream_name = watchdog_names.get(stream_id, "Unknown Stream")
                                    print(f"✅ Switched stream for channel {stream_id} - {stream_name}.")
                                else:
                                    print(f"❌ Failed to switch stream for channel {stream_id}.")
                    else:
                        # Reset buffering state when speed returns to normal
                        if stream_id in buffer_start_times:
                            del buffer_start_times[stream_id]
                            stream_name = watchdog_names.get(stream_id, "Unknown Stream")
                            print(f"✅ Buffering resolved for channel {stream_name}.")

                        # Allow future switches when buffering is no longer an issue
                        stream_switched = False
                        last_switch_time = 0  # Reset switch cooldown

                # Check for FFmpeg errors if enabled
                if ERROR_THRESHOLD > 0:
                    for error_pattern in ERROR_PATTERNS:
                        if error_pattern.search(line):
                            error_count += 1
                            #stream_name = watchdog_names.get(stream_id, "Unknown Stream")
                            print(f"⚠️ FFmpeg error detected on channel {stream_id} ({stream_name}): {line}")

                            # Record the first error time
                            if error_start_time is None:
                                error_start_time = time.time()

                            # Reset error count if errors occur too far apart
                            if time.time() - error_start_time > ERROR_RESET_TIME:
                                error_count = 1
                                error_start_time = time.time()

                            # If too many errors occur within the threshold, switch streams
                            if error_count >= ERROR_THRESHOLD:
                                current_time = time.time()

                                # Prevent switching if still within the cooldown period
                                if current_time - last_switch_time < ERROR_SWITCH_COOLDOWN:
                                    print(f"🕒 Cooldown active. Not switching channel {stream_id} ({stream_name}) yet.")
                                    continue  # Skip switching
                                stream_name = watchdog_names.get(stream_id, "Unknown Stream")
                                print(f"❌ Too many errors on channel {stream_name}. Switching stream.")
                                # Run custom command if enabled
                                if CUSTOM_COMMAND:
                                    Thread(target=execute_and_monitor_command, args=(CUSTOM_COMMAND, 10), daemon=True).start()
                                # Attempt to switch the stream
                                if send_next_stream(stream_id, SERVER_URL, USERNAME, PASSWORD):
                                    # Update watchdog names to reflect new stream name
                                    current_streams, watchdog_names = get_running_streams(SERVER_URL, USERNAME, PASSWORD)
                                    stream_switched = True
                                    last_switch_time = current_time  # Update last switch time
                                    stream_name = watchdog_names.get(stream_id, "Unknown Stream")
                                    error_count = 0
                                    print(f"✅ Switched stream for channel {stream_id} - {stream_name}.")
                                else:
                                    print(f"❌ Failed to switch channel {stream_id}.")
                                # Max number of errors reached, break out of for loop
                                continue_read = False
                                break
            # Change continue read back to true
            continue_read = True

    except Exception as e:
        print(f"❌ Error in FFmpeg process: {e}")

    finally:
        # Ensure that the watchdog process is properly stopped if needed
        if watchdog_processes.get(stream_id):
            stream_name = watchdog_names.get(stream_id, "Unknown Stream")
            stop_watchdog(stream_id, stream_name, False)


def monitor_streams():
    """Monitor and manage streams periodically."""
    global watchdog_names
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
                    stream_name = watchdog_names.get(stream_id, "Unknown Stream")
                    print(f"Channel ID: {stream_id} - Current Speed: {speed:.2f}x - {stream_name}")
                else:
                    # Remove watchdog_speed if stream_id is no longer a running process
                    watchdog_speeds.pop(stream_id)
        except Exception as e:
            print(f"❌ Error in monitoring streams: {e}")
        except KeyboardInterrupt:
            print("Interrupted by user. Cleaning up...")
            for stream_id in list(watchdog_processes):
                stop_watchdog(stream_id, stream_name, True)
            break
        # Wait for the next query cycle
        time.sleep(QUERY_INTERVAL)
        # Monitor the current watchdog ffmpeg processes for high memory usage
        Thread(target=monitor_ffmpeg_memory, args=(watchdog_processes,), daemon=True).start()

def monitor_ffmpeg_memory(watchdog_processes, max_memory_mb=150):
    """Monitor all FFmpeg processes and restart them if memory usage exceeds max_memory_mb."""
    for stream_id, process in list(watchdog_processes.items()):
        if process.poll() is None:  # Process is still running
            try:
                mem_usage = psutil.Process(process.pid).memory_info().rss / (1024 * 1024)  # Convert bytes to MB

                if mem_usage > max_memory_mb:
                    print(f"⚠️ FFmpeg process {stream_id} exceeded {max_memory_mb:.2f}MB! Restarting...")
                    process.kill()  # Kill the process
                    process.wait(timeout=5)  # Ensure it fully exits
                    watchdog_processes.pop(stream_id, None)  # Remove from tracking
                    stream_name = watchdog_names.get(stream_id, "Unknown Stream")
                    stop_watchdog(stream_id, stream_name)
                    start_watchdog(stream_id, stream_name)  # Restart

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue  # Process might have already exited


if __name__ == "__main__":
    print(f"Starting Stream Watchdog version: {get_version()}...")
    startup()
    print(f"Stream Watchdog has stopped.")