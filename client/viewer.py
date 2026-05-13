# client/viewer.py
"""
Step 8 — Viewer GUI
Tkinter interface: enter session ID + optional password, connect/disconnect,
live status. Video is rendered inside the tkinter window via a canvas + PIL,
so cv2.imshow is called safely from the main thread via after().
"""
import asyncio
import queue
import threading
import tkinter as tk
from tkinter import messagebox
from turtle import title
import cv2
import requests

from webrtc import WebRTCViewer

HTTP_URL = "https://signal.shashankfq.app"
WS_URL = "wss://signal.shashankfq.app"

VIDEO_POLL_MS = 16   # how often the GUI polls for a new frame (~33 fps)


class ViewerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Screen Share — Viewer")
        self.resizable(False, False)
        self.configure(bg="#1e1e2e")

        self._viewer: WebRTCViewer = None
        self._loop: asyncio.AbstractEventLoop = None
        self._thread: threading.Thread = None
        self._session_id: str = ""
        self._polling = False

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        BG, FG = "#1e1e2e", "#cdd6f4"
        ACCENT = "#cba6f7"
        PANEL = "#313244"
        BTN_C = "#a6e3a1"
        BTN_D = "#f38ba8"
        FONT = ("Segoe UI", 10)
        FONT_BIG = ("Segoe UI", 14, "bold")

        tk.Label(self, text="🖥️  Screen Viewer", font=FONT_BIG,
                 bg=BG, fg=ACCENT).pack(pady=(20, 4))
        tk.Label(self, text="Enter a Session ID to watch a remote screen.",
                 font=FONT, bg=BG, fg=FG).pack(pady=(0, 14))

        # ── Input form ──
        form = tk.Frame(self, bg=PANEL, padx=20, pady=14)
        form.pack(fill="x", padx=20, pady=(0, 10))

        tk.Label(form, text="Session ID:", font=FONT, bg=PANEL, fg=FG,
                 width=16, anchor="w").grid(row=0, column=0, sticky="w", pady=5)
        self._id_var = tk.StringVar()
        id_entry = tk.Entry(form, textvariable=self._id_var,
                            font=("Consolas", 12, "bold"), width=12,
                            bg="#45475a", fg="#cba6f7", insertbackground=FG,
                            relief="flat", bd=4)
        id_entry.grid(row=0, column=1, sticky="w", pady=5)
        id_entry.bind("<Return>", lambda _: self._connect())

        tk.Label(form, text="Password (if any):", font=FONT, bg=PANEL, fg=FG,
                 width=16, anchor="w").grid(row=1, column=0, sticky="w", pady=5)
        self._pw_var = tk.StringVar()
        tk.Entry(form, textvariable=self._pw_var, show="●", font=FONT, width=12,
                 bg="#45475a", fg=FG, insertbackground=FG,
                 relief="flat", bd=4).grid(row=1, column=1, sticky="w", pady=5)

        # ── Status ──
        sf = tk.Frame(self, bg=BG)
        sf.pack(pady=(4, 0))
        tk.Label(sf, text="Status: ", font=FONT, bg=BG, fg=FG).pack(side="left")
        self._status_var = tk.StringVar(value="Idle")
        self._status_lbl = tk.Label(sf, textvariable=self._status_var,
                                    font=("Segoe UI", 10, "bold"),
                                    bg=BG, fg="#a6e3a1")
        self._status_lbl.pack(side="left")

        # ── Buttons ──
        bf = tk.Frame(self, bg=BG)
        bf.pack(pady=16)
        self._connect_btn = tk.Button(
            bf, text="▶  Connect", font=("Segoe UI", 11, "bold"),
            bg=BTN_C, fg="#1e1e2e", activebackground="#94d29a",
            relief="flat", bd=0, padx=20, pady=8, cursor="hand2",
            command=self._connect)
        self._connect_btn.grid(row=0, column=0, padx=8)

        self._disc_btn = tk.Button(
            bf, text="⏹  Disconnect", font=("Segoe UI", 11, "bold"),
            bg=BTN_D, fg="#1e1e2e", activebackground="#e37a96",
            relief="flat", bd=0, padx=20, pady=8, cursor="hand2",
            command=self._disconnect, state="disabled")
        self._disc_btn.grid(row=0, column=1, padx=8)

        tk.Label(self,
                 text="Video will open in a separate window. Press 'q' in it to close.",
                 font=("Segoe UI", 8), bg=BG, fg="#6c7086").pack(pady=(0, 14))

        self.geometry("700x660")

    # ── Helpers ──────────────────────────────────────────────

    def _set_status(self, text: str, color: str = "#a6e3a1"):
        self._status_var.set(text)
        self._status_lbl.config(fg=color)

    def _on_webrtc_status(self, state: str):
        mapping = {
            "connected":          ("Connected ✓",         "#a6e3a1"),
            "connecting":         ("Connecting…",         "#f9e2af"),
            "waiting":            ("Waiting for offer…",  "#f9e2af"),
            "disconnected":       ("Disconnected",        "#f38ba8"),
            "failed":             ("Failed ✗",            "#f38ba8"),
            "reconnecting":       ("Reconnecting…",       "#f9e2af"),
            "sender_disconnected":("Sender disconnected", "#f9e2af"),
        }
        label, color = mapping.get(state, (state, "#cdd6f4"))
        self.after(0, lambda: self._set_status(label, color))

    # ── Video polling (runs on main thread via after()) ──────

    def _start_video_poll(self):
        self._polling = True
        self._window_open = False
        self._session_id_for_window = self._session_id
        self._poll_video()

    def _poll_video(self):
        if not self._polling:
            return

        if self._viewer and self._viewer.frame_queue:
            try:
                img = self._viewer.frame_queue.get_nowait()
                title = f"Screen Share — {self._session_id_for_window}"
                if not self._window_open:
                    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
                    cv2.resizeWindow(title, 1440, 810)  # Initial size
                    self._window_open = True
                cv2.imshow(title, img)
                # cv2.namedWindow(title, cv2.WINDOW_NORMAL)
                # cv2.resizeWindow(title, 1600, 900)
                cv2.waitKey(1)
                self._window_open = True
            except queue.Empty:
                pass

        # Keep polling while connected
        self.after(VIDEO_POLL_MS, self._poll_video)

    def _stop_video_poll(self):
        self._polling = False
        cv2.destroyAllWindows()

    # ── Actions ──────────────────────────────────────────────

    def _connect(self):
        session_id = self._id_var.get().strip().upper()
        password = self._pw_var.get().strip()

        if not session_id:
            messagebox.showwarning("Missing ID", "Please enter a Session ID.")
            return

        # Validate with backend
        try:
            params = {"password": password} if password else {}
            resp = requests.get(f"{HTTP_URL}/join-session/{session_id}",
                                params=params, timeout=5)
            if resp.status_code == 401:
                messagebox.showerror("Auth Error", "This session requires a password.")
                return
            if resp.status_code == 403:
                messagebox.showerror("Auth Error", "Incorrect password.")
                return
            if resp.status_code == 404:
                messagebox.showerror("Not Found",
                                     "Session ID not found.\nAsk the sender for the correct ID.")
                return
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Connection Error",
                                 "Could not reach signaling server.\nIs the backend running?")
            return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        self._session_id = session_id
        self._connect_btn.config(state="disabled")
        self._disc_btn.config(state="normal")
        self._set_status("Connecting…", "#f9e2af")

        # Start async viewer in a background thread
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_async, args=(session_id, password), daemon=True)
        self._thread.start()

        # Start polling for video frames on the main thread
        self._start_video_poll()

    def _run_async(self, session_id: str, password: str):
        asyncio.set_event_loop(self._loop)
        self._viewer = WebRTCViewer(WS_URL, session_id, password)
        self._viewer.on_status_change = self._on_webrtc_status
        try:
            self._loop.run_until_complete(self._viewer.connect_signaling())
        except Exception as e:
            print(f"[Viewer GUI] Async error: {e}")

    def _disconnect(self):
        if self._viewer:
            self._viewer.stop()
            self._viewer = None
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        self._stop_video_poll()
        self._connect_btn.config(state="normal")
        self._disc_btn.config(state="disabled")
        self._set_status("Idle")

    def _on_close(self):
        self._disconnect()
        self.destroy()


if __name__ == "__main__":
    app = ViewerApp()
    app.mainloop()