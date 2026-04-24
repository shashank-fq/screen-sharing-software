# client/webrtc.py
import asyncio
import json
import websockets
import cv2
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame
from capture import ScreenCapture 

class ScreenStreamTrack(VideoStreamTrack):
    """Step 4: Attach capture to WebRTC."""
    def __init__(self):
        super().__init__()
        self.capture = ScreenCapture(fps=15, resize_scale=0.5)

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        loop = asyncio.get_event_loop()
        frame_array = await loop.run_in_executor(None, self.capture.get_frame)

        video_frame = VideoFrame.from_ndarray(frame_array, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

class WebRTCSession:
    def __init__(self, signaling_url, session_id):
        self.signaling_url = signaling_url
        self.session_id = session_id
        self.pc = RTCPeerConnection()
        self.websocket = None

    async def connect_signaling(self):
        ws_url = f"{self.signaling_url}/ws/{self.session_id}"
        self.websocket = await websockets.connect(ws_url)
        asyncio.create_task(self.listen_signaling())

    async def listen_signaling(self):
        raise NotImplementedError

class WebRTCSender(WebRTCSession):
    async def listen_signaling(self):
        try:
            async for message in self.websocket:
                data = json.loads(message)
                if data["type"] == "answer":
                    answer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                    await self.pc.setRemoteDescription(answer)
        except websockets.exceptions.ConnectionClosed:
            print("Signaling disconnected.")

    async def start_streaming(self):
        self.pc.addTrack(ScreenStreamTrack())
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        await self.websocket.send(json.dumps({
            "type": self.pc.localDescription.type,
            "sdp": self.pc.localDescription.sdp
        }))

class WebRTCViewer(WebRTCSession):
    def __init__(self, signaling_url, session_id):
        super().__init__(signaling_url, session_id)
        
        @self.pc.on("track")
        def on_track(track):
            print("Receiving remote screen...")
            asyncio.ensure_future(self.consume_video(track))

        @self.pc.on("icecandidate")
        async def on_icecandidate(candidate):
            if candidate:
                await self.websocket.send(json.dumps({
                    "type": "ice",
                    "candidate": {
                        "candidate": candidate.to_sdp(),
                        "sdpMid": candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex
                    }
                }))

    async def consume_video(self, track):
        """Step 5: Viewer Rendering via OpenCV."""
        try:
            while True:
                frame = await track.recv()
                img = frame.to_ndarray(format="bgr24")
                cv2.imshow(f"Screen Share - Session: {self.session_id}", img)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        except Exception as e:
            print(f"Stream ended: {e}")
        finally:
            cv2.destroyAllWindows()

    async def listen_signaling(self):
        try:
            async for message in self.websocket:
                data = json.loads(message)
                if data["type"] == "offer":
                    offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                    await self.pc.setRemoteDescription(offer)
                    answer = await self.pc.createAnswer()
                    await self.pc.setLocalDescription(answer)
                    await self.websocket.send(json.dumps({
                        "type": self.pc.localDescription.type,
                        "sdp": self.pc.localDescription.sdp
                    }))
        except websockets.exceptions.ConnectionClosed:
             print("Signaling disconnected.")