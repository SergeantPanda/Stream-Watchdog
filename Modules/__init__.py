import requests

AIPTV_SERVER_URL = "http://10.0.0.10:5002"
ACTIVE_CHANNELS_API = f"{AIPTV_SERVER_URL}/api/proxy/streams/active"

def get_running_streams():
    """Fetch current running streams from the API."""
    try:
        response = requests.get(
            ACTIVE_CHANNELS_API, 
            headers={"accept": "application/json"}
        )
        response.raise_for_status()
        streams = response.json()
        
        # Create a dictionary with streamId as the key and stream details as the value
        streams_by_id = {
            stream.get("channelId"): {
                "id": stream.get("channelId"),
                "name": stream.get("channelName"),
                "currentstream": stream.get("streamId"),
                "clients": [
                    client.get("userAgent")
                    for client in stream.get("clients", [])
                ],
                "availableStreams": [
                    available_stream.get("id")
                    for available_stream in stream.get("availableStreams", [])
                ],
            }
            for stream in streams
        }
        
        return streams_by_id
    except requests.exceptions.RequestException as e:
        print(f"HTTP error occurred: {e}")
    except Exception as e:
        print(f"Unexpected error fetching streams from {ACTIVE_CHANNELS_API}: {e}")
    return {}  # Return an empty dictionary on failure

def switch_stream(channel_id):
    """Switch to the next available stream for a given channel ID."""
    streams_by_id = get_running_streams()  # Fetch all streams
    
    # Check if the channel_id exists in the streams dictionary
    if channel_id in streams_by_id:
        # Get the current stream ID for the given channel
        current_stream_id = streams_by_id[channel_id].get("currentstream")
        available_streams = streams_by_id[channel_id].get("availableStreams", [])
        
        # Find the next available stream after the current one
        next_stream_id = find_next_stream_after_current(streams_by_id, current_stream_id)
        
        # If a next stream is found, proceed to switch
        if next_stream_id:
            url = f"{AIPTV_SERVER_URL}/api/proxy/stream/{channel_id}/switch"
            headers = {
                "accept": "application/json",
                "Content-Type": "application/json"
            }
            payload = {"streamId": next_stream_id}
            
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                print(f"Stream switched successfully to {next_stream_id}: {response.json()}")
            else:
                print(f"Error switching stream: {response.text}")
                print(f"Payload: {payload}")
        else:
            print(f"No next available stream found for channel {channel_id}.")
    else:
        print(f"Channel with ID {channel_id} not found.")


def find_next_stream_after_current(streams_by_id, current_stream_id):
    """Find the next available stream after the current one in the list."""
    # Loop through each stream in the dictionary
    for stream_id, stream in streams_by_id.items():
        # Find if the stream contains available streams
        available_streams = stream.get("availableStreams", [])
        
        # Check if the current stream is in the list of available streams
        if current_stream_id in available_streams:
            # Find the index of the current stream in the available streams list
            current_index = available_streams.index(current_stream_id)
            
            # If there's a next stream in the list, return it
            if current_index + 1 < len(available_streams):
                return available_streams[current_index + 1]
            
    return None  # Return None if no next stream is found


# Test the function
if __name__ == "__main__":
    streams = get_running_streams()
    #current_stream_id = "100eb6bf"  # The current stream ID you're connected to
    #switch_stream("e0939aa0-b1a6d793")
    #next_stream_id = find_next_stream_after_current(streams, current_stream_id)
    #print(f"Next available stream ID after {current_stream_id}: {next_stream_id}")
    print(streams)
