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

import requests

# Maintain running processes, speeds, and buffering timers with stream names
watchdog_names = {}  # Store stream names

def stream_url_template(SERVER_URL):
    return f"{SERVER_URL}/v/0/{{id}}"

def get_running_streams(stream_master_url):
    """Fetch current running streams from the API."""
    try:
        CHANNEL_METRICS_API_URL = f"{stream_master_url}/api/statistics/getchannelmetrics"
        response = requests.get(CHANNEL_METRICS_API_URL, headers={"accept": "application/json"})
        response.raise_for_status()
        streams = response.json()
        
        # Update the watchdog_names dictionary with stream names
        for stream in streams:
            stream_id = stream.get("id") or stream.get("Id")
            stream_name = stream.get("name") or stream.get("Name", "Unknown Channel")
            if stream_id:
                watchdog_names[stream_id] = stream_name  # Store name by stream ID
        
        return [
            {
                "id": stream.get("id") or stream.get("Id"),  # Handle both "id" and "Id"
                "name": stream.get("name") or stream.get("Name", "Unknown Channel"),  # Handle both "name" and "Name"
                "clients": [
                    client.get("clientUserAgent") or client.get("ClientUserAgent", "") 
                    for client in stream.get("clientStreams") or stream.get("ClientStreams", [])
                ],
            }
            for stream in streams if not stream.get("isFailed", False)
        ], watchdog_names  # Return both the streams and the dictionary
    except Exception as e:
        print(f"Error fetching streams: {e}")
        return [], {}  # Return empty structures on failure
    
def send_next_stream(stream_id, stream_master_url):
    """Handle the buffering event by switching to the next stream."""
    try:
        NEXT_STREAM_API_URL = f"{stream_master_url}/api/streaming/movetonextstream"
        # Trigger the next stream switch
        payload = {"SMChannelId": stream_id}
        response = requests.patch(
            NEXT_STREAM_API_URL,
            json=payload,
            headers={
                "accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        result = response.json()  # Parse the JSON response
        # Log the result of switching the stream
        if not result.get("isError", True) or not result.get("IsError", True):
            return True
        else:
            return False

    except Exception as e:
        print(f"Error switching to the next stream for channel {stream_id}: {e}")
        return False
    