# client/capture.py
import threading
import mss
import numpy as np
import cv2
import time
import ctypes
ctypes.windll.user32.SetProcessDPIAware()

_thread_local = threading.local()


class ScreenCapture:
    def __init__(self, fps: int = 25, resize_scale: float = 1.0):
        self.fps = fps
        self.resize_scale = resize_scale
        self.frame_duration = 1.0 / fps

    @staticmethod
    def _get_sct() -> mss.mss:
        """Return a thread-local mss instance — mss is NOT thread-safe when shared."""
        if not hasattr(_thread_local, "sct"):
            _thread_local.sct = mss.mss()
        return _thread_local.sct

    def get_frame(self) -> np.ndarray:
        start = time.time()
        sct = self._get_sct()
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        frame = np.array(sct_img)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        if self.resize_scale != 1.0:
            w = int(frame.shape[1] * self.resize_scale)
            h = int(frame.shape[0] * self.resize_scale)
            frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR)
        elapsed = time.time() - start
        sleep_time = self.frame_duration - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)
        return frame