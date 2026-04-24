# client/sender.py
import asyncio
import requests
from webrtc import WebRTCSender

HTTP_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

async def main():
    print("Initializing Screen Share...")
    
    # Contact backend to create session
    try:
        response = requests.post(f"{HTTP_URL}/create-session")
        session_id = response.json().get("session_id")
    except Exception as e:
        print("Error connecting to signaling server. Is it running?")
        return

    print("\n" + "="*30)
    print(f"SESSION CREATED SUCCESSFULLY")
    print(f"Share this ID with the Viewer: {session_id}")
    print("="*30 + "\n")

    sender = WebRTCSender(WS_URL, session_id)
    await sender.connect_signaling()
    await sender.start_streaming()

    print("Streaming started. Waiting for viewer to connect...")
    print("Press Ctrl+C to stop sharing.")

    try:
        while True:
            await asyncio.sleep(3600)  # Keep event loop running
    except KeyboardInterrupt:
        print("\nStopping screen share...")

if __name__ == "__main__":
    asyncio.run(main())
    