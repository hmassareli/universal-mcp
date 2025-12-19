"""
Windows-specific utilities for window management.

Provides functions to enumerate windows, get window information,
and interact with the Windows UI.
"""

from dataclasses import dataclass
from typing import Optional, Callable
import ctypes
from ctypes import wintypes

from .models import BoundingBox, WindowInfo


# Windows API constants
GW_OWNER = 4
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
GA_ROOTOWNER = 3

SW_HIDE = 0
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9


# Load Windows DLLs
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi


# Type definitions
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def get_window_title(hwnd: int) -> str:
    """Get the title of a window."""
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def get_window_class(hwnd: int) -> str:
    """Get the class name of a window."""
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def get_window_rect(hwnd: int) -> Optional[BoundingBox]:
    """Get the bounding rectangle of a window."""
    rect = wintypes.RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return BoundingBox(
            x=rect.left,
            y=rect.top,
            width=rect.right - rect.left,
            height=rect.bottom - rect.top,
        )
    return None


def get_client_rect(hwnd: int) -> Optional[BoundingBox]:
    """Get the client area rectangle of a window."""
    rect = wintypes.RECT()
    if user32.GetClientRect(hwnd, ctypes.byref(rect)):
        # Convert client coordinates to screen coordinates
        point = wintypes.POINT(0, 0)
        user32.ClientToScreen(hwnd, ctypes.byref(point))
        return BoundingBox(
            x=point.x,
            y=point.y,
            width=rect.right,
            height=rect.bottom,
        )
    return None


def get_process_name(hwnd: int) -> str:
    """Get the process name of a window."""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    
    # Open process
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    
    handle = kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid.value
    )
    
    if not handle:
        return ""
    
    try:
        buffer = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            # Extract just the filename
            path = buffer.value
            return path.split("\\")[-1] if "\\" in path else path
        return ""
    finally:
        kernel32.CloseHandle(handle)


def get_process_id(hwnd: int) -> int:
    """Get the process ID of a window."""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def is_window_visible(hwnd: int) -> bool:
    """Check if a window is visible."""
    return bool(user32.IsWindowVisible(hwnd))


def is_window_minimized(hwnd: int) -> bool:
    """Check if a window is minimized."""
    return bool(user32.IsIconic(hwnd))


def is_window_maximized(hwnd: int) -> bool:
    """Check if a window is maximized."""
    return bool(user32.IsZoomed(hwnd))


def get_foreground_window() -> int:
    """Get the handle of the foreground window."""
    return user32.GetForegroundWindow()


def set_foreground_window(hwnd: int) -> bool:
    """Bring a window to the foreground."""
    return bool(user32.SetForegroundWindow(hwnd))


def is_taskbar_window(hwnd: int) -> bool:
    """Check if a window should appear in the taskbar (main window)."""
    # Must be visible
    if not is_window_visible(hwnd):
        return False
    
    # Check extended styles
    ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    
    # Tool windows don't appear in taskbar
    if ex_style & WS_EX_TOOLWINDOW:
        return False
    
    # Check if window has an owner
    owner = user32.GetWindow(hwnd, GW_OWNER)
    if owner and not (ex_style & WS_EX_APPWINDOW):
        return False
    
    return True


def get_window_info(hwnd: int) -> WindowInfo:
    """Get complete information about a window."""
    bounds = get_window_rect(hwnd) or BoundingBox(0, 0, 0, 0)
    foreground = get_foreground_window()
    
    return WindowInfo(
        handle=hwnd,
        title=get_window_title(hwnd),
        bounds=bounds,
        class_name=get_window_class(hwnd),
        process_name=get_process_name(hwnd),
        process_id=get_process_id(hwnd),
        is_active=(hwnd == foreground),
        is_visible=is_window_visible(hwnd),
        is_minimized=is_window_minimized(hwnd),
        is_maximized=is_window_maximized(hwnd),
    )


