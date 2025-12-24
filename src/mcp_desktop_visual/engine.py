"""
Desktop Visual Engine - Core orchestration module.

Coordinates screen capture, element detection, and state management
to provide a unified visual understanding of the desktop.

Uses a provider-based architecture:
- UIA (UI Automation) for native Windows apps
- OCR as fallback for anything else
"""

import asyncio
import time
from datetime import datetime
from typing import Optional
import numpy as np

from .config import Config, get_config
from .models import (
    UIElement, WindowInfo, ScreenState, VisualDiff,
    BoundingBox, ElementType, ActionType, ActionResult
)
from .capture import ScreenCapture, CaptureResult
from .ocr import OCREngine, get_ocr_engine
from .detector import ElementDetector, get_element_detector
from .cache import VisualStateCache, get_visual_cache
from .input import InputController, MouseButton, get_input_controller
from .windows import get_all_windows, get_screen_size, get_active_window_info


class DesktopVisualEngine:
    """
    Main engine for desktop visual understanding.
    
    Provides a high-level API for:
    - Capturing and understanding the screen
    - Detecting UI elements
    - Performing input actions
    - Querying the visual state
    
    Uses intelligent provider selection:
    - UI Automation for native Windows apps
    - OCR as fallback
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        
        # Initialize components
        self._capture = ScreenCapture(self.config.capture)
        self._ocr = OCREngine(self.config.ocr)
        self._detector = ElementDetector(self.config.element_detection, self._ocr)
        self._cache = VisualStateCache(self.config.cache)
        self._input = InputController(self.config.input)
        
        # Provider registry (lazy initialized)
        self._provider_registry = None
        self._last_provider_name = "unknown"
        
        # State
        self._is_running = False
        self._last_capture_time = 0.0
        self._capture_count = 0
    
    def _get_provider_registry(self):
        """Lazy-load the provider registry."""
        if self._provider_registry is None:
            try:
                from .providers import ProviderRegistry
                self._provider_registry = ProviderRegistry()
                self._provider_registry.initialize()
            except Exception as e:
                # If providers fail to load, we'll fall back to OCR-only
                self._provider_registry = None
        return self._provider_registry
    
    def start(self) -> None:
        """Start the engine."""
        self._capture.start()
        self._is_running = True
        
        # Initial full capture
        self.capture_and_analyze()
    
    def stop(self) -> None:
        """Stop the engine."""
        self._capture.stop()
        self._is_running = False
    
    def __enter__(self) -> "DesktopVisualEngine":
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
    
    # ==================== Capture & Analysis ====================
    
    def capture_and_analyze(self, force_full: bool = False) -> VisualDiff:
        """
        Capture the screen and analyze for elements.
        
        Uses incremental capture when possible to only process
        regions that have changed.
        
        Args:
            force_full: Force a full screen analysis
        
        Returns:
            VisualDiff showing what changed
        """
        start_time = time.time()
        
        # Capture screen
        if force_full:
            self._capture.reset()
        
        capture_result = self._capture.capture_incremental()
        self._last_capture_time = time.time()
        self._capture_count += 1
        
        # Get window information
        windows = get_all_windows()
        screen_size = get_screen_size()
        
        if capture_result.is_full_capture:
            # Full analysis
            elements = self._analyze_full_screen(capture_result)
        else:
            if not capture_result.has_changes:
                # No changes, just update windows
                self._cache.update_windows(windows)
                return VisualDiff(
                    timestamp=datetime.now(),
                    changed_regions=[],
                )
            
            # Incremental analysis
            elements = self._analyze_regions(capture_result)
        
        # Create screen state
        state = ScreenState(
            timestamp=datetime.now(),
            elements=elements,
            windows=windows,
            active_window=next(
                (w.title for w in windows if w.is_active), None
            ),
            screen_size=screen_size,
        )
        
        # Update cache and get diff
        diff = self._cache.update_full(state)
        
        return diff
    
    def _analyze_full_screen(self, capture: CaptureResult) -> list[UIElement]:
        """
        Analyze the full screen for elements.
        
        Uses intelligent provider selection:
        1. Try UI Automation for native Windows apps
        2. Fall back to OCR for everything else
        """
        # Try to use intelligent providers first
        elements = self._try_smart_providers()
        
        if elements is not None:
            return elements
        
        # Fall back to OCR-based detection
        self._last_provider_name = "OCR"
        detection_result = self._detector.detect(capture.frame.image)
        return detection_result.elements
    
    def _try_smart_providers(self) -> Optional[list[UIElement]]:
        """
        Try to use UIA providers for better accuracy.
        
        Returns:
            List of elements if a smart provider worked, None otherwise
        """
        import logging
        logger = logging.getLogger(__name__)
        
        registry = self._get_provider_registry()
        if registry is None:
            return None
        
        # Get info about active window
        try:
            active_window = get_active_window_info()
            if active_window is None:
                return None
            
            process_name = active_window.get("process_name", "")
            window_title = active_window.get("title", "")
            window_class = active_window.get("class_name", "")
            window_handle = active_window.get("handle")
            
            logger.debug(f"Smart providers: process={process_name}, title={window_title[:30]}")
            
            # Find best provider for the ACTIVE window only
            # We should only use UIA when the active window matches
            # This ensures we capture what the user is actually looking at
            provider = registry.get_provider(process_name, window_title, window_class)
            
            # NOTE: We intentionally do NOT target a specific app when another window is active.
            # The MCP should capture information from whatever window is active.
            
            if provider is None:
                logger.debug(f"Smart providers: No provider matched for active window '{process_name}' - will use OCR")
                return None
            
            logger.debug(f"Smart providers: Using {provider.name}")
            
            # Try to detect elements
            result = provider.detect(window_handle=window_handle)
            
            logger.debug(f"Smart providers: success={result.success}, elements={len(result.elements)}, error={result.error}")
            
            # Use the provider result if successful (even if empty - we trust CDP/UIA over OCR)
            if result.success:
                self._last_provider_name = provider.name
                return result.elements if result.elements else []
            
        except Exception as e:
            # If anything fails, fall back to OCR
            logger.warning(f"Smart providers error: {e}")
        
        return None
    
    def _analyze_regions(self, capture: CaptureResult) -> list[UIElement]:
        """Analyze only the changed regions."""
        all_elements: list[UIElement] = []
        
        for region in capture.dirty_regions:
            # Extract region image
            region_image = capture.get_region_image(region)
            
            # Detect elements in region
            detection_result = self._detector.detect(
                region_image,
                region_offset=(region.bounds.x, region.bounds.y)
            )
            
            all_elements.extend(detection_result.elements)
        
        # Merge with existing elements outside changed regions
        for elem in self._cache.current_state.elements:
            in_changed_region = any(
                region.bounds.intersects(elem.bounds)
                for region in capture.dirty_regions
            )
            if not in_changed_region:
                all_elements.append(elem)
        
        return all_elements
    
    def capture_region(self, bounds: BoundingBox) -> list[UIElement]:
        """Capture and analyze a specific region."""
        frame = self._capture.capture_region(bounds)
        detection_result = self._detector.detect(
            frame.image,
            region_offset=(bounds.x, bounds.y)
        )
        return detection_result.elements
    
    # ==================== Query Methods ====================
    
    def get_state(self) -> ScreenState:
        """Get the current screen state."""
        return self._cache.current_state
    
    def get_state_summary(self) -> dict:
        """Get a summary of the current state."""
        return self._cache.get_summary()
    
    def get_diff(self) -> VisualDiff:
        """
        Get the latest changes by capturing and analyzing.
        
        This is a convenience method that captures and returns
        only the diff (changes) from the previous state.
        """
        return self.capture_and_analyze()
    
    def find_element_by_id(self, element_id: str) -> Optional[UIElement]:
        """Find an element by its ID."""
        return self._cache.get_element_by_id(element_id)
    
    def find_element_by_label(
        self,
        label: str,
        fuzzy: bool = True
    ) -> Optional[UIElement]:
        """Find an element by its label."""
        return self._cache.get_element_by_label(label, fuzzy=fuzzy)
    
    def find_element_at(self, x: int, y: int) -> Optional[UIElement]:
        """Find the element at a specific position."""
        return self._cache.get_element_at(x, y)
    
    def query_elements(
        self,
        label: Optional[str] = None,
        element_type: Optional[str] = None,
        window_title: Optional[str] = None,
        limit: int = 50
    ) -> list[UIElement]:
        """
        Query elements with filters.
        
        Args:
            label: Filter by label (partial match)
            element_type: Filter by element type name
            window_title: Filter by window title
            limit: Maximum results
        """
        elem_type = None
        if element_type:
            try:
                elem_type = ElementType(element_type)
            except ValueError:
                pass
        
        return self._cache.query_elements(
            label=label,
            element_type=elem_type,
            window_title=window_title,
            limit=limit,
        )
    
    def get_all_buttons(self) -> list[UIElement]:
        """Get all button elements."""
        return self._cache.get_all_buttons()
    
    def get_all_inputs(self) -> list[UIElement]:
        """Get all input elements."""
        return self._cache.get_all_inputs()
    
    def get_all_text(self) -> list[UIElement]:
        """Get all text elements."""
        return self._cache.get_all_text()
    
    def get_all_windows(self) -> list[WindowInfo]:
        """Get all windows."""
        return self._cache.get_all_windows()
    
    def get_active_window(self) -> Optional[WindowInfo]:
        """Get the active window."""
        return self._cache.get_active_window()
    
    # ==================== Action Methods ====================
    
    def click(
        self,
        target: str | tuple[int, int],
        button: str = "left"
    ) -> ActionResult:
        """
        Click on a target.
        
        Args:
            target: Element ID, label, or (x, y) coordinates
            button: Mouse button ("left", "right", "middle")
        """
        position = self._resolve_target(target)
        if position is None:
            return ActionResult(
                success=False,
                action_type=ActionType.CLICK,
                error=f"Target not found: {target}",
            )
        
        mouse_button = MouseButton(button)
        return self._input.click(position[0], position[1], button=mouse_button)
    
    def double_click(self, target: str | tuple[int, int]) -> ActionResult:
        """Double-click on a target."""
        position = self._resolve_target(target)
        if position is None:
            return ActionResult(
                success=False,
                action_type=ActionType.DOUBLE_CLICK,
                error=f"Target not found: {target}",
            )
        
        return self._input.double_click(position[0], position[1])
    
    def right_click(self, target: str | tuple[int, int]) -> ActionResult:
        """Right-click on a target."""
        position = self._resolve_target(target)
        if position is None:
            return ActionResult(
                success=False,
                action_type=ActionType.RIGHT_CLICK,
                error=f"Target not found: {target}",
            )
        
        return self._input.right_click(position[0], position[1])
    
    def type_text(self, text: str) -> ActionResult:
        """Type text at current position."""
        return self._input.type_text_unicode(text)
    
    def type_in(
        self,
        target: str | tuple[int, int],
        text: str,
        clear_first: bool = False
    ) -> ActionResult:
        """
        Click on a target and type text.
        
        Args:
            target: Element ID, label, or (x, y) coordinates
            text: Text to type
            clear_first: Clear existing text first
        """
        position = self._resolve_target(target)
        if position is None:
            return ActionResult(
                success=False,
                action_type=ActionType.TYPE,
                error=f"Target not found: {target}",
            )
        
        # Click to focus
        click_result = self._input.click(position[0], position[1])
        if not click_result.success:
            return click_result
        
        time.sleep(0.1)
        
        if clear_first:
            self._input.hotkey("ctrl", "a")
            time.sleep(0.05)
        
        return self._input.type_text_unicode(text)
    
    def press_key(self, key: str) -> ActionResult:
        """Press a key."""
        return self._input.press_key(key)
    
    def hotkey(self, *keys: str) -> ActionResult:
        """Press a key combination."""
        return self._input.hotkey(*keys)
    
    def scroll(
        self,
        clicks: int,
        target: Optional[str | tuple[int, int]] = None
    ) -> ActionResult:
        """
        Scroll the mouse wheel.
        
        Args:
            clicks: Number of scroll clicks (positive = up, negative = down)
            target: Optional target to scroll at
        """
        x, y = None, None
        if target:
            position = self._resolve_target(target)
            if position:
                x, y = position
        
        return self._input.scroll(clicks, x, y)
    
    def drag(
        self,
        start: str | tuple[int, int],
        end: str | tuple[int, int]
    ) -> ActionResult:
        """
        Drag from one position to another.
        
        Args:
            start: Starting element/label/position
            end: Ending element/label/position
        """
        start_pos = self._resolve_target(start)
        end_pos = self._resolve_target(end)
        
        if start_pos is None:
            return ActionResult(
                success=False,
                action_type=ActionType.DRAG,
                error=f"Start target not found: {start}",
            )
        
        if end_pos is None:
            return ActionResult(
                success=False,
                action_type=ActionType.DRAG,
                error=f"End target not found: {end}",
            )
        
        return self._input.drag(
            start_pos[0], start_pos[1],
            end_pos[0], end_pos[1]
        )
    
    def move_to(self, target: str | tuple[int, int]) -> ActionResult:
        """Move mouse to a target."""
        position = self._resolve_target(target)
        if position is None:
            return ActionResult(
                success=False,
                action_type=ActionType.MOVE,
                error=f"Target not found: {target}",
            )
        
        return self._input.move(position[0], position[1])
    
    def hover(
        self,
        target: str | tuple[int, int],
        duration: float = 0.5
    ) -> ActionResult:
        """Hover over a target."""
        position = self._resolve_target(target)
        if position is None:
            return ActionResult(
                success=False,
                action_type=ActionType.HOVER,
                error=f"Target not found: {target}",
            )
        
        return self._input.hover(position[0], position[1], duration)
    
    def get_mouse_position(self) -> tuple[int, int]:
        """Get current mouse position."""
        return self._input.get_position()
    
    def _resolve_target(
        self,
        target: str | tuple[int, int]
    ) -> Optional[tuple[int, int]]:
        """Resolve a target to screen coordinates."""
        if isinstance(target, tuple):
            return target
        
        # Try as element ID first
        elem = self._cache.get_element_by_id(target)
        if elem:
            return elem.bounds.center
        
        # Try as label
        elem = self._cache.get_element_by_label(target)
        if elem:
            return elem.bounds.center
        
        return None
    
    # ==================== Utility Methods ====================
    
    def refresh(self) -> VisualDiff:
        """Force a full refresh of the visual state."""
        return self.capture_and_analyze(force_full=True)
    
    def wait_for_element(
        self,
        label: str,
        timeout: float = 10.0,
        interval: float = 0.5
    ) -> Optional[UIElement]:
        """
        Wait for an element to appear.
        
        Args:
            label: Element label to wait for
            timeout: Maximum wait time in seconds
            interval: Check interval in seconds
        
        Returns:
            The element if found, None if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            self.capture_and_analyze()
            elem = self._cache.get_element_by_label(label)
            if elem:
                return elem
            time.sleep(interval)
        
        return None
    
    def wait_for_change(
        self,
        timeout: float = 10.0,
        interval: float = 0.5
    ) -> bool:
        """
        Wait for any visual change.
        
        Args:
            timeout: Maximum wait time in seconds
            interval: Check interval in seconds
        
        Returns:
            True if change detected, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            diff = self.capture_and_analyze()
            if diff.has_changes:
                return True
            time.sleep(interval)
        
        return False
    
    def get_stats(self) -> dict:
        """Get engine statistics."""
        return {
            "is_running": self._is_running,
            "capture_count": self._capture_count,
            "last_capture_time": self._last_capture_time,
            "ocr_available": self._ocr.is_available,
            "cache_stats": self._cache.stats.to_dict(),
        }


# Global engine instance
_engine: Optional[DesktopVisualEngine] = None


def get_engine() -> DesktopVisualEngine:
    """Get or create the global engine instance."""
    global _engine
    if _engine is None:
        _engine = DesktopVisualEngine()
    return _engine


def start_engine() -> DesktopVisualEngine:
    """Start the global engine instance."""
    engine = get_engine()
    if not engine._is_running:
        engine.start()
    return engine
