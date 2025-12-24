"""
Windows UI Automation Provider.

Provides UI element detection for native Windows applications using
the Windows UI Automation API.

This works for most traditional Windows apps:
- Win32 applications
- WPF applications
- WinForms applications
- UWP applications

Does NOT work well for:
- Chromium-based apps (usually requires OCR fallback or browser-side integration)
- Games
- Custom rendering engines
"""

import time
from typing import Optional

from .base import ElementProvider, ProviderResult
from ..models import UIElement, BoundingBox, ElementType


# Process names that are known to NOT work well with UIA
# (usually because they're Chromium-based or have custom rendering)
UIA_BLACKLIST = {
    "chrome.exe", "msedge.exe", "brave.exe", "vivaldi.exe", "opera.exe",
    "code.exe", "slack.exe", "discord.exe", "teams.exe", "notion.exe",
    "spotify.exe", "figma.exe", "postman.exe", "insomnia.exe",
}


class UIAProvider(ElementProvider):
    """
    Provider that uses Windows UI Automation for element detection.
    
    UI Automation is a Windows API that provides access to the UI
    elements of applications that support accessibility.
    """
    
    def __init__(self):
        self._uia_available: Optional[bool] = None
        self._auto = None
    
    @property
    def name(self) -> str:
        return "UIA"
    
    @property
    def priority(self) -> int:
        return 80
    
    def can_handle(self, process_name: str, window_title: str, window_class: str) -> bool:
        """
        Check if this window is suitable for UI Automation.
        
        We handle everything EXCEPT known Chromium-based apps.
        """
        process_lower = process_name.lower()
        
        # Blacklisted processes (Chromium-based)
        if process_lower in UIA_BLACKLIST:
            return False
        
        # Most other Windows apps work with UIA
        return True
    
    def is_available(self) -> bool:
        """Check if uiautomation package is available."""
        if self._uia_available is None:
            try:
                import uiautomation
                self._auto = uiautomation
                self._uia_available = True
            except ImportError:
                self._uia_available = False
        
        return self._uia_available
    
    def detect(
        self,
        window_handle: Optional[int] = None,
        region: Optional[BoundingBox] = None
    ) -> ProviderResult:
        """
        Detect UI elements using Windows UI Automation.
        """
        start_time = time.time()
        
        if not self.is_available():
            return ProviderResult(
                elements=[],
                provider_name=self.name,
                detection_time_ms=(time.time() - start_time) * 1000,
                success=False,
                error="uiautomation package not installed",
            )
        
        try:
            elements = self._get_elements_via_uia(window_handle)
            
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
    
    def _get_elements_via_uia(self, window_handle: Optional[int] = None) -> list[UIElement]:
        """
        Get elements using UI Automation.
        """
        auto = self._auto
        elements = []
        
        # Get the target window or the foreground window
        if window_handle:
            root = auto.ControlFromHandle(window_handle)
        else:
            root = auto.GetForegroundControl()
        
        if not root:
            return elements
        
        # Find all interactive controls
        # We look for common control types that are usually interactive
        control_types = [
            ("ButtonControl", ElementType.BUTTON),
            ("HyperlinkControl", ElementType.LINK),
            ("EditControl", ElementType.INPUT),
            ("ComboBoxControl", ElementType.DROPDOWN),
            ("CheckBoxControl", ElementType.CHECKBOX),
            ("RadioButtonControl", ElementType.RADIO),
            ("MenuItemControl", ElementType.MENU_ITEM),
            ("TabItemControl", ElementType.TAB),
            ("ListItemControl", ElementType.LIST_ITEM),
        ]
        
        for control_method, elem_type in control_types:
            try:
                # Find all controls of this type
                controls = root.GetChildren()
                self._find_controls_recursive(root, control_method, elem_type, elements, max_depth=10)
            except Exception:
                continue
        
        # Also get all text elements
        self._find_text_elements(root, elements, max_depth=10)
        
        return elements
    
    def _find_controls_recursive(
        self,
        parent,
        control_type_name: str,
        elem_type: ElementType,
        elements: list[UIElement],
        max_depth: int,
        current_depth: int = 0
    ) -> None:
        """Recursively find controls of a specific type."""
        if current_depth >= max_depth:
            return
        
        auto = self._auto
        
        try:
            # Check if current element matches
            if parent.ControlTypeName == control_type_name.replace("Control", ""):
                rect = parent.BoundingRectangle
                if rect.width() > 0 and rect.height() > 0:
                    bounds = BoundingBox(
                        x=rect.left,
                        y=rect.top,
                        width=rect.width(),
                        height=rect.height()
                    )
                    
                    name = parent.Name or ""
                    
                    elements.append(UIElement.create(
                        type=elem_type,
                        bounds=bounds,
                        text=name,
                        label=name,
                        is_enabled=parent.IsEnabled,
                        confidence=1.0,
                        metadata={"control_type": control_type_name, "source": "uia"}
                    ))
            
            # Recurse into children
            for child in parent.GetChildren():
                self._find_controls_recursive(
                    child, control_type_name, elem_type, elements,
                    max_depth, current_depth + 1
                )
        except Exception:
            pass
    
    def _find_text_elements(
        self,
        parent,
        elements: list[UIElement],
        max_depth: int,
        current_depth: int = 0
    ) -> None:
        """Find text elements (labels, static text)."""
        if current_depth >= max_depth:
            return
        
        try:
            if parent.ControlTypeName in ("Text", "Static"):
                rect = parent.BoundingRectangle
                if rect.width() > 0 and rect.height() > 0:
                    name = parent.Name or ""
                    if name.strip():
                        bounds = BoundingBox(
                            x=rect.left,
                            y=rect.top,
                            width=rect.width(),
                            height=rect.height()
                        )
                        
                        elements.append(UIElement.create(
                            type=ElementType.TEXT,
                            bounds=bounds,
                            text=name,
                            label=name,
                            confidence=1.0,
                            metadata={"source": "uia"}
                        ))
            
            # Recurse into children
            for child in parent.GetChildren():
                self._find_text_elements(child, elements, max_depth, current_depth + 1)
        except Exception:
            pass
