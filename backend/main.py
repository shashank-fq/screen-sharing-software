# backend/main.py
import asyncio
import hashlib
import uuid
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Screen Share Signaling Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session storage
# { "sockets": [WebSocket, ...], "password_hash": str | None, "cleanup_task": Task | None }
sessions: Dict[str, dict] = {}

SESSION_TTL_SECONDS = 30


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ──────────────────────────────────────────────
# REST endpoints
# ──────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    password: Optional[str] = None


@app.post("/create-session")
async def create_session(body: CreateSessionRequest = CreateSessionRequest()):
    """Create a session, optionally protected by a password."""
    session_id = str(uuid.uuid4())[:6].upper()
    sessions[session_id] = {
        "sockets": [],
        "password_hash": _hash_password(body.password) if body.password else None,
        "cleanup_task": None,
    }
    return {"session_id": session_id}


@app.get("/join-session/{session_id}")
async def join_session(
    session_id: str,
    password: Optional[str] = Query(default=None),
):
    """Validate session existence and optional password."""
    session_id = session_id.upper()
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    if session["password_hash"] is not None:
        if password is None:
            raise HTTPException(status_code=401, detail="Password required")
        if _hash_password(password) != session["password_hash"]:
            raise HTTPException(status_code=403, detail="Incorrect password")

    return {"status": "success", "peer_count": len(session["sockets"])}


# ──────────────────────────────────────────────
# WebSocket signaling
# ──────────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    password: Optional[str] = Query(default=None),
):
    """Relay signaling messages between peers."""
    session_id = session_id.upper()

    # Auth check BEFORE accepting
    if session_id not in sessions:
        await websocket.close(code=4004, reason="Session not found")
        return

    session = sessions[session_id]
    if session["password_hash"] is not None:
        if password is None or _hash_password(password) != session["password_hash"]:
            await websocket.close(code=4003, reason="Unauthorized")
            return

    await websocket.accept()

    # Cancel any pending TTL cleanup so reconnects work
    if session["cleanup_task"] and not session["cleanup_task"].done():
        session["cleanup_task"].cancel()
        session["cleanup_task"] = None

    session["sockets"].append(websocket)
    peer_count = len(session["sockets"])
    print(f"[{session_id}] Peer connected ({peer_count} total)")

    # ── FIX: notify EXISTING peers that a new peer joined ──
    # This is what triggers the Sender to send its offer.
    if peer_count > 1:
        join_msg = '{"type": "peer_joined"}'
        for peer in session["sockets"]:
            if peer is not websocket:
                try:
                    await peer.send_text(join_msg)
                except Exception:
                    pass

    try:
        async for raw_message in websocket.iter_text():
            # Relay to every OTHER peer in the session
            for peer in list(session["sockets"]):
                if peer is not websocket:
                    try:
                        await peer.send_text(raw_message)
                    except Exception:
                        pass

    except WebSocketDisconnect:
        pass
    finally:
        if websocket in session["sockets"]:
            session["sockets"].remove(websocket)
        print(f"[{session_id}] Peer disconnected ({len(session['sockets'])} remaining)")

        # Notify remaining peers
        disconnect_msg = '{"type": "peer_disconnected"}'
        for peer in list(session["sockets"]):
            try:
                await peer.send_text(disconnect_msg)
            except Exception:
                pass

        # Schedule session cleanup after TTL
        if not session["sockets"]:
            session["cleanup_task"] = asyncio.create_task(
                _schedule_session_cleanup(session_id)
            )


async def _schedule_session_cleanup(session_id: str):
    """Remove session after TTL if no peers reconnect."""
    await asyncio.sleep(SESSION_TTL_SECONDS)
    if session_id in sessions and not sessions[session_id]["sockets"]:
        del sessions[session_id]
        print(f"[{session_id}] Session expired and removed.")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)