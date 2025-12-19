"""
Screen capture module with incremental change detection.

This module provides efficient screen capture that only processes
regions that have changed, dramatically reducing processing overhead.
"""

import time
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import cv2
import mss
import mss.tools

from .config import get_config, CaptureConfig
from .models import BoundingBox


@dataclass
class CapturedFrame:
    """A captured frame with metadata."""
    
    image: np.ndarray
    timestamp: float
    monitor_info: dict
    
    @property
    def width(self) -> int:
        return self.image.shape[1]
    
    @property
    def height(self) -> int:
        return self.image.shape[0]
    
    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)


@dataclass
class DirtyRegion:
    """A region of the screen that has changed."""
    
    bounds: BoundingBox
    diff_score: float  # How much the region changed (0-1)
    
    def to_dict(self) -> dict:
        return {
            "bounds": self.bounds.to_dict(),
            "diff_score": self.diff_score,
        }


@dataclass
class CaptureResult:
    """Result of a screen capture with change detection."""
    
    frame: CapturedFrame
    dirty_regions: list[DirtyRegion] = field(default_factory=list)
    is_full_capture: bool = True
    previous_frame_time: Optional[float] = None
    
    @property
    def has_changes(self) -> bool:
        return self.is_full_capture or len(self.dirty_regions) > 0
    
    def get_region_image(self, region: DirtyRegion) -> np.ndarray:
        """Extract image for a specific dirty region."""
        b = region.bounds
        return self.frame.image[b.y:b.y2, b.x:b.x2]
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.frame.timestamp,
            "size": list(self.frame.size),
            "is_full_capture": self.is_full_capture,
            "dirty_regions": [r.to_dict() for r in self.dirty_regions],
            "total_dirty_area": sum(r.bounds.area for r in self.dirty_regions),
        }


