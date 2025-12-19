"""
Input control module for mouse and keyboard.

Provides safe and reliable input automation using PyAutoGUI and pynput.
"""

import time
from enum import Enum
from typing import Optional, Union
import pyautogui

from .config import get_config, InputConfig
from .models import BoundingBox, ActionType, ActionResult


# Configure PyAutoGUI
pyautogui.PAUSE = 0.0  # We handle pauses ourselves
pyautogui.FAILSAFE = True  # Enable fail-safe by default


class MouseButton(str, Enum):
    """Mouse button identifiers."""
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class InputController:
    """
    Controls mouse and keyboard input.
    
    Provides high-level methods for common input operations
    with configurable delays and safety features.
    """
    
    def __init__(self, config: Optional[InputConfig] = None):
        self.config = config or get_config().input
        pyautogui.FAILSAFE = self.config.failsafe
    
    def _pause(self) -> None:
        """Pause after an action."""
        if self.config.pause_after_action > 0:
            time.sleep(self.config.pause_after_action)
    
    # ==================== Mouse Operations ====================
    
    def move(
        self,
        x: int,
        y: int,
        duration: Optional[float] = None
    ) -> ActionResult:
        """
        Move mouse to a position.
        
        Args:
            x: X coordinate
            y: Y coordinate
            duration: Movement duration (default from config)
        """
        start_time = time.time()
        
        try:
            dur = duration if duration is not None else self.config.move_duration
            pyautogui.moveTo(x, y, duration=dur)
            self._pause()
            
            return ActionResult(
                success=True,
                action_type=ActionType.MOVE,
                position=(x, y),
                duration_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.MOVE,
                position=(x, y),
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )
    
    def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: MouseButton = MouseButton.LEFT,
        clicks: int = 1
    ) -> ActionResult:
        """
        Click at a position.
        
        Args:
            x: X coordinate (None = current position)
            y: Y coordinate (None = current position)
            button: Mouse button to click
            clicks: Number of clicks
        """
        start_time = time.time()
        
        try:
            if x is not None and y is not None:
                pyautogui.moveTo(x, y, duration=self.config.move_duration)
            
            time.sleep(self.config.click_delay)
            pyautogui.click(button=button.value, clicks=clicks)
            self._pause()
            
            pos = (x, y) if x is not None and y is not None else pyautogui.position()
            
            action_type = ActionType.DOUBLE_CLICK if clicks == 2 else ActionType.CLICK
            if button == MouseButton.RIGHT:
                action_type = ActionType.RIGHT_CLICK
            
            return ActionResult(
                success=True,
                action_type=action_type,
                position=pos,
                duration_ms=(time.time() - start_time) * 1000,
                metadata={"button": button.value, "clicks": clicks},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.CLICK,
                position=(x, y) if x and y else None,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )
    
    def double_click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None
    ) -> ActionResult:
        """Double-click at a position."""
        return self.click(x, y, clicks=2)
    
    def right_click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None
    ) -> ActionResult:
        """Right-click at a position."""
        return self.click(x, y, button=MouseButton.RIGHT)
    
    def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: Optional[float] = None,
        button: MouseButton = MouseButton.LEFT
    ) -> ActionResult:
        """
        Drag from one position to another.
        
        Args:
            start_x, start_y: Starting position
            end_x, end_y: Ending position
            duration: Drag duration
            button: Mouse button to hold
        """
        start_time = time.time()
        
        try:
            dur = duration if duration is not None else self.config.move_duration * 2
            
            pyautogui.moveTo(start_x, start_y, duration=self.config.move_duration)
            time.sleep(self.config.click_delay)
            pyautogui.drag(
                end_x - start_x,
                end_y - start_y,
                duration=dur,
                button=button.value
            )
            self._pause()
            
            return ActionResult(
                success=True,
                action_type=ActionType.DRAG,
                position=(end_x, end_y),
                duration_ms=(time.time() - start_time) * 1000,
                metadata={
                    "start": [start_x, start_y],
                    "end": [end_x, end_y],
                    "button": button.value,
                },
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.DRAG,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )
    
    def scroll(
        self,
        clicks: int,
        x: Optional[int] = None,
        y: Optional[int] = None
    ) -> ActionResult:
        """
        Scroll the mouse wheel.
        
        Args:
            clicks: Number of scroll clicks (positive = up, negative = down)
            x, y: Position to scroll at (None = current position)
        """
        start_time = time.time()
        
        try:
            if x is not None and y is not None:
                pyautogui.moveTo(x, y, duration=self.config.move_duration)
            
            pyautogui.scroll(clicks)
            self._pause()
            
            pos = (x, y) if x is not None and y is not None else pyautogui.position()
            
            return ActionResult(
                success=True,
                action_type=ActionType.SCROLL,
                position=pos,
                duration_ms=(time.time() - start_time) * 1000,
                metadata={"clicks": clicks},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.SCROLL,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )
    
    def hover(
        self,
        x: int,
        y: int,
        duration: float = 0.5
    ) -> ActionResult:
        """
        Move to a position and hover.
        
        Args:
            x, y: Position to hover at
            duration: How long to hover
        """
        start_time = time.time()
        
        try:
            pyautogui.moveTo(x, y, duration=self.config.move_duration)
            time.sleep(duration)
            
            return ActionResult(
                success=True,
                action_type=ActionType.HOVER,
                position=(x, y),
                duration_ms=(time.time() - start_time) * 1000,
                metadata={"hover_duration": duration},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.HOVER,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )
    
    def get_position(self) -> tuple[int, int]:
        """Get current mouse position."""
        return pyautogui.position()
    
    # ==================== Keyboard Operations ====================
    
    def type_text(
        self,
        text: str,
        interval: Optional[float] = None
    ) -> ActionResult:
        """
        Type text character by character.
        
        Args:
            text: Text to type
            interval: Delay between characters (default from config)
        """
        start_time = time.time()
        
        try:
            delay = interval if interval is not None else self.config.typing_delay
            pyautogui.write(text, interval=delay)
            self._pause()
            
            return ActionResult(
                success=True,
                action_type=ActionType.TYPE,
                duration_ms=(time.time() - start_time) * 1000,
                metadata={"text": text, "length": len(text)},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.TYPE,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )
    
    def type_text_unicode(self, text: str) -> ActionResult:
        """
        Type text supporting Unicode characters.
        
        Uses clipboard method for reliable Unicode input.
        """
        start_time = time.time()
        
        try:
            import pyperclip
            
            # Save current clipboard
            try:
                old_clipboard = pyperclip.paste()
            except:
                old_clipboard = ""
            
            # Copy text to clipboard and paste
            pyperclip.copy(text)
            # Longer delay to ensure clipboard is fully updated before pasting
            time.sleep(0.15)
            pyautogui.hotkey('ctrl', 'v')
            
            # Wait for paste to complete before restoring clipboard
            time.sleep(0.15)
            
            # Restore clipboard
            try:
                pyperclip.copy(old_clipboard)
            except:
                pass
            
            self._pause()
            
            return ActionResult(
                success=True,
                action_type=ActionType.TYPE,
                duration_ms=(time.time() - start_time) * 1000,
                metadata={"text": text, "method": "clipboard"},
            )
        except ImportError:
            # Fall back to regular typing
            return self.type_text(text)
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.TYPE,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )
    
    def press_key(self, key: str) -> ActionResult:
        """
        Press a single key.
        
        Args:
            key: Key name (e.g., 'enter', 'tab', 'escape', 'a', 'f1')
        """
        start_time = time.time()
        
        try:
            pyautogui.press(key)
            self._pause()
            
            return ActionResult(
                success=True,
                action_type=ActionType.PRESS_KEY,
                duration_ms=(time.time() - start_time) * 1000,
                metadata={"key": key},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.PRESS_KEY,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )
    
    def hotkey(self, *keys: str) -> ActionResult:
        """
        Press a key combination.
        
        Args:
            keys: Key names (e.g., 'ctrl', 'c' for Ctrl+C)
        """
        start_time = time.time()
        
        try:
            pyautogui.hotkey(*keys)
            self._pause()
            
            return ActionResult(
                success=True,
                action_type=ActionType.HOTKEY,
                duration_ms=(time.time() - start_time) * 1000,
                metadata={"keys": list(keys)},
            )
        except Exception as e:
            return ActionResult(
                success=False,
                action_type=ActionType.HOTKEY,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )
    
    def key_down(self, key: str) -> None:
        """Hold a key down."""
        pyautogui.keyDown(key)
    
    def key_up(self, key: str) -> None:
        """Release a key."""
        pyautogui.keyUp(key)
    
    # ==================== Utility Methods ====================
    
    def click_element(
        self,
        bounds: BoundingBox,
        button: MouseButton = MouseButton.LEFT,
        offset: tuple[int, int] = (0, 0)
    ) -> ActionResult:
        """
        Click on the center of an element.
        
        Args:
            bounds: Element bounding box
            button: Mouse button
            offset: Offset from center (x, y)
        """
        center_x, center_y = bounds.center
        return self.click(
            center_x + offset[0],
            center_y + offset[1],
            button=button
        )
    
    def type_in_element(
        self,
        bounds: BoundingBox,
        text: str,
        clear_first: bool = False
    ) -> ActionResult:
        """
        Click on an element and type text.
        
        Args:
            bounds: Element bounding box
            text: Text to type
            clear_first: Clear existing text first (Ctrl+A)
        """
        # Click to focus
        click_result = self.click_element(bounds)
        if not click_result.success:
            return click_result
        
        time.sleep(0.1)
        
        # Clear if requested
        if clear_first:
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.05)
        
        # Type text
        return self.type_text_unicode(text)


# Global input controller instance
_controller: Optional[InputController] = None


def get_input_controller() -> InputController:
    """Get the global input controller instance."""
    global _controller
    if _controller is None:
        _controller = InputController()
    return _controller
