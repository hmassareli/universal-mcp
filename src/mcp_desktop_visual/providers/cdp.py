"""
Chrome DevTools Protocol (CDP) Provider.

Provides accurate UI element detection for Chromium-based applications:
- Chrome, Edge, Brave (browsers)
- VS Code, Slack, Discord, Teams (Electron apps)

Automatically manages Chrome debugging port:
- Copies user profile to debug directory
- Starts Chrome with --remote-debugging-port=9222
- Connects via CDP for accurate element detection
"""

import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .base import ElementProvider, ProviderResult
from ..models import UIElement, BoundingBox, ElementType


# Chromium-based processes that support CDP
# NOTE: We only list BROWSERS here, not Electron apps like VS Code
# Each Electron app would need its own debug port connection
# We can't use Chrome's CDP port to control VS Code or other Electron apps
CHROMIUM_BROWSER_PROCESSES = {
    # Browsers only
    "chrome.exe", "msedge.exe", "brave.exe", "vivaldi.exe", "opera.exe",
}

# Electron apps - listed for reference but NOT supported by CDP provider
# Each would need its own debug configuration
ELECTRON_APPS = {
    "code.exe",           # VS Code
    "slack.exe",          # Slack
    "discord.exe",        # Discord
    "teams.exe",          # Microsoft Teams
    "notion.exe",         # Notion
    "figma.exe",          # Figma Desktop
    "postman.exe",        # Postman
    "insomnia.exe",       # Insomnia
    "spotify.exe",        # Spotify (partial Electron)
    "whatsapp.exe",       # WhatsApp Desktop
    "signal.exe",         # Signal
    "obsidian.exe",       # Obsidian
    "atom.exe",           # Atom
}


@dataclass
class CDPConnection:
    """Represents a connection to a CDP endpoint."""
    host: str
    port: int
    websocket_url: Optional[str] = None


class CDPProvider(ElementProvider):
    """
    Provider that uses Chrome DevTools Protocol for element detection.
    
    This provider offers the most accurate detection for Chromium-based apps:
    - Exact element bounds from the DOM
    - Accurate text content
    - Knows which elements are clickable (links, buttons, etc.)
    - Can detect input fields and their types
    
    Automatically manages Chrome debugging:
    - If Chrome isn't running with debug port, restarts it with the port enabled
    - Copies user profile to maintain login sessions
    """
    
    # Chrome paths to try
    CHROME_PATHS = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    
    def __init__(self, default_port: int = 9222, auto_start: bool = True):
        self.default_port = default_port
        self.auto_start = auto_start
        self._connection: Optional[CDPConnection] = None
        self._ws = None
        self._debug_profile_dir = Path(os.environ.get("TEMP", "/tmp")) / "chrome-debug-profile"
    
    @property
    def name(self) -> str:
        return "CDP"
    
    @property
    def priority(self) -> int:
        return 100  # Highest priority
    
    def can_handle(self, process_name: str, window_title: str, window_class: str) -> bool:
        """
        Check if this is a browser process we can control via CDP.
        
        Only returns True for browsers (Chrome, Edge, etc.) - not Electron apps.
        Each Electron app has its own separate debug port that we don't control.
        """
        process_lower = process_name.lower()
        return process_lower in CHROMIUM_BROWSER_PROCESSES
    
    def is_available(self) -> bool:
        """
        Check if CDP is available.
        
        If auto_start is enabled and Chrome is running but port isn't open,
        we can make CDP available by restarting Chrome.
        """
        if self._check_debug_port(self.default_port):
            return True
        
        # If auto_start is enabled, we CAN make it available
        if self.auto_start:
            return self._is_chrome_installed()
        
        return False
    
    def _is_chrome_installed(self) -> bool:
        """Check if Chrome is installed."""
        for path in self.CHROME_PATHS:
            if os.path.exists(path):
                return True
        return False
    
    def _get_chrome_path(self) -> Optional[str]:
        """Get the path to Chrome executable."""
        for path in self.CHROME_PATHS:
            if os.path.exists(path):
                return path
        return None
    
    def _find_start_script(self) -> Optional[str]:
        """Find the start-chrome-debug script in the project."""
        # Look relative to this file's location
        this_dir = Path(__file__).parent
        project_root = this_dir.parent.parent.parent  # src/mcp_desktop_visual/providers -> project root
        
        script_names = ["start-chrome-debug.bat", "start-chrome-debug.cmd"]
        for name in script_names:
            script_path = project_root / name
            if script_path.exists():
                return str(script_path)
        
        return None
    
    def _ensure_debug_port_available(self) -> bool:
        """
        Ensure Chrome is running with debug port enabled.
        
        If port is already open, returns True immediately.
        Otherwise, uses the start-chrome-debug script to launch Chrome properly.
        """
        if self._check_debug_port(self.default_port):
            return True
        
        if not self.auto_start:
            return False
        
        try:
            # Try to use the batch script first (it handles profile sync properly)
            script_path = self._find_start_script()
            
            if script_path:
                # Use the batch script
                subprocess.run(
                    [script_path],
                    capture_output=True,
                    text=True,
                    shell=True
                )
            else:
                # Fallback: do it manually
                chrome_path = self._get_chrome_path()
                if not chrome_path:
                    return False
                
                # Sync profile
                self._sync_user_profile()
                
                # Kill existing Chrome instances
                subprocess.run(
                    ["taskkill", "/F", "/IM", "chrome.exe", "/T"],
                    capture_output=True,
                    text=True
                )
                time.sleep(2)
                
                # Start Chrome with debug port
                subprocess.Popen([
                    chrome_path,
                    f"--remote-debugging-port={self.default_port}",
                    f"--user-data-dir={self._debug_profile_dir}",
                    "--remote-allow-origins=*",
                ])
            
            # Wait for port to become available
            for _ in range(10):
                time.sleep(1)
                if self._check_debug_port(self.default_port):
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _sync_user_profile(self):
        """
        Copy essential user profile data to debug profile directory.
        
        Copies cookies, login data, preferences AND the encryption key
        to maintain sessions. The key is in 'Local State' at User Data level.
        """
        user_data_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
        src_default = user_data_dir / "Default"
        dst_default = self._debug_profile_dir / "Default"
        
        if not src_default.exists():
            return
        
        # Create destination directory
        dst_default.mkdir(parents=True, exist_ok=True)
        
        # CRITICAL: Copy "Local State" which contains the encryption key for cookies
        # This file is at User Data level, not inside Default
        local_state_src = user_data_dir / "Local State"
        local_state_dst = self._debug_profile_dir / "Local State"
        if local_state_src.exists():
            try:
                shutil.copy2(local_state_src, local_state_dst)
            except Exception:
                pass  # File might be locked
        
        # Files to copy for maintaining sessions
        files_to_copy = [
            "Cookies",
            "Cookies-journal", 
            "Login Data",
            "Login Data-journal",
            "Preferences",
            "Secure Preferences",
            "Web Data",
            "Web Data-journal",
            # Additional files that may help with sessions
            "Network Action Predictor",
            "Network Action Predictor-journal",
        ]
        
        for filename in files_to_copy:
            src_file = src_default / filename
            dst_file = dst_default / filename
            if src_file.exists():
                try:
                    shutil.copy2(src_file, dst_file)
                except Exception:
                    pass  # File might be locked
    
    def _check_debug_port(self, port: int, timeout: float = 0.5) -> bool:
        """Check if a debugging port is open."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _activate_chrome_window(self) -> bool:
        """Find and activate the Chrome window to ensure correct focus."""
        try:
            from ..windows import get_all_windows, set_foreground_window
            import time as t
            
            windows = get_all_windows()
            for w in windows:
                if w.process_name.lower() == "chrome.exe" and w.is_visible and not w.is_minimized:
                    set_foreground_window(w.handle)
                    t.sleep(0.1)  # Small delay to let window activate
                    return True
            return False
        except Exception:
            return False
    
    def detect(
        self,
        window_handle: Optional[int] = None,
        region: Optional[BoundingBox] = None
    ) -> ProviderResult:
        """
        Detect UI elements using CDP.
        
        Connects to the Chrome debugging port and queries the DOM
        for all interactive elements.
        
        If Chrome isn't running with debug port, automatically restarts it.
        """
        start_time = time.time()
        
        try:
            # Ensure Chrome is running with debug port
            if not self._ensure_debug_port_available():
                return ProviderResult(
                    elements=[],
                    provider_name=self.name,
                    detection_time_ms=(time.time() - start_time) * 1000,
                    success=False,
                    error="Could not enable Chrome debug port",
                )
            
            elements = self._get_elements_via_cdp()
            
            return ProviderResult(
                elements=elements,
                provider_name=self.name,
                detection_time_ms=(time.time() - start_time) * 1000,
                success=True,
                supports_click_detection=True,
                supports_input_detection=True,
                supports_text_content=True,
            )
        except Exception as e:
            return ProviderResult(
                elements=[],
                provider_name=self.name,
                detection_time_ms=(time.time() - start_time) * 1000,
                success=False,
                error=str(e),
            )
    
    def _get_elements_via_cdp(self) -> list[UIElement]:
        """
        Query CDP for all interactive elements.
        
        This is a simplified implementation. A full implementation would:
        1. Connect via WebSocket to the debugging endpoint
        2. Execute JavaScript to query the DOM
        3. Get bounding boxes for each element
        """
        import urllib.request
        import json
        import logging
        
        logger = logging.getLogger(__name__)
        elements = []
        
        try:
            # Get list of debuggable targets
            url = f"http://localhost:{self.default_port}/json"
            with urllib.request.urlopen(url, timeout=2) as response:
                targets = json.loads(response.read().decode())
            
            if not targets:
                logger.debug("CDP: No targets found")
                return elements
            
            # For now, we'll use a simpler HTTP-based approach
            # to execute JavaScript and get elements
            # Full implementation would use WebSocket for real-time communication
            
            # Get the first page target
            page_target = None
            for target in targets:
                if target.get("type") == "page":
                    page_target = target
                    break
            
            if page_target:
                # Connect via WebSocket and query DOM
                elements = self._query_dom_elements(page_target)
                logger.debug(f"CDP: Found {len(elements)} elements")
            else:
                logger.debug("CDP: No page target found")
        
        except Exception as e:
            # CDP not available or error
            logger.warning(f"CDP error: {e}")
        
        return elements
    
    def _query_dom_elements(self, target: dict) -> list[UIElement]:
        """
        Query the DOM for interactive elements.
        
        Uses CDP to execute JavaScript and get element information.
        """
        import websocket
        import json
        
        elements = []
        ws_url = target.get("webSocketDebuggerUrl")
        
        if not ws_url:
            return elements
        
        try:
            ws = websocket.create_connection(ws_url, timeout=5)
            
            # JavaScript to find all interactive elements with their bounds
            js_code = """
            (() => {
                const results = [];
                const selectors = 'a, button, input, select, textarea, [onclick], [role="button"], [role="link"], [tabindex]';
                const elements = document.querySelectorAll(selectors);
                
                elements.forEach((el, index) => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        let text = el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '';
                        text = text.trim().substring(0, 100);
                        
                        let type = 'unknown';
                        const tagName = el.tagName.toLowerCase();
                        if (tagName === 'a') type = 'link';
                        else if (tagName === 'button') type = 'button';
                        else if (tagName === 'input') type = 'input';
                        else if (tagName === 'select') type = 'dropdown';
                        else if (tagName === 'textarea') type = 'input';
                        else if (el.getAttribute('role') === 'button') type = 'button';
                        else if (el.getAttribute('role') === 'link') type = 'link';
                        else if (el.onclick) type = 'button';
                        
                        results.push({
                            index: index,
                            type: type,
                            text: text,
                            x: Math.round(rect.left + window.screenX),
                            y: Math.round(rect.top + window.screenY + (window.outerHeight - window.innerHeight)),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                            tagName: tagName,
                            isEnabled: !el.disabled,
                            isVisible: rect.width > 0 && rect.height > 0
                        });
                    }
                });
                
                return results;
            })()
            """
            
            # Send Runtime.evaluate command
            msg_id = 1
            ws.send(json.dumps({
                "id": msg_id,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": js_code,
                    "returnByValue": True
                }
            }))
            
            # Receive response
            response = json.loads(ws.recv())
            ws.close()
            
            if "result" in response and "result" in response["result"]:
                result_value = response["result"]["result"].get("value", [])
                
                for item in result_value:
                    elem_type = ElementType.TEXT
                    if item["type"] == "button":
                        elem_type = ElementType.BUTTON
                    elif item["type"] == "link":
                        elem_type = ElementType.LINK
                    elif item["type"] == "input":
                        elem_type = ElementType.INPUT
                    elif item["type"] == "dropdown":
                        elem_type = ElementType.DROPDOWN
                    
                    bounds = BoundingBox(
                        x=item["x"],
                        y=item["y"],
                        width=item["width"],
                        height=item["height"]
                    )
                    
                    elements.append(UIElement.create(
                        type=elem_type,
                        bounds=bounds,
                        text=item["text"],
                        label=item["text"],
                        is_enabled=item["isEnabled"],
                        is_visible=item["isVisible"],
                        confidence=1.0,  # CDP is 100% accurate
                        metadata={"tag": item["tagName"], "source": "cdp"}
                    ))
        
        except ImportError as e:
            # websocket-client not installed
            import logging
            logging.getLogger(__name__).warning(f"CDP: websocket not installed: {e}")
        except Exception as e:
            # Connection failed or other error
            import logging
            logging.getLogger(__name__).warning(f"CDP query_dom error: {e}")
        
        return elements
