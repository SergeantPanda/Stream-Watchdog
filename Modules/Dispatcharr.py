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
import time

session = None
refresh_token = None
token_expiry = 0  # Track when token will expire

def stream_url_template(SERVER_URL):
    return f"{SERVER_URL}/proxy/ts/stream/{{id}}"

def login(dispatcharr_url, USERNAME, PASSWORD):
    global session, refresh_token, token_expiry
    if session is None:
        session = requests.Session()
        if USERNAME is None:
            # Return an empty session if no username is supplied
            print(f"No credentials provided, skipping login.")
            return requests.session()
        # Define login URL and credentials
        login_url = f"{dispatcharr_url}/api/accounts/token/"
        credentials = {"username": USERNAME, "password": PASSWORD}
        # Perform the login
        try:
            response = session.post(login_url, data=credentials)
            if response.status_code == 200:
                print(f"Successfully logged in!")
                tokens = response.json()
                session.headers.update({"Authorization": f"Bearer {tokens['access']}"})  # Add access token to headers
                refresh_token = tokens.get('refresh')  # Store refresh token
                token_expiry = time.time() + 1800  # Set expiry to 30 minutes from now
            elif response.status_code == 400:
                print(f"Invalid credentials provided!")
                return None
            else:
                print(f"Unexpected response during login: {response.status_code}")
                return None
        except requests.exceptions.ConnectionError as e:
            print(f"Unable to connect to Dispatcharr! Error: {e}")
            return None
        except Exception as e:
            print(f"Error logging in: {e}")
            return None

    return session

def refresh_access_token(dispatcharr_url):
    """Refresh the access token using the refresh token."""
    global session, refresh_token, token_expiry

    if not refresh_token:
        print("No refresh token available. Need to login again.")
        return False

    refresh_url = f"{dispatcharr_url}/api/accounts/token/refresh/"
    payload = {"refresh": refresh_token}

    try:
        # Use a new session for this request to avoid using expired headers
        temp_session = requests.Session()
        response = temp_session.post(refresh_url, json=payload)

        if response.status_code == 200:
            tokens = response.json()
            session.headers.update({"Authorization": f"Bearer {tokens['access']}"})
            # Update refresh token if a new one is provided
            if 'refresh' in tokens:
                refresh_token = tokens['refresh']
            token_expiry = time.time() + 1800  # Reset expiry time
            print("Access token refreshed successfully")
            return True
        else:
            print(f"Failed to refresh token: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error refreshing token: {e}")
        return False

def get_running_streams(dispatcharr_url, USERNAME=None, PASSWORD=None):
    """Fetch current running streams from the API."""
    global session, token_expiry
    watchdog_names = {}  # Store stream names
    headers = {"Accept": "application/json"}
    try:
        CHANNEL_METRICS_API_URL = f"{dispatcharr_url}/proxy/ts/status"

        # Check if we have a session and if we need to refresh the token
        if session is None:
            session = login(dispatcharr_url, USERNAME, PASSWORD)
        elif time.time() > token_expiry - 60:  # Refresh 1 minute before expiry
            if not refresh_access_token(dispatcharr_url):
                # If refresh fails, try to login again
                session = login(dispatcharr_url, USERNAME, PASSWORD)

        # Check if session was returned indicating login is successful or not needed
        if session is None:
            # Connection error return empty response to not crash watchdog
            return [], {}

        # Merge session headers with additional headers
        merged_headers = {**session.headers, **headers}

        response = session.get(CHANNEL_METRICS_API_URL, headers=merged_headers)

        # Handle potential token expiration
        if response.status_code == 401:
            print("Token appears expired. Attempting refresh...")
            if refresh_access_token(dispatcharr_url):
                # Retry the request with refreshed token
                merged_headers = {**session.headers, **headers}
                response = session.get(CHANNEL_METRICS_API_URL, headers=merged_headers)
            else:
                # If refresh failed, try logging in again
                session = login(dispatcharr_url, USERNAME, PASSWORD)
                if session is not None:
                    merged_headers = {**session.headers, **headers}
                    response = session.get(CHANNEL_METRICS_API_URL, headers=merged_headers)

        response.raise_for_status()
        # Ensure the response status code is 200
        if response.status_code != 200:
            print(f"Unexpected response status: {response.status_code}")
            return [], {}
        data = response.json()

        # Parse the new data structure
        channels = data.get("channels", [])
        for channel in channels:
            channel_id = channel.get("channel_id")
            stream_name = channel.get("stream_name", "Unknown Name")
            if channel_id:
                watchdog_names[channel_id] = stream_name  # Store name by channel ID

        return [
            {
                "id": channel.get("channel_id"),
                "name": channel.get("stream_name", "Unknown Name"),
                "clients": [
                    client.get("user_agent", "")
                    for client in channel.get("clients", [])
                ],
            }
            for channel in channels if channel.get("state") == "active"
        ], watchdog_names  # Return both the streams and the dictionary
    except Exception as e:
        print(f"Error fetching streams: {e}")
        session = None
        return [], {}  # Return empty structures on failure

def send_next_stream(channel_id, dispatcharr_url, USERNAME = None, PASSWORD = None):
    """Handle the buffering event by switching to the next stream."""
    global session, token_expiry
    try:
        NEXT_STREAM_API_URL = f"{dispatcharr_url}/proxy/ts/next_stream/{channel_id}"
        print(f"Url to switch stream: {NEXT_STREAM_API_URL}")

        # Check if we have a session and if we need to refresh the token
        if session is None:
            session = login(dispatcharr_url, USERNAME, PASSWORD)
        elif time.time() > token_expiry - 60:  # Refresh 1 minute before expiry
            if not refresh_access_token(dispatcharr_url):
                # If refresh fails, try to login again
                session = login(dispatcharr_url, USERNAME, PASSWORD)

        # Check if session was returned indicating login is successful
        if session is None:
            return False

        response = session.post(
            NEXT_STREAM_API_URL,
            headers={
                "accept": "application/json",
                "Content-Type": "application/json",
            },
        )

        # Handle potential token expiration
        if response.status_code == 401:
            print("Token appears expired. Attempting refresh...")
            if refresh_access_token(dispatcharr_url):
                # Retry the request with refreshed token
                response = session.post(
                    NEXT_STREAM_API_URL,
                    headers={
                        "accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
            else:
                # If refresh failed, try logging in again
                session = login(dispatcharr_url, USERNAME, PASSWORD)
                if session is not None:
                    response = session.post(
                        NEXT_STREAM_API_URL,
                        headers={
                            "accept": "application/json",
                            "Content-Type": "application/json",
                        },
                    )

        response.raise_for_status()
        result = response.json()  # Parse the JSON response
        # Log the result of switching the stream
        if result.get("message", 'Stream switched to next available'):
            return True
        else:
            return False

    except Exception as e:
        print(f"Error switching to the next stream for channel {channel_id}: {e}")
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
    #print(f"{send_next_stream(os.getenv('CHANNEL_ID'), os.getenv('SERVER_URL'), os.getenv('USERNAME'), os.getenv('PASSWORD'))}")