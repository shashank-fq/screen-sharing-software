# backend/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List
import uuid
import uvicorn

app = FastAPI()

# Session storage: Maps session_id to connected WebSockets
sessions: Dict[str, List[WebSocket]] = {}

@app.post("/create-session")
async def create_session():
    """Step 1: Create a session."""
    session_id = str(uuid.uuid4())[:6]  # Short ID for easy sharing
    sessions[session_id] = []
    return {"session_id": session_id}

@app.get("/join-session/{session_id}")
async def join_session(session_id: str):
    """Step 1: Validate session existence."""
    if session_id in sessions:
        return {"status": "success"}
    return {"status": "error", "message": "Session not found"}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """Relays signaling messages between peers."""
    await websocket.accept()
    
    if session_id not in sessions:
        sessions[session_id] = []
    sessions[session_id].append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            # Broadcast to the other peer in the session
            for client in sessions[session_id]:
                if client != websocket:
                    await client.send_text(data)
    except WebSocketDisconnect:
        sessions[session_id].remove(websocket)
        if not sessions[session_id]:
            del sessions[session_id]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)