# client/webrtc.py
import asyncio
import json
import queue
import websockets
import cv2
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCIceCandidate
from av import VideoFrame
from capture import ScreenCapture

MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_BACKOFF_BASE = 2


class ScreenStreamTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.capture = ScreenCapture(fps=15, resize_scale=0.5)

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        loop = asyncio.get_running_loop()
        frame_array = await loop.run_in_executor(None, self.capture.get_frame)
        video_frame = VideoFrame.from_ndarray(frame_array, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame


class WebRTCSession:
    def __init__(self, signaling_url: str, session_id: str, password: str = ""):
        self.signaling_url = signaling_url
        self.session_id = session_id
        self.password = password
        self.pc: RTCPeerConnection = None
        self.websocket = None
        self._running = False
        self._loop: asyncio.AbstractEventLoop = None
        self.on_status_change = None

    def _build_ws_url(self) -> str:
        url = f"{self.signaling_url}/ws/{self.session_id}"
        if self.password:
            url += f"?password={self.password}"
        return url

    def _create_peer_connection(self):
        self.pc = RTCPeerConnection()

        @self.pc.on("connectionstatechange")
        async def on_state():
            state = self.pc.connectionState
            print(f"[WebRTC] State: {state}")
            if self.on_status_change:
                self.on_status_change(state)

        @self.pc.on("icecandidate")
        async def on_ice(candidate):
            if candidate and self.websocket:
                try:
                    await self.websocket.send(json.dumps({
                        "type": "ice",
                        "candidate": candidate.to_sdp(),
                        "sdpMid": candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex,
                    }))
                except Exception as e:
                    print(f"[ICE] Send failed: {e}")

    async def connect_signaling(self):
        self._running = True
        self._loop = asyncio.get_running_loop()
        attempt = 0

        while self._running and attempt <= MAX_RECONNECT_ATTEMPTS:
            try:
                ws_url = self._build_ws_url()
                print(f"[Signaling] Connecting (attempt {attempt + 1})")
                self.websocket = await websockets.connect(ws_url)
                print("[Signaling] Connected.")
                await self.listen_signaling()
            except (websockets.exceptions.ConnectionClosed,
                    websockets.exceptions.WebSocketException,
                    OSError) as e:
                print(f"[Signaling] Lost: {e}")

            if not self._running:
                break

            attempt += 1
            if attempt <= MAX_RECONNECT_ATTEMPTS:
                wait = RECONNECT_BACKOFF_BASE ** attempt
                print(f"[Signaling] Retry in {wait}s ({attempt}/{MAX_RECONNECT_ATTEMPTS})")
                if self.on_status_change:
                    self.on_status_change("reconnecting")
                await asyncio.sleep(wait)
            else:
                print("[Signaling] Max retries reached.")
                if self.on_status_change:
                    self.on_status_change("failed")

    async def listen_signaling(self):
        raise NotImplementedError

    async def _handle_ice(self, data: dict):
        if self.pc is None:
            return
        try:
            candidate = RTCIceCandidate(
                sdpMid=data.get("sdpMid"),
                sdpMLineIndex=data.get("sdpMLineIndex"),
                candidate=data.get("candidate", ""),
            )
            await self.pc.addIceCandidate(candidate)
        except Exception as e:
            print(f"[ICE] Add failed: {e}")

    def stop(self):
        self._running = False
        if self._loop and not self._loop.is_closed():
            if self.websocket:
                asyncio.run_coroutine_threadsafe(self.websocket.close(), self._loop)
            if self.pc:
                asyncio.run_coroutine_threadsafe(self.pc.close(), self._loop)


class WebRTCSender(WebRTCSession):

    async def _make_offer(self):
        """Create a fresh PC, add track, and send offer."""
        if self.pc:
            await self.pc.close()
        self._create_peer_connection()
        self.pc.addTrack(ScreenStreamTrack())
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        await self.websocket.send(json.dumps({
            "type": self.pc.localDescription.type,
            "sdp": self.pc.localDescription.sdp,
        }))
        print("[Sender] Offer sent.")

    async def listen_signaling(self):
        print("[Sender] Waiting for viewer to join…")
        if self.on_status_change:
            self.on_status_change("waiting")

        try:
            async for raw in self.websocket:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")

                if msg_type == "peer_joined":
                    print("[Sender] Viewer joined — sending offer.")
                    if self.on_status_change:
                        self.on_status_change("connecting")
                    await self._make_offer()

                elif msg_type == "answer":
                    if self.pc:
                        answer = RTCSessionDescription(sdp=data["sdp"], type="answer")
                        await self.pc.setRemoteDescription(answer)
                        print("[Sender] Answer applied. Stream live!")

                elif msg_type == "ice":
                    await self._handle_ice(data)

                elif msg_type == "peer_disconnected":
                    print("[Sender] Viewer disconnected.")
                    if self.on_status_change:
                        self.on_status_change("viewer_disconnected")

        except websockets.exceptions.ConnectionClosed:
            print("[Sender] Signaling closed.")
        except Exception as e:
            print(f"[Sender] Signaling error: {e}")


class WebRTCViewer(WebRTCSession):
    def __init__(self, signaling_url: str, session_id: str, password: str = ""):
        super().__init__(signaling_url, session_id, password)
        # Frames are placed here; the GUI polls and renders from the main thread
        self.frame_queue: queue.Queue = queue.Queue(maxsize=4)

    def _create_peer_connection(self):
        super()._create_peer_connection()

        @self.pc.on("track")
        def on_track(track):
            print(f"[Viewer] Track received: {track.kind}")
            if track.kind == "video":
                asyncio.ensure_future(self._consume_video(track))

    async def _consume_video(self, track):
        """Decode frames and put them into frame_queue for the GUI to render."""
        print("[Viewer] Video stream started.")
        try:
            while self._running:
                frame = await track.recv()
                img = frame.to_ndarray(format="bgr24")
                # Non-blocking put — drop frame if GUI is slow
                try:
                    self.frame_queue.put_nowait(img)
                except queue.Full:
                    pass
        except Exception as e:
            print(f"[Viewer] Stream ended: {e}")
        finally:
            print("[Viewer] Video consumer exited.")

    async def listen_signaling(self):
        print("[Viewer] Waiting for offer…")
        if self.on_status_change:
            self.on_status_change("connecting")

        # Create the PC once when signaling is established
        self._create_peer_connection()

        try:
            async for raw in self.websocket:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type")

                if msg_type == "offer":
                    print("[Viewer] Offer received. Creating answer…")
                    offer = RTCSessionDescription(sdp=data["sdp"], type="offer")
                    await self.pc.setRemoteDescription(offer)
                    answer = await self.pc.createAnswer()
                    await self.pc.setLocalDescription(answer)
                    await self.websocket.send(json.dumps({
                        "type": self.pc.localDescription.type,
                        "sdp": self.pc.localDescription.sdp,
                    }))
                    print("[Viewer] Answer sent.")

                elif msg_type == "ice":
                    await self._handle_ice(data)

                elif msg_type == "peer_disconnected":
                    print("[Viewer] Sender disconnected.")
                    if self.on_status_change:
                        self.on_status_change("sender_disconnected")

        except websockets.exceptions.ConnectionClosed:
            print("[Viewer] Signaling closed.")
        except Exception as e:
            print(f"[Viewer] Signaling error: {e}")