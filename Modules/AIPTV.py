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

def stream_url_template(AIPTV_SERVER_URL):
    return f"{AIPTV_SERVER_URL}/api/proxy/{{id}}"

def get_running_streams(AIPTV_SERVER_URL, USERNAME = None, PASSWORD = None):
    """Fetch current running streams from the API."""
    ACTIVE_CHANNELS_API = f"{AIPTV_SERVER_URL}/api/proxy/streams/active"
    watchdog_names = {}  # Initialize watchdog_names as an empty dictionary
    try:
        response = requests.get(
            ACTIVE_CHANNELS_API, 
            headers={"accept": "application/json"}
        )
        response.raise_for_status()
        streams = response.json()
        
        # Create a list of stream dictionaries
        processed_streams = [
            {
                "id": stream.get("channelId"),
                "name": stream.get("streamName"),
                "currentstream": stream.get("streamId"),
                "clients": [
                    client.get("userAgent")
                    for client in stream.get("clients", [])
                ],
                "availableStreams": [                 
                    {
                        "id": available_stream.get("id"),
                        "name": available_stream.get("name")  # Add name for each available stream
                    }
                    for available_stream in stream.get("availableStreams", [])
                ],
            }
            for stream in streams
        ]
        
        # Populate watchdog_names
        for stream in processed_streams:
            stream_id = stream.get("id")
            stream_name = stream.get("name") or "Unknown Channel"
            if stream_id:
                watchdog_names[stream_id] = stream_name  # Store name by stream ID

        return processed_streams, watchdog_names  # Return both values
    except requests.exceptions.RequestException as e:
        print(f"HTTP error occurred: {e}")
    except Exception as e:
        print(f"Unexpected error fetching streams from {ACTIVE_CHANNELS_API}: {e}")
    return [], {}  # Return empty structures on failure


def send_next_stream(channel_id,AIPTV_SERVER_URL, USERNAME = None, PASSWORD = None):
    """Switch to the next available stream for a given channel ID."""
    streams, watchdog_names = get_running_streams(AIPTV_SERVER_URL)  # Fetch all streams

    # Transform the list of streams into a dictionary keyed by 'id'
    streams_by_id = {stream["id"]: stream for stream in streams}
    # Check if the channel_id exists in the streams dictionary
    if channel_id in streams_by_id:
        # Get the current stream ID for the given channel
        current_stream_id = streams_by_id[channel_id].get("currentstream")
        available_streams = streams_by_id[channel_id].get("availableStreams", [])       
        # Find the next available stream after the current one
        next_stream_id = find_next_stream_after_current(available_streams, current_stream_id)       
        # If a next stream is found, proceed to switch
        if next_stream_id != current_stream_id:
            url = f"{AIPTV_SERVER_URL}/api/proxy/stream/{channel_id}/switch"
            headers = {
                "accept": "application/json",
                "Content-Type": "application/json"
            }
            payload = {"streamId": next_stream_id}           
            response = requests.post(url, json=payload, headers=headers)            
            if response.status_code == 200:
                #print(f"Stream switched successfully to {next_stream_id}: {response.json()}")
                return True
            else:
                print(f"Error switching stream: {response.text}")
                #print(f"Payload: {payload}")
                return False
        else:
            print(f"No next available stream found for channel {channel_id}.")
            return False
    else:
        print(f"Channel with ID {channel_id} not found.")
        return False

def find_next_stream_after_current(available_streams, current_stream_id, USERNAME = None, PASSWORD = None):
    """Find the next available stream after the current one in the list."""
    # Transform available streams to a list of dictionaries
    available_streams_by_id = {stream["id"]: stream for stream in available_streams}   
    # Check if the current stream ID exists in the available streams
    if current_stream_id in available_streams_by_id:
        # Find the list of available stream IDs
        available_stream_ids = list(available_streams_by_id.keys())
        
        # Find the index of the current stream in the list of available stream IDs
        current_index = available_stream_ids.index(current_stream_id)        
        # If there's a next stream in the list, return it
        if current_index + 1 < len(available_stream_ids):
            next_stream_id = available_stream_ids[current_index + 1]
            return next_stream_id  # Return the next stream dictionary
        elif current_index +1 == len(available_stream_ids):
            next_stream_id = available_stream_ids[0]
            return next_stream_id # Return the first stream in the dictionary after reaching the end         
    return None  # Return None if no next stream is found

# Test the function
#if __name__ == "__main__":
    #AIPTV_SERVER_URL = os.getenv("SERVER_URL", "http://SERVERNAME:5002")
    #channel_id = "a159c90e-f5fe1d7d"  # Replace with an actual channel ID for testing
    #send_next_stream(channel_id, AIPTV_SERVER_URL)