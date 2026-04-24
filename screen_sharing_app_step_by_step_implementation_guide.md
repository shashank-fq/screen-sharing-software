# Screen Sharing App (Python + WebRTC) — Step-by-Step Implementation Guide

---

## 📁 Project Structure (Create First)

```
/project
  /backend
    main.py

  /client
    sender.py
    viewer.py
    webrtc.py
    capture.py
```

---

## 🧱 Step 1 — Build Backend (Signaling Server)

**File:** `/backend/main.py`

### Objective
Create a WebSocket-based signaling server.

### Tasks
1. Setup FastAPI server
2. Implement session storage (dictionary)
3. Create endpoints:
   - `/create-session`
   - `/join-session`
4. Add WebSocket route:
   - `/ws/{session_id}`
5. Relay messages between connected clients

### Success Criteria
- Sender and Viewer can connect
- Messages sent by one are received by the other

---

## 🔗 Step 2 — Establish WebRTC Connection

**File:** `/client/webrtc.py`

### Objective
Create peer-to-peer connection (no video yet)

### Tasks
1. Create RTCPeerConnection
2. Generate SDP offer (Sender)
3. Send offer via backend
4. Receive and send SDP answer (Viewer)
5. Exchange ICE candidates

### Success Criteria
- Connection state becomes `connected`
- No video required yet

---

## 🖥️ Step 3 — Implement Screen Capture

**File:** `/client/capture.py`

### Objective
Capture and prepare frames

### Tasks
1. Capture screen using mss
2. Convert frame to numpy array
3. Resize frame (important)
4. Control FPS (10–20 FPS)

### Success Criteria
- Frames are captured continuously
- Stable FPS without freezing

---

## 🎥 Step 4 — Attach Capture to WebRTC

**File:** `/client/webrtc.py`

### Objective
Send video frames over WebRTC

### Tasks
1. Create custom VideoStreamTrack
2. Pull frames from capture module
3. Feed frames into track
4. Attach track to peer connection

### Success Criteria
- Viewer starts receiving frames
- Video may be rough but working

---

## 📺 Step 5 — Viewer Rendering

**File:** `/client/viewer.py`

### Objective
Display incoming frames

### Tasks
1. Receive video track
2. Decode frames
3. Display using:
   - OpenCV window OR
   - GUI canvas

### Success Criteria
- Viewer can see sender screen

---

## 🔄 Step 6 — Improve Signaling Stability

**File:** `/backend/main.py`, `/client/webrtc.py`

### Objective
Handle real-world usage issues

### Tasks
1. Standardize message formats
2. Handle disconnects
3. Add reconnect logic

### Success Criteria
- Stable connection over time

---

## 🔐 Step 7 — Add Basic Authentication

### Objective
Control access to sessions

### Options
- Session ID only (simplest)
- Token-based login

### Success Criteria
- Only authorized users can join

---

## 🖱️ Step 8 — Integrate GUI

**Files:** `/client/sender.py`, `/client/viewer.py`

### Objective
Make application usable

### Tasks
1. Add Start/Stop buttons
2. Display session ID (Sender)
3. Add input field (Viewer)

### Success Criteria
- User can operate app without terminal

---

## 📦 Step 9 — Convert to Executable

### Objective
Package application for distribution

### Tasks
1. Use PyInstaller
2. Generate:
   - sender.exe
   - viewer.exe

### Success Criteria
- Runs without Python installed

---

## ⚡ Step 10 — Optimize Performance

### Objective
Improve usability

### Tasks
1. Reduce resolution (e.g., 540p)
2. Limit FPS (15–20)
3. Reduce CPU usage
4. Fix lag spikes

### Success Criteria
- Smooth and stable streaming

---

## 🔁 Final Execution Order (Follow Strictly)

```
Backend → WebRTC Connection → Capture → Streaming → Display → GUI → Optimize
```

---

## ⚠️ Rules to Follow

- Do NOT build GUI before streaming works
- Do NOT send raw frames manually
- Do NOT skip WebRTC connection testing
- Keep each module focused on one responsibility

---

## ✅ Definition of Done (MVP)

- Works over internet
- Viewer can see sender screen
- Stable connection
- Acceptable performance (~15 FPS)

---

This is the complete step-by-step process to build your screen sharing application.

