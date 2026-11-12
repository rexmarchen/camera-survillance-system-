import cv2
import logging
import threading
import time
import math
import os
import datetime
import numpy as np

logger = logging.getLogger(__name__)

class CameraStreamProcessor:
    def __init__(self, camera_id, camera_info, config):
        self.camera_id = camera_id
        self.camera_info = camera_info
        self.url = str(camera_info.get('camera_url', '')).strip()
        self.running = False
        self.thread = None

        # ── BUG FIX 1: varThreshold was 16 (too sensitive → noise triggers motion).
        # Raised to 25 so minor lighting flickers don't register as movement.
        # detectShadows=True kept — shadows are excluded from foreground mask.
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=25, detectShadows=True
        )

        self.motion_score = 0.0
        self.crowd_density = 0.0
        self.unusual_behavior = 0.0
        self.time_factor = 0.5

        # ── BUG FIX 2: time_factor was always hardcoded to 0.5 (never changes).
        # Now it dynamically adjusts based on hour-of-day risk (night = higher).
        self._refresh_time_factor()

        # Load weights
        weights = config.get('ai_engine', {}).get('priority_weights', {})
        self.w_motion   = weights.get('motion_score',      0.4)
        self.w_crowd    = weights.get('crowd_density',     0.3)
        self.w_behavior = weights.get('unusual_behavior',  0.2)
        self.w_time     = weights.get('time_of_day',       0.1)

        # Motion velocity tracking for behavior detection (FIX 3)
        self._prev_motion_score = 0.0
        self._motion_spike_count = 0

        # Setup Video Writer
        self.video_writer = None
        self.recording_filename = ""
        self.recordings_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', '..', 'recordings')
        )
        os.makedirs(self.recordings_dir, exist_ok=True)

    # ─────────────────────────────────────────────────────────────────────────
    # BUG FIX 2 helper: time-of-day risk factor
    # ─────────────────────────────────────────────────────────────────────────
    def _refresh_time_factor(self):
        """
        Dynamically compute a time-of-day risk weight.
        Night hours (22:00 – 06:00) → 0.9 (high risk).
        Peak business hours (09:00 – 18:00) → 0.4 (normal).
        Evening / early morning → 0.65 (moderate).
        """
        hour = datetime.datetime.now().hour
        if 22 <= hour or hour < 6:        # Night
            self.time_factor = 0.9
        elif 9 <= hour < 18:              # Day / business hours
            self.time_factor = 0.4
        else:                             # Dusk / dawn
            self.time_factor = 0.65

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

    def _process_loop(self):
        logger.info(f"Starting frame processor for camera {self.camera_id}: {self.url}")

        url_lower = self.url.lower()
        if (url_lower.startswith('demo://') or url_lower.startswith('test://')
                or 'demo' in url_lower or 'test' in url_lower or 'mock' in url_lower):
            self._process_demo_loop()
        elif url_lower.startswith('http://') or url_lower.startswith('https://'):
            self._process_http_loop()
        else:
            self._process_opencv_loop()

        if self.video_writer is not None:
            self.video_writer.release()
        logger.info(f"Stopped frame processor for camera {self.camera_id}")

    def _process_demo_loop(self):
        """Simulate realistic camera stream motion for demo feeds"""
        tick = 0
        while self.running:
            tick += 1
            motion_val = (math.sin(tick * 0.1) + 1.0) / 2.0
            crowd_val  = (math.cos(tick * 0.05) + 1.0) / 4.0
            self.motion_score    = round(min(1.0, max(0.05, motion_val)), 2)
            self.crowd_density   = round(min(1.0, max(0.05, crowd_val)),  2)
            # ── BUG FIX 3 (demo): behavior was capped at 0.1 and never scaled.
            # Now uses same formula as real frames so demo matches real behavior.
            if self.motion_score > 0.55:
                self.unusual_behavior = round(
                    min(1.0, (self.motion_score - 0.45) * 1.5), 2
                )
            else:
                self.unusual_behavior = 0.0
            self._refresh_time_factor()
            time.sleep(0.5)

    def _simulate_tick(self, tick):
        """Generates realistic telemetry when camera is offline or disconnected"""
        motion_val = (math.sin(tick * 0.15) + 1.0) / 2.0
        crowd_val  = (math.cos(tick * 0.08) + 1.0) / 3.0
        self.motion_score  = round(min(1.0, max(0.05, motion_val * 0.8)), 2)
        self.crowd_density = round(min(1.0, max(0.05, crowd_val)),         2)
        self.unusual_behavior = round(0.15 if self.motion_score > 0.7 else 0.0, 2)

    def _process_opencv_loop(self):
        """Capture from webcam (0, 1) or RTSP/file using OpenCV VideoCapture"""
        is_webcam = self.url.isdigit()
        if is_webcam:
            cap_source = int(self.url)
            cap = cv2.VideoCapture(cap_source, cv2.CAP_DSHOW) if os.name == 'nt' else cv2.VideoCapture(cap_source)
        else:
            cap_source = self.url
            cap = cv2.VideoCapture(cap_source)

        # ── BUG FIX 4: MOG2 needs ~30 frames of background before scores are
        # meaningful. Warmup here so early frames don't spike motion to 1.0.
        self._warmup_bg_subtractor(cap)

        fail_count = 0
        while self.running:
            ret, frame = cap.read()
            if not ret or frame is None:
                fail_count += 1
                if fail_count > 3:
                    self._simulate_tick(fail_count)
                time.sleep(0.5)
                continue

            fail_count = 0
            self._process_frame(frame)
            # Refresh time factor every ~100 frames (~15 s) instead of never
            if hasattr(self, '_frame_count'):
                self._frame_count += 1
            else:
                self._frame_count = 0
            if self._frame_count % 100 == 0:
                self._refresh_time_factor()

            time.sleep(0.15)

        cap.release()

    def _warmup_bg_subtractor(self, cap, warmup_frames=30):
        """
        BUG FIX 4: Feed frames into MOG2 silently so it learns the
        background before we start computing real scores.
        Without this, the very first frame always shows 100% motion.
        """
        logger.info(f"Camera {self.camera_id}: warming up background model ({warmup_frames} frames)...")
        fed = 0
        while fed < warmup_frames:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            frame_small = cv2.resize(frame, (320, 240))
            self.bg_subtractor.apply(frame_small)
            fed += 1
        logger.info(f"Camera {self.camera_id}: background warmup done.")

    def _process_http_loop(self):
        """Process HTTP/HTTPS MJPEG streams"""
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        target_url = self.url
        if (not target_url.endswith('.jpg') and not target_url.endswith('.jpeg')
                and '/video' not in target_url and '/shot.jpg' not in target_url):
            target_url = target_url.rstrip('/') + '/video'

        fail_count = 0
        warmup_frames_fed = 0
        while self.running:
            try:
                res = requests.get(target_url, stream=True, timeout=4, verify=False)
                if res.status_code != 200:
                    fail_count += 1
                    self._simulate_tick(fail_count)
                    time.sleep(2)
                    continue

                bytes_data = bytes()
                for chunk in res.iter_content(chunk_size=4096):
                    if not self.running:
                        break
                    bytes_data += chunk
                    a = bytes_data.find(b'\xff\xd8')
                    b = bytes_data.find(b'\xff\xd9')

                    if a != -1 and b != -1:
                        if a < b:
                            jpg = bytes_data[a:b+2]
                            bytes_data = bytes_data[b+2:]
                            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                            if frame is not None:
                                fail_count = 0
                                # BUG FIX 4 for HTTP streams: warmup
                                if warmup_frames_fed < 30:
                                    frame_small = cv2.resize(frame, (320, 240))
                                    self.bg_subtractor.apply(frame_small)
                                    warmup_frames_fed += 1
                                else:
                                    self._process_frame(frame)
                        else:
                            bytes_data = bytes_data[b+2:]
            except Exception as e:
                fail_count += 1
                self._simulate_tick(fail_count)
                time.sleep(2)

    def _record_frame(self, frame):
        now = datetime.datetime.now()
        timestamp_str = now.strftime('%Y%m%d_%H00')
        cam_name = str(self.camera_info.get('camera_name', f'Cam{self.camera_id}')).replace(' ', '_')
        expected_filename = os.path.join(self.recordings_dir, f"{cam_name}_{timestamp_str}.avi")

        if self.video_writer is None or self.recording_filename != expected_filename:
            if self.video_writer is not None:
                self.video_writer.release()
            height, width = frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.video_writer = cv2.VideoWriter(expected_filename, fourcc, 15.0, (width, height))
            self.recording_filename = expected_filename

        loc = str(self.camera_info.get('location', 'Unknown'))
        display_text = f"{cam_name} | {loc} | {now.strftime('%Y-%m-%d %H:%M:%S')}"
        display_frame = frame.copy()
        cv2.rectangle(display_frame, (0, 0), (display_frame.shape[1], 30), (0, 0, 0), -1)
        cv2.putText(display_frame, display_text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        if self.video_writer is not None:
            self.video_writer.write(display_frame)

    def _process_frame(self, frame):
        frame = cv2.resize(frame, (320, 240))
        fg_mask = self.bg_subtractor.apply(frame)

        # ── BUG FIX 5: Original threshold was 200 which also passes MOG2 shadow
        # pixels (value=127). Using THRESH_BINARY at 254 ensures ONLY confirmed
        # foreground (255) counts — not grey shadow pixels.
        _, fg_mask = cv2.threshold(fg_mask, 254, 255, cv2.THRESH_BINARY)

        # Morphological cleanup: remove salt-and-pepper noise, then dilate to
        # merge adjacent fragments of a single moving person.
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel_open)   # noise removal
        kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(fg_mask, kernel_dilate, iterations=2)

        # ── MOTION ───────────────────────────────────────────────────────────
        non_zero    = cv2.countNonZero(dilated)
        total_pixels = frame.shape[0] * frame.shape[1]
        motion_ratio = non_zero / total_pixels

        current_motion = min(1.0, motion_ratio * 4.0)
        self.motion_score = round(0.7 * self.motion_score + 0.3 * current_motion, 2)
        if self.motion_score < 0.05:
            self.motion_score = 0.0

        # ── CROWD DENSITY ─────────────────────────────────────────────────
        # BUG FIX (crowd): blob area threshold of 200px was at 320×240 scale.
        # At this resolution a standing adult occupies ~1500–3000 px²,
        # so 200 is far too small and counts noise as people.
        # Raised to 800 to match realistic person-sized blobs.
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        people_blobs = [c for c in contours if cv2.contourArea(c) > 800]
        blob_count = len(people_blobs)

        # Each detected blob ≈ 1 person; cap scales at 4 people = density 1.0
        estimated_crowd = min(1.0, blob_count * 0.25)
        self.crowd_density = round(0.6 * self.crowd_density + 0.4 * estimated_crowd, 2)

        # ── UNUSUAL BEHAVIOR ──────────────────────────────────────────────
        # BUG FIX 3: Old logic only looked at absolute motion level, not velocity.
        # A slowly-crowded scene scores high motion but isn't "unusual".
        # Now: behavior is raised by SUDDEN SPIKES in motion (Δmotion > 0.2).
        motion_delta = self.motion_score - self._prev_motion_score
        self._prev_motion_score = self.motion_score

        if motion_delta > 0.20:
            # Rapid surge → possible running, fight, panic, sudden crowd scatter
            self._motion_spike_count = min(self._motion_spike_count + 1, 5)
        else:
            self._motion_spike_count = max(self._motion_spike_count - 1, 0)

        if self.motion_score > 0.55:
            # High sustained motion + velocity spikes = unusual
            spike_boost = self._motion_spike_count * 0.08
            self.unusual_behavior = round(
                min(1.0, (self.motion_score - 0.45) * 1.5 + spike_boost), 2
            )
        else:
            # Gradual decay so the score doesn't snap to 0 abruptly
            self.unusual_behavior = round(max(0.0, self.unusual_behavior - 0.05), 2)

        # ── RECORDING ─────────────────────────────────────────────────────
        if self.motion_score > 0.35 or self.unusual_behavior > 0.0:
            try:
                self._record_frame(frame)
            except Exception as e:
                logger.debug(f"Frame recording error: {e}")

    def get_scores(self):
        overall = (
            self.motion_score    * self.w_motion   +
            self.crowd_density   * self.w_crowd    +
            self.unusual_behavior * self.w_behavior +
            self.time_factor     * self.w_time
        )
        return {
            'motion':   self.motion_score,
            'crowd':    self.crowd_density,
            'behavior': self.unusual_behavior,
            'time':     self.time_factor,
            'overall':  overall
        }
