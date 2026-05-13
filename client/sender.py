# client/sender.py
"""
Step 8 — Sender GUI
Tkinter interface: create session, display/copy session ID, optional password,
start/stop streaming, live connection status.
"""
import asyncio
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import requests

from webrtc import WebRTCSender

HTTP_URL = "https://signal.shashankfq.app"
WS_URL = "wss://signal.shashankfq.app"


class SenderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Screen Share — Sender")
        self.resizable(False, False)
        self.configure(bg="#1e1e2e")

        # Internal state
        self._session_id: str = ""
        self._password: str = ""
        self._sender: WebRTCSender = None
        self._loop: asyncio.AbstractEventLoop = None
        self._thread: threading.Thread = None
        self._streaming = False

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ──────────────────────────────────────
 
    def _build_ui(self):
        PAD = {"padx": 18, "pady": 10}
        BG = "#1e1e2e"
        FG = "#cdd6f4"
        ACCENT = "#89b4fa"
        PANEL = "#313244"
        BTN_START = "#a6e3a1"
        BTN_STOP = "#f38ba8"
        FONT = ("Segoe UI", 10)
        FONT_BIG = ("Segoe UI", 14, "bold")
        FONT_MONO = ("Consolas", 22, "bold")

        # ── Header ──
        tk.Label(self, text="📡  Screen Share", font=FONT_BIG,
                 bg=BG, fg=ACCENT).pack(pady=(20, 4))
        tk.Label(self, text="Share your screen in one click.",
                 font=FONT, bg=BG, fg=FG).pack(pady=(0, 16))

        # ── Password frame ──
        pw_frame = tk.Frame(self, bg=PANEL, padx=16, pady=12)
        pw_frame.pack(fill="x", padx=20, pady=(0, 8))

        tk.Label(pw_frame, text="Session Password (optional):",
                 font=FONT, bg=PANEL, fg=FG).grid(row=0, column=0, sticky="w")

        self._pw_var = tk.StringVar()
        pw_entry = tk.Entry(pw_frame, textvariable=self._pw_var,
                            show="●", font=FONT, width=12,
                            bg="#45475a", fg=FG, insertbackground=FG,
                            relief="flat", bd=4)
        pw_entry.grid(row=0, column=1, padx=(10, 0))

        # ── Session ID panel ──
        id_frame = tk.Frame(self, bg=PANEL, padx=16, pady=16)
        id_frame.pack(fill="x", padx=20, pady=(0, 10))

        tk.Label(id_frame, text="Session ID", font=FONT, bg=PANEL, fg=FG).pack()

        self._session_label = tk.Label(
            id_frame, text="——", font=FONT_MONO, bg=PANEL, fg=ACCENT
        )
        self._session_label.pack(pady=4)

        self._copy_btn = tk.Button(
            id_frame, text="📋 Copy ID", font=FONT,
            bg="#45475a", fg=FG, activebackground="#585b70", relief="flat",
            bd=0, padx=12, pady=4, cursor="hand2",
            command=self._copy_id, state="disabled"
        )
        self._copy_btn.pack()

        # ── Status ──
        status_frame = tk.Frame(self, bg=BG)
        status_frame.pack(pady=(4, 0))

        tk.Label(status_frame, text="Status: ", font=FONT, bg=BG, fg=FG).pack(side="left")
        self._status_var = tk.StringVar(value="Idle")
        self._status_label = tk.Label(
            status_frame, textvariable=self._status_var,
            font=("Segoe UI", 10, "bold"), bg=BG, fg="#a6e3a1"
        )
        self._status_label.pack(side="left")

        # ── Buttons ──
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(pady=18)

        self._start_btn = tk.Button(
            btn_frame, text="▶  Start Sharing", font=("Segoe UI", 11, "bold"),
            bg=BTN_START, fg="#1e1e2e", activebackground="#94d29a",
            relief="flat", bd=0, padx=20, pady=8, cursor="hand2",
            command=self._start_sharing
        )
        self._start_btn.grid(row=0, column=0, padx=8)

        self._stop_btn = tk.Button(
            btn_frame, text="⏹  Stop Sharing", font=("Segoe UI", 11, "bold"),
            bg=BTN_STOP, fg="#1e1e2e", activebackground="#e37a96",
            relief="flat", bd=0, padx=20, pady=8, cursor="hand2",
            command=self._stop_sharing, state="disabled"
        )
        self._stop_btn.grid(row=0, column=1, padx=8)

        # ── Footer ──
        tk.Label(self, text="Viewer must have the session ID to connect.",
                 font=("Segoe UI", 8), bg=BG, fg="#6c7086").pack(pady=(0, 14))

        self.geometry("700x660")

    # ── Actions ─────────────────────────────────────────────

    def _set_status(self, text: str, color: str = "#a6e3a1"):
        self._status_var.set(text)
        self._status_label.config(fg=color)

    def _on_webrtc_status(self, state: str):
        """Called from the async thread; schedule update on the Tk main thread."""
        color_map = {
            "connected": "#a6e3a1",
            "connecting": "#f9e2af",
            "disconnected": "#f38ba8",
            "failed": "#f38ba8",
            "reconnecting": "#f9e2af",
            "viewer_disconnected": "#f9e2af",
        }
        label_map = {
            "connected": "Connected ✓",
            "connecting": "Connecting…",
            "disconnected": "Disconnected",
            "failed": "Failed ✗",
            "reconnecting": "Reconnecting…",
            "viewer_disconnected": "Waiting for viewer…",
        }
        self.after(0, lambda: self._set_status(
            label_map.get(state, state),
            color_map.get(state, "#cdd6f4")
        ))

    def _start_sharing(self):
        password = self._pw_var.get().strip()

        # Create session
        try:
            payload = {"password": password} if password else {}
            resp = requests.post(f"{HTTP_URL}/create-session", json=payload, timeout=5)
            resp.raise_for_status()
            self._session_id = resp.json()["session_id"]
            self._password = password
        except Exception as e:
            messagebox.showerror("Connection Error",
                                 f"Could not reach signaling server.\n\nIs backend running?\n\n{e}")
            return

        self._session_label.config(text=self._session_id)
        self._copy_btn.config(state="normal")
        self._start_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._set_status("Waiting for viewer…", "#f9e2af")

        # Start async streaming in background thread
        self._streaming = True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_async, daemon=True)
        self._thread.start()

    def _run_async(self):
        asyncio.set_event_loop(self._loop)
        self._sender = WebRTCSender(WS_URL, self._session_id, self._password)
        self._sender.on_status_change = self._on_webrtc_status
        try:
            self._loop.run_until_complete(self._sender.connect_signaling())
        except Exception as e:
            print(f"[Sender] Async error: {e}")

    def _stop_sharing(self):
        self._streaming = False
        if self._sender:
            self._sender.stop()
            self._sender = None
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        self._session_label.config(text="——")
        self._copy_btn.config(state="disabled")
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._set_status("Idle")

    def _copy_id(self):
        self.clipboard_clear()
        self.clipboard_append(self._session_id)
        self._copy_btn.config(text="✓ Copied!")
        self.after(2000, lambda: self._copy_btn.config(text="📋 Copy ID"))

    def _on_close(self):
        self._stop_sharing()
        self.destroy()


if __name__ == "__main__":
    app = SenderApp()
    app.mainloop()