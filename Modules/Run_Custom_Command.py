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
import time
import os
import signal

def execute_and_monitor_command(command, timeout=30):
    """
    Execute a shell command, monitor its runtime, and terminate it if it exceeds the timeout.
    Args:
        command (str): The command to execute.
        timeout (int): Maximum allowed time (in seconds) for the command to run.
    Returns:
        dict: A dictionary containing the result of the execution, runtime, and status.
    """
    result = {
        "command": command,
        "output": None,
        "error": None,
        "runtime": 0,
        "status": "Success",  # Can be 'Success', 'Timeout', or 'Error'
    }

    print(f"Executing command: {command}")
    start_time = time.time()

    try:
        # Start the process without waiting for it to complete
        process = subprocess.Popen(
            command,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Monitor the process for the timeout
        while True:
            if process.poll() is not None:  # Process completed
                break

            elapsed_time = time.time() - start_time
            if elapsed_time > timeout:
                # Kill the process if it exceeds the timeout
                #os.kill(process.pid, signal.SIGTERM)  # Send SIGTERM
                process.terminate()
                process.wait()
                result["status"] = "Timeout"
                result["error"] = f"Command timed out after {timeout} seconds."
                print(result["error"])
                break

            time.sleep(0.1)  # Avoid busy waiting

        # Collect output if process completed within the timeout
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            result["output"] = stdout
            if process.returncode != 0:
                result["status"] = "Error"
                result["error"] = stderr or "An error occurred during command execution."
            else:
                # Print output if successful
                print(f"Successfully ran command: {result['output']}")
    except Exception as e:
        result["status"] = "Error"
        result["error"] = str(e)
        print(f"Unexpected error: {result['error']}")

# Test custom command
if __name__ == "__main__":
    print("Testing custom command.")
    execute_and_monitor_command("ping google.com -n 2", 30)
