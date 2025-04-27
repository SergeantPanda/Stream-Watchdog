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

import requests

session = None

def stream_url_template(SERVER_URL):
    return f"{SERVER_URL}/v/0/{{id}}"

def login(stream_master_url, USERNAME, PASSWORD):
    global session
    if session is None:
        session = requests.Session()
        if USERNAME is None:
            # Return an empty session if no username is supplied
            print(f"No credentials provided, skipping login.")
            return requests.session()
        # Define login URL and credentials
        login_url = f"{stream_master_url}/login"
        credentials = {"username": USERNAME, "password": PASSWORD}
        # Perform the login
        try:
            session.post(login_url, data=credentials)
        except requests.exceptions.ConnectionError as e:
            print(f"Unable to connect to Stream Master! Error: {e}")
            return None
        except Exception as e:
            print(f"Error logging in: {e}")
            return None
        if not session.cookies:
            print(f"Failed to log in, please verify username and password!")
            return None
        else:
            print(f"Successfully logged in!")

    return session

def get_running_streams(stream_master_url, USERNAME = None, PASSWORD= None):
    """Fetch current running streams from the API."""
    global session
    watchdog_names = {}  # Store stream names
    headers = {"Accept": "application/json"}
    try:
        CHANNEL_METRICS_API_URL = f"{stream_master_url}/api/statistics/getchannelmetrics"
        session = login(stream_master_url, USERNAME, PASSWORD)
        # Check if session was returned indicating login is successful or not needed
        if session is None:
            # Connection error return empty response to not crash watchdog
            return [],{}
        response = session.get(CHANNEL_METRICS_API_URL, headers=headers, allow_redirects=False)
        response.raise_for_status()
        # Check if a redirect occured indicating a login might be required
        if response.is_redirect:
            #if response.next.path_url == '/login':
            redirect_location = response.headers.get("Location", "")
            if "/login" in redirect_location:
                print("Login page detected, is authentication enabled in Stream Master?")
            else:
                print(f"Redirect detected to: {redirect_location}, is authentication enabled in Stream Master?")
            # Stop processing response and return empty
            return [],{}
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
        session = None
        return [], {}  # Return empty structures on failure

def send_next_stream(stream_id, stream_master_url, USERNAME = None, PASSWORD = None):
    """Handle the buffering event by switching to the next stream."""
    try:
        NEXT_STREAM_API_URL = f"{stream_master_url}/api/streaming/movetonextstream"
        # Trigger the next stream switch
        session = login(stream_master_url, USERNAME, PASSWORD)
        payload = {"SMChannelId": stream_id}
        response = session.patch(
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

if __name__ == "__main__":
    import os
    # Print USERNAME and PASSWORD being attempted
    print(f"The following credentials will be attempted for the login: USERNAME: '{os.getenv('USERNAME')}' PASSWORD: '{os.getenv('PASSWORD')}'")
    # Print cookies during test.
    print(f"Cookie returned after login attempt:")
    print(f"{login(os.getenv('SERVER_URL'), os.getenv('USERNAME'), os.getenv('PASSWORD')).cookies}")
    # Print get_running_streams return
    print(f"Currently running streams returned from API:")
    print(f"{get_running_streams(os.getenv('SERVER_URL'), os.getenv('USERNAME'), os.getenv('PASSWORD'))}")