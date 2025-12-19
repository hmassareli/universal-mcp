"""
UI Element Detection Providers.

This module provides different strategies for detecting UI elements:
- CDP: Chrome DevTools Protocol for Chromium-based apps (Chrome, Edge, VS Code, Electron apps)
- UIA: UI Automation for native Windows applications
- OCR: Tesseract OCR as fallback for anything else

The main detector will automatically choose the best provider based on the active window.
"""

from .base import ElementProvider, ProviderResult
from .registry import ProviderRegistry, get_provider_for_window
from .cdp import CDPProvider
from .uia import UIAProvider
from .ocr_provider import OCRProvider

__all__ = [
    "ElementProvider",
    "ProviderResult", 
    "ProviderRegistry",
    "get_provider_for_window",
    "CDPProvider",
    "UIAProvider",
    "OCRProvider",
]