class ScreenCapture:
    """
    Screen capture with incremental change detection.
    
    Uses MSS for fast screen capture and OpenCV for efficient
    change detection between frames.
    """
    
    def __init__(self, config: Optional[CaptureConfig] = None):
        self.config = config or get_config().capture
        self._sct: Optional[mss.mss] = None
        self._previous_frame: Optional[np.ndarray] = None
        self._previous_frame_gray: Optional[np.ndarray] = None
        self._previous_time: Optional[float] = None
        self._monitor_info: Optional[dict] = None
    
    def __enter__(self) -> "ScreenCapture":
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
    
    def start(self) -> None:
        """Initialize the screen capture."""
        self._sct = mss.mss()
        self._update_monitor_info()
    
    def stop(self) -> None:
        """Release screen capture resources."""
        if self._sct:
            self._sct.close()
            self._sct = None
        self._previous_frame = None
        self._previous_frame_gray = None
    
    def _update_monitor_info(self) -> None:
        """Update monitor information."""
        if not self._sct:
            return
        
        monitors = self._sct.monitors
        if self.config.monitor is not None and self.config.monitor < len(monitors):
            self._monitor_info = monitors[self.config.monitor]
        else:
            # Use primary monitor (index 1) or full virtual screen (index 0)
            self._monitor_info = monitors[1] if len(monitors) > 1 else monitors[0]
    
    @property
    def monitor(self) -> dict:
        """Get current monitor info."""
        if self._monitor_info is None:
            self._update_monitor_info()
        return self._monitor_info or {"left": 0, "top": 0, "width": 1920, "height": 1080}
    
    def capture_full(self) -> CapturedFrame:
        """Capture the full screen without change detection."""
        if not self._sct:
            self.start()
        
        screenshot = self._sct.grab(self.monitor)
        
        # Convert to numpy array (BGRA format)
        image = np.array(screenshot)
        # Convert BGRA to BGR
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        
        return CapturedFrame(
            image=image,
            timestamp=time.time(),
            monitor_info=self.monitor.copy(),
        )
    
    def capture_region(self, bounds: BoundingBox) -> CapturedFrame:
        """Capture a specific region of the screen."""
        if not self._sct:
            self.start()
        
        region = {
            "left": self.monitor["left"] + bounds.x,
            "top": self.monitor["top"] + bounds.y,
            "width": bounds.width,
            "height": bounds.height,
        }
        
        screenshot = self._sct.grab(region)
        image = np.array(screenshot)
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        
        return CapturedFrame(
            image=image,
            timestamp=time.time(),
            monitor_info=region,
        )
    
    def capture_incremental(self) -> CaptureResult:
        """
        Capture screen and detect changes from previous capture.
        
        Returns a CaptureResult with dirty regions indicating what changed.
        On first capture, returns full frame with is_full_capture=True.
        """
        frame = self.capture_full()
        
        # Convert to grayscale for comparison
        frame_gray = cv2.cvtColor(frame.image, cv2.COLOR_BGR2GRAY)
        
        # If no previous frame, this is a full capture
        if self._previous_frame_gray is None:
            self._previous_frame = frame.image.copy()
            self._previous_frame_gray = frame_gray
            self._previous_time = frame.timestamp
            return CaptureResult(
                frame=frame,
                is_full_capture=True,
            )
        
        # Check if frames have same dimensions
        if frame_gray.shape != self._previous_frame_gray.shape:
            # Resolution changed, treat as full capture
            self._previous_frame = frame.image.copy()
            self._previous_frame_gray = frame_gray
            self._previous_time = frame.timestamp
            return CaptureResult(
                frame=frame,
                is_full_capture=True,
            )
        
        # Detect dirty regions
        dirty_regions = self._detect_changes(frame_gray, self._previous_frame_gray)
        
        result = CaptureResult(
            frame=frame,
            dirty_regions=dirty_regions,
            is_full_capture=False,
            previous_frame_time=self._previous_time,
        )
        
        # Update previous frame
        self._previous_frame = frame.image.copy()
        self._previous_frame_gray = frame_gray
        self._previous_time = frame.timestamp
        
        return result
    
    def _detect_changes(
        self,
        current: np.ndarray,
        previous: np.ndarray
    ) -> list[DirtyRegion]:
        """
        Detect regions that changed between two frames.
        
        Uses image differencing and contour detection to find
        rectangular regions that have changed.
        """
        config = self.config
        
        # Optionally downscale for faster comparison
        if config.diff_scale < 1.0:
            h, w = current.shape[:2]
            new_w = int(w * config.diff_scale)
            new_h = int(h * config.diff_scale)
            current_small = cv2.resize(current, (new_w, new_h))
            previous_small = cv2.resize(previous, (new_w, new_h))
            scale_factor = 1.0 / config.diff_scale
        else:
            current_small = current
            previous_small = previous
            scale_factor = 1.0
        
        # Compute absolute difference
        diff = cv2.absdiff(current_small, previous_small)
        
        # Apply threshold
        _, thresh = cv2.threshold(
            diff, config.diff_threshold, 255, cv2.THRESH_BINARY
        )
        
        # Apply morphological operations to reduce noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        thresh = cv2.dilate(thresh, kernel, iterations=2)
        thresh = cv2.erode(thresh, kernel, iterations=1)
        
        # Find contours
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        dirty_regions: list[DirtyRegion] = []
        
        for contour in contours:
            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            
            # Scale back to original resolution
            x = int(x * scale_factor)
            y = int(y * scale_factor)
            w = int(w * scale_factor)
            h = int(h * scale_factor)
            
            # Filter by minimum area
            area = w * h
            if area < config.min_region_area:
                continue
            
            # Calculate diff score for this region
            region_diff = diff[
                int(y / scale_factor):int((y + h) / scale_factor),
                int(x / scale_factor):int((x + w) / scale_factor)
            ]
            diff_score = np.mean(region_diff) / 255.0
            
            bounds = BoundingBox(x, y, w, h)
            dirty_regions.append(DirtyRegion(bounds=bounds, diff_score=diff_score))
        
        # Merge overlapping regions
        dirty_regions = self._merge_regions(dirty_regions)
        
        # Limit number of regions
        if len(dirty_regions) > config.max_regions:
            # Keep the largest regions
            dirty_regions.sort(key=lambda r: r.bounds.area, reverse=True)
            dirty_regions = dirty_regions[:config.max_regions]
        
        return dirty_regions
    
    def _merge_regions(
        self,
        regions: list[DirtyRegion],
        merge_distance: int = 20
    ) -> list[DirtyRegion]:
        """Merge nearby or overlapping regions."""
        if len(regions) <= 1:
            return regions
        
        merged = []
        used = set()
        
        for i, region1 in enumerate(regions):
            if i in used:
                continue
            
            current = region1.bounds
            current_score = region1.diff_score
            
            # Find all regions that should be merged with this one
            for j, region2 in enumerate(regions):
                if j <= i or j in used:
                    continue
                
                # Expand bounds slightly for distance check
                expanded = BoundingBox(
                    current.x - merge_distance,
                    current.y - merge_distance,
                    current.width + 2 * merge_distance,
                    current.height + 2 * merge_distance,
                )
                
                if expanded.intersects(region2.bounds):
                    current = current.union(region2.bounds)
                    current_score = max(current_score, region2.diff_score)
                    used.add(j)
            
            merged.append(DirtyRegion(bounds=current, diff_score=current_score))
        
        return merged
    
    def reset(self) -> None:
        """Reset the change detection (next capture will be full)."""
        self._previous_frame = None
        self._previous_frame_gray = None
        self._previous_time = None
    
    def get_screen_size(self) -> tuple[int, int]:
        """Get the current screen size."""
        return (self.monitor["width"], self.monitor["height"])


# Convenience function for one-shot capture
def capture_screen() -> np.ndarray:
    """Capture the full screen and return as numpy array."""
    with ScreenCapture() as cap:
        return cap.capture_full().image


def capture_region(bounds: BoundingBox) -> np.ndarray:
    """Capture a region of the screen and return as numpy array."""
    with ScreenCapture() as cap:
        return cap.capture_region(bounds).image
