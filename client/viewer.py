# client/viewer.py
import asyncio
import requests
from webrtc import WebRTCViewer

HTTP_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

async def main():
    print("=== Join a Screen Share ===")
    session_id = input("Enter the Session ID: ").strip()

    # Validate session ID with backend
    try:
        response = requests.get(f"{HTTP_URL}/join-session/{session_id}")
        if response.json().get("status") != "success":
            print("Error: Invalid or expired Session ID.")
            return
    except Exception as e:
        print("Error connecting to signaling server.")
        return

    print(f"Joining session {session_id}...")
    viewer = WebRTCViewer(WS_URL, session_id)
    await viewer.connect_signaling()

    print("Waiting for stream data... (Window will open automatically)")
    print("Press 'q' in the video window or Ctrl+C here to quit.")

    try:
        while True:
            await asyncio.sleep(1) # Keep loop alive while OpenCV handles rendering
    except KeyboardInterrupt:
        print("\nDisconnecting...")

if __name__ == "__main__":
    asyncio.run(main())