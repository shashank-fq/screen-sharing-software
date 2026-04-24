# client/capture.py
import mss
import numpy as np
import cv2
import time

class ScreenCapture:
    def __init__(self, fps=15, resize_scale=0.5):
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1]  # Primary monitor
        self.fps = fps
        self.resize_scale = resize_scale
        self.frame_duration = 1.0 / self.fps

    def get_frame(self):
        """Step 3: Capture and process frames."""
        start_time = time.time()

        # Capture
        sct_img = self.sct.grab(self.monitor)
        frame = np.array(sct_img)
        
        # Convert BGRA to BGR
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        # Resize for performance (Step 10 Optimization)
        if self.resize_scale != 1.0:
            width = int(frame.shape[1] * self.resize_scale)
            height = int(frame.shape[0] * self.resize_scale)
            frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

        # FPS Control
        elapsed = time.time() - start_time
        sleep_time = self.frame_duration - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

        return frame