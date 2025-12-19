"""
OCR Provider - Fallback using Tesseract OCR.

This is the fallback provider when CDP and UIA are not available.
Uses screen capture + Tesseract OCR to detect text elements.

Use cases:
- Games
- Remote desktop (RDP/VNC)
- Applications that don't support accessibility APIs
- PDF viewers with rendered content
- Legacy applications
"""

import time
from typing import Optional

from .base import ElementProvider, ProviderResult
from ..models import UIElement, BoundingBox, ElementType


class OCRProvider(ElementProvider):
    """
    Provider that uses Tesseract OCR for element detection.
    
    This is the fallback provider - slowest but works with anything visible.
    """
    
    def __init__(self):
        self._ocr_engine = None
        self._capture = None
        self._available: Optional[bool] = None
    
    @property
    def name(self) -> str:
        return "OCR"
    
    @property
    def priority(self) -> int:
        return 10  # Lowest priority - fallback only
    
    def can_handle(self, process_name: str, window_title: str, window_class: str) -> bool:
        """OCR can handle anything visible on screen."""
        return True
    
    def is_available(self) -> bool:
        """Check if Tesseract OCR is available."""
        if self._available is None:
            try:
                from ..ocr import OCREngine
                engine = OCREngine()
                self._available = engine.is_available
            except Exception:
                self._available = False
        
        return self._available
    
    def _get_ocr_engine(self):
        """Get or create the OCR engine."""
        if self._ocr_engine is None:
            from ..ocr import OCREngine
            self._ocr_engine = OCREngine()
        return self._ocr_engine
    
    def _get_capture(self):
        """Get or create the screen capture."""
        if self._capture is None:
            from ..capture import ScreenCapture
            self._capture = ScreenCapture()
            self._capture.start()
        return self._capture
    
    def detect(
        self,
        window_handle: Optional[int] = None,
        region: Optional[BoundingBox] = None
    ) -> ProviderResult:
        """
        Detect UI elements using OCR.
        
        Captures the screen and runs Tesseract OCR to detect text.
        """
        start_time = time.time()
        
        if not self.is_available():
            return ProviderResult(
                elements=[],
                provider_name=self.name,
                detection_time_ms=(time.time() - start_time) * 1000,
                success=False,
                error="Tesseract OCR not available",
            )
        
        try:
            elements = self._detect_with_ocr(region)
            
            return ProviderResult(
                elements=elements,
                provider_name=self.name,
                detection_time_ms=(time.time() - start_time) * 1000,
                success=True,
                supports_click_detection=False,  # OCR can't tell if something is clickable
                supports_input_detection=False,  # OCR can't reliably detect input fields
                supports_text_content=True,      # OCR provides text content
            )
        except Exception as e:
            return ProviderResult(
                elements=[],
                provider_name=self.name,
                detection_time_ms=(time.time() - start_time) * 1000,
                success=False,
                error=str(e),
            )
    
    def _detect_with_ocr(self, region: Optional[BoundingBox] = None) -> list[UIElement]:
        """
        Capture screen and detect text using OCR.
        """
        elements = []
        
        capture = self._get_capture()
        ocr = self._get_ocr_engine()
        
        # Capture screen
        if region:
            # TODO: Implement region capture
            frame = capture.capture_full()
        else:
            frame = capture.capture_full()
        
        if frame is None:
            return elements
        
        # Run OCR
        ocr_result = ocr.extract_text(frame.image)
        
        # Convert OCR words to UI elements
        for word in ocr_result.words:
            elements.append(UIElement.create(
                type=ElementType.TEXT,
                bounds=word.bounds,
                text=word.text,
                label=word.text,
                confidence=word.confidence,
                metadata={"source": "ocr"}
            ))
        
        return elements
