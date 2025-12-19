"""
Base classes for UI element detection providers.

All providers implement the same interface, making them interchangeable.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from ..models import UIElement, BoundingBox, ElementType


@dataclass
class ProviderResult:
    """Result from a provider detection."""
    
    elements: list[UIElement] = field(default_factory=list)
    provider_name: str = "unknown"
    detection_time_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    
    # Provider-specific capabilities detected
    supports_click_detection: bool = False  # Can tell if element is clickable
    supports_input_detection: bool = False  # Can detect input fields
    supports_text_content: bool = False     # Has accurate text content
    
    def to_dict(self) -> dict:
        return {
            "provider": self.provider_name,
            "elements_count": len(self.elements),
            "detection_time_ms": self.detection_time_ms,
            "success": self.success,
            "error": self.error,
            "capabilities": {
                "click_detection": self.supports_click_detection,
                "input_detection": self.supports_input_detection,
                "text_content": self.supports_text_content,
            }
        }


class ElementProvider(ABC):
    """
    Abstract base class for UI element detection providers.
    
    Each provider implements a different strategy for detecting UI elements:
    - CDP: Uses Chrome DevTools Protocol
    - UIA: Uses Windows UI Automation
    - OCR: Uses Tesseract OCR on screen images
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging and debugging."""
        pass
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """
        Priority for provider selection (higher = preferred).
        
        - CDP: 100 (best for Chromium apps)
        - UIA: 80 (good for native Windows apps)
        - OCR: 10 (fallback)
        """
        pass
    
    @abstractmethod
    def can_handle(self, process_name: str, window_title: str, window_class: str) -> bool:
        """
        Check if this provider can handle the given window.
        
        Args:
            process_name: Name of the process (e.g., "chrome.exe", "Code.exe")
            window_title: Title of the window
            window_class: Windows class name
        
        Returns:
            True if this provider can handle this window
        """
        pass
    
    @abstractmethod
    def detect(
        self,
        window_handle: Optional[int] = None,
        region: Optional[BoundingBox] = None
    ) -> ProviderResult:
        """
        Detect UI elements.
        
        Args:
            window_handle: Optional window handle to focus on
            region: Optional region to limit detection
        
        Returns:
            ProviderResult with detected elements
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available (dependencies installed, etc.)."""
        pass
    
    def find_element_by_text(
        self,
        text: str,
        elements: list[UIElement],
        fuzzy: bool = True
    ) -> Optional[UIElement]:
        """
        Find an element by its text content.
        
        Default implementation searches through detected elements.
        Providers can override for more efficient searching.
        """
        from rapidfuzz import fuzz
        
        text_lower = text.lower()
        
        # Exact match first
        for elem in elements:
            elem_text = (elem.text or elem.label or "").lower()
            if elem_text == text_lower:
                return elem
        
        # Fuzzy match
        if fuzzy:
            best_match = None
            best_score = 0
            
            for elem in elements:
                elem_text = (elem.text or elem.label or "").lower()
                if elem_text:
                    score = fuzz.ratio(text_lower, elem_text)
                    if score > best_score and score >= 70:
                        best_score = score
                        best_match = elem
            
            return best_match
        
        return None    
    def get_tabs(self) -> list[dict]:
        """
        Get list of open tabs (if supported by provider).
        
        Returns:
            List of tab dicts with: id, title, url, active
            Empty list if not supported.
        """
        return []
    
    def switch_tab(self, tab_id: str) -> bool:
        """
        Switch to a specific tab (if supported by provider).
        
        Args:
            tab_id: The tab ID to activate
            
        Returns:
            True if successful, False if not supported or failed
        """
        return False