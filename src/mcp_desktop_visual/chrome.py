"""Chrome helpers.

This project no longer controls Chrome via CDP/debug ports.
The only supported browser-side behavior here is:
- open Chrome if it's not already running (optionally to a URL)

Any deeper browser automation should be implemented via the unpacked extension
in `browser_extension/`.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ChromeOpenResult:
    already_running: bool
    started: bool
    used_path: Optional[str]
    error: Optional[str] = None


_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def _find_chrome_exe() -> Optional[str]:
    for path in _CHROME_PATHS:
        if os.path.exists(path):
            return path
    return None


def _is_process_running(image_name: str) -> bool:
    """Return True if an image name is present in tasklist.

    Windows-only.
    """
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}"],
            capture_output=True,
            text=True,
            check=False,
        )
        out = (completed.stdout or "").lower()
        return image_name.lower() in out
    except Exception:
        return False


def ensure_chrome_open(url: Optional[str] = None) -> ChromeOpenResult:
    """Open Chrome only if it is not already running.

    Args:
        url: Optional URL to open.

    Returns:
        ChromeOpenResult describing what happened.
    """
    if _is_process_running("chrome.exe"):
        if url:
            try:
                subprocess.Popen(["cmd", "/c", "start", "", "chrome", url])
            except Exception:
                pass
        return ChromeOpenResult(already_running=True, started=False, used_path=None)

    chrome_exe = _find_chrome_exe()
    try:
        if chrome_exe:
            args = [chrome_exe]
            if url:
                args.append(url)
            subprocess.Popen(args)
            return ChromeOpenResult(already_running=False, started=True, used_path=chrome_exe)

        # Fallback: rely on app registration
        if url:
            subprocess.Popen(["cmd", "/c", "start", "", "chrome", url])
        else:
            subprocess.Popen(["cmd", "/c", "start", "", "chrome"])
        return ChromeOpenResult(already_running=False, started=True, used_path=None)
    except Exception as e:
        return ChromeOpenResult(already_running=False, started=False, used_path=chrome_exe, error=str(e))