def enumerate_windows(
    callback: Callable[[int], bool],
    include_invisible: bool = False
) -> None:
    """
    Enumerate all top-level windows.
    
    Args:
        callback: Function called for each window. Return False to stop enumeration.
        include_invisible: Include invisible windows
    """
    @WNDENUMPROC
    def enum_callback(hwnd: int, lparam: int) -> bool:
        if not include_invisible and not is_window_visible(hwnd):
            return True  # Continue enumeration
        return callback(hwnd)
    
    user32.EnumWindows(enum_callback, 0)


def get_all_windows(taskbar_only: bool = True) -> list[WindowInfo]:
    """Get information about all windows."""
    windows: list[WindowInfo] = []
    
    def callback(hwnd: int) -> bool:
        if taskbar_only and not is_taskbar_window(hwnd):
            return True
        
        info = get_window_info(hwnd)
        if info.title:  # Only include windows with titles
            windows.append(info)
        return True
    
    enumerate_windows(callback)
    return windows


def find_window_by_title(
    title: str,
    exact: bool = False,
    case_sensitive: bool = False
) -> Optional[WindowInfo]:
    """Find a window by its title."""
    windows = get_all_windows(taskbar_only=False)
    
    search_title = title if case_sensitive else title.lower()
    
    for window in windows:
        window_title = window.title if case_sensitive else window.title.lower()
        
        if exact:
            if window_title == search_title:
                return window
        else:
            if search_title in window_title:
                return window
    
    return None


def find_window_by_class(class_name: str) -> Optional[WindowInfo]:
    """Find a window by its class name."""
    hwnd = user32.FindWindowW(class_name, None)
    if hwnd:
        return get_window_info(hwnd)
    return None


def minimize_window(hwnd: int) -> bool:
    """Minimize a window."""
    return bool(user32.ShowWindow(hwnd, SW_MINIMIZE))


def maximize_window(hwnd: int) -> bool:
    """Maximize a window."""
    return bool(user32.ShowWindow(hwnd, SW_MAXIMIZE))


def restore_window(hwnd: int) -> bool:
    """Restore a minimized/maximized window."""
    return bool(user32.ShowWindow(hwnd, SW_RESTORE))


def close_window(hwnd: int) -> bool:
    """Send close message to a window."""
    WM_CLOSE = 0x0010
    return bool(user32.PostMessageW(hwnd, WM_CLOSE, 0, 0))


def move_window(hwnd: int, x: int, y: int, width: int, height: int) -> bool:
    """Move and resize a window."""
    return bool(user32.MoveWindow(hwnd, x, y, width, height, True))


def get_screen_size() -> tuple[int, int]:
    """Get the primary screen size."""
    SM_CXSCREEN = 0
    SM_CYSCREEN = 1
    width = user32.GetSystemMetrics(SM_CXSCREEN)
    height = user32.GetSystemMetrics(SM_CYSCREEN)
    return (width, height)


def get_cursor_position() -> tuple[int, int]:
    """Get the current cursor position."""
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return (point.x, point.y)


def get_window_at_point(x: int, y: int) -> Optional[WindowInfo]:
    """Get the window at a specific screen position."""
    hwnd = user32.WindowFromPoint(wintypes.POINT(x, y))
    if hwnd:
        # Get the root owner (main window)
        root = user32.GetAncestor(hwnd, GA_ROOTOWNER)
        if root:
            hwnd = root
        return get_window_info(hwnd)
    return None


def get_active_window_info() -> Optional[dict]:
    """
    Get information about the currently active (foreground) window.
    
    Returns a dict with:
    - handle: Window handle
    - title: Window title
    - class_name: Window class name
    - process_name: Process name (e.g., "chrome.exe")
    - bounds: Window bounds
    
    Returns None if no active window.
    """
    hwnd = get_foreground_window()
    if not hwnd:
        return None
    
    bounds = get_window_rect(hwnd)
    
    return {
        "handle": hwnd,
        "title": get_window_title(hwnd),
        "class_name": get_window_class(hwnd),
        "process_name": get_process_name(hwnd),
        "process_id": get_process_id(hwnd),
        "bounds": bounds,
    }
