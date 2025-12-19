"""
UI Element detection module.

Detects UI elements (buttons, inputs, etc.) from screen images
using image processing and heuristics.
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np
import cv2

from .config import get_config, ElementDetectionConfig
from .models import BoundingBox, UIElement, ElementType
from .ocr import OCREngine, get_ocr_engine


@dataclass
class DetectionResult:
    """Result of element detection on an image."""
    
    elements: list[UIElement]
    processing_time_ms: float
    
    def to_dict(self) -> dict:
        return {
            "elements": [e.to_dict() for e in self.elements],
            "count": len(self.elements),
            "processing_time_ms": self.processing_time_ms,
        }


class ElementDetector:
    """
    Detects UI elements from screen images.
    
    Uses computer vision techniques to identify buttons, text inputs,
    checkboxes, and other interactive elements.
    """
    
    def __init__(
        self,
        config: Optional[ElementDetectionConfig] = None,
        ocr_engine: Optional[OCREngine] = None
    ):
        self.config = config or get_config().element_detection
        self.ocr = ocr_engine or get_ocr_engine()
    
    def detect(
        self,
        image: np.ndarray,
        region_offset: tuple[int, int] = (0, 0),
        fast_mode: bool = True
    ) -> DetectionResult:
        """
        Detect UI elements in an image.
        
        Args:
            image: BGR image as numpy array
            region_offset: Offset to add to element positions (x, y)
            fast_mode: If True, use optimized detection (skip heavy CV operations)
        
        Returns:
            DetectionResult with detected elements
        """
        import time
        start_time = time.time()
        
        elements: list[UIElement] = []
        offset_x, offset_y = region_offset
        
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        if fast_mode:
            # FAST MODE: Just run OCR once and create text elements
            # This is much faster and sufficient for most LLM interactions
            text_elements = self._detect_text(image, offset_x, offset_y)
            elements.extend(text_elements)
        else:
            # FULL MODE: Run all detection algorithms
            if self.config.detect_buttons:
                buttons = self._detect_buttons_fast(image, gray, offset_x, offset_y)
                elements.extend(buttons)
            
            if self.config.detect_inputs:
                inputs = self._detect_inputs(image, gray, offset_x, offset_y)
                elements.extend(inputs)
            
            if self.config.detect_checkboxes:
                checkboxes = self._detect_checkboxes(image, gray, offset_x, offset_y)
                elements.extend(checkboxes)
            
            # Detect text
            text_elements = self._detect_text(image, offset_x, offset_y)
            elements.extend(text_elements)
        
        # Remove duplicates and overlapping elements
        elements = self._filter_elements(elements)
        
        processing_time = (time.time() - start_time) * 1000
        
        return DetectionResult(
            elements=elements,
            processing_time_ms=processing_time,
        )
    
    def _detect_buttons_fast(
        self,
        image: np.ndarray,
        gray: np.ndarray,
        offset_x: int,
        offset_y: int
    ) -> list[UIElement]:
        """
        Fast button detection without individual OCR per button.
        Uses shape detection only - text will be matched from OCR results.
        """
        elements = []
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150)
        
        # Dilate to connect nearby edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=1)
        
        # Find contours
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        min_w, min_h = self.config.min_element_size
        max_w, max_h = self.config.max_element_size
        
        for contour in contours:
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            if len(approx) < 4 or len(approx) > 8:
                continue
            
            x, y, w, h = cv2.boundingRect(contour)
            
            if w < min_w or h < min_h or w > max_w or h > max_h:
                continue
            
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.5 or aspect_ratio > 8:
                continue
            
            region = gray[y:y+h, x:x+w]
            if region.size == 0:
                continue
            
            std_dev = np.std(region)
            if std_dev > 80:
                continue
            
            bounds = BoundingBox(x + offset_x, y + offset_y, w, h)
            
            # No OCR here - just detect the shape
            elements.append(UIElement.create(
                type=ElementType.BUTTON,
                bounds=bounds,
                confidence=0.5,
            ))
        
        return elements
    
    def _detect_buttons(
        self,
        image: np.ndarray,
        gray: np.ndarray,
        offset_x: int,
        offset_y: int
    ) -> list[UIElement]:
        """Detect button-like elements (legacy - calls OCR per button, slow)."""
        elements = []
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150)
        
        # Dilate to connect nearby edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=1)
        
        # Find contours
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        min_w, min_h = self.config.min_element_size
        max_w, max_h = self.config.max_element_size
        
        for contour in contours:
            # Approximate contour to polygon
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            # Buttons are typically rectangular (4 corners)
            if len(approx) < 4 or len(approx) > 8:
                continue
            
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by size
            if w < min_w or h < min_h or w > max_w or h > max_h:
                continue
            
            # Filter by aspect ratio (buttons are usually wider than tall)
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.3 or aspect_ratio > 10:
                continue
            
            # Check if region has consistent background (button-like)
            region = gray[y:y+h, x:x+w]
            if region.size == 0:
                continue
            
            std_dev = np.std(region)
            # Buttons typically have relatively uniform backgrounds
            if std_dev > 80:
                continue
            
            # Extract text from button region (SLOW!)
            button_img = image[y:y+h, x:x+w]
            ocr_result = self.ocr.extract_text(button_img)
            label = ocr_result.text if ocr_result.text else None
            
            bounds = BoundingBox(x + offset_x, y + offset_y, w, h)
            
            elements.append(UIElement.create(
                type=ElementType.BUTTON,
                bounds=bounds,
                label=label,
                text=label,
                confidence=0.7 if label else 0.5,
            ))
        
        return elements
    
    def _detect_inputs(
        self,
        image: np.ndarray,
        gray: np.ndarray,
        offset_x: int,
        offset_y: int
    ) -> list[UIElement]:
        """Detect text input fields."""
        elements = []
        
        # Input fields are typically rectangular with distinct borders
        edges = cv2.Canny(gray, 30, 100)
        
        # Find horizontal lines (input fields often have bottom border)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
        horizontal = cv2.morphologyEx(edges, cv2.MORPH_OPEN, horizontal_kernel)
        
        # Find contours in horizontal lines
        contours, _ = cv2.findContours(
            horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        min_w, min_h = self.config.min_element_size
        max_w, max_h = self.config.max_element_size
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Input fields are typically wider and have small height
            if w < 50 or w > max_w:
                continue
            
            # Expand to capture the full input field
            input_height = 30  # Typical input field height
            y_start = max(0, y - input_height)
            y_end = min(gray.shape[0], y + 5)
            
            if y_end - y_start < 15:
                continue
            
            bounds = BoundingBox(x + offset_x, y_start + offset_y, w, y_end - y_start)
            
            # Don't run OCR here - just detect the shape
            elements.append(UIElement.create(
                type=ElementType.INPUT,
                bounds=bounds,
                confidence=0.6,
            ))
        
        return elements
    
    def _detect_checkboxes(
        self,
        image: np.ndarray,
        gray: np.ndarray,
        offset_x: int,
        offset_y: int
    ) -> list[UIElement]:
        """Detect checkboxes and radio buttons."""
        elements = []
        
        # Look for small square/circular regions
        edges = cv2.Canny(gray, 50, 150)
        
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Checkboxes are small and roughly square
            if w < 10 or w > 30 or h < 10 or h > 30:
                continue
            
            # Check aspect ratio (should be close to 1:1)
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.7 or aspect_ratio > 1.4:
                continue
            
            # Calculate circularity
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue
            
            circularity = 4 * np.pi * area / (perimeter * perimeter)
            
            # Determine type based on shape
            if circularity > 0.7:
                elem_type = ElementType.RADIO
            else:
                elem_type = ElementType.CHECKBOX
            
            bounds = BoundingBox(x + offset_x, y + offset_y, w, h)
            
            elements.append(UIElement.create(
                type=elem_type,
                bounds=bounds,
                confidence=0.6,
            ))
        
        return elements
    
    def _detect_text(
        self,
        image: np.ndarray,
        offset_x: int,
        offset_y: int
    ) -> list[UIElement]:
        """Detect text elements using OCR."""
        elements = []
        
        ocr_result = self.ocr.extract_text(image, (offset_x, offset_y))
        
        for word in ocr_result.words:
            # Create text element for each detected word
            elements.append(UIElement.create(
                type=ElementType.TEXT,
                bounds=word.bounds,
                text=word.text,
                label=word.text,
                confidence=word.confidence,
            ))
        
        return elements
    
    def _filter_elements(self, elements: list[UIElement]) -> list[UIElement]:
        """Remove duplicate and overlapping elements."""
        if len(elements) <= 1:
            return elements
        
        # Sort by confidence (higher first)
        elements.sort(key=lambda e: e.confidence, reverse=True)
        
        filtered = []
        
        for elem in elements:
            # Check for significant overlap with existing elements
            is_duplicate = False
            
            for existing in filtered:
                if self._elements_overlap(elem, existing, threshold=0.5):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                filtered.append(elem)
        
        return filtered
    
    def _elements_overlap(
        self,
        elem1: UIElement,
        elem2: UIElement,
        threshold: float = 0.5
    ) -> bool:
        """Check if two elements overlap significantly."""
        intersection = elem1.bounds.intersection(elem2.bounds)
        if intersection is None:
            return False
        
        # Calculate overlap ratio
        intersection_area = intersection.area
        min_area = min(elem1.bounds.area, elem2.bounds.area)
        
        if min_area == 0:
            return False
        
        overlap_ratio = intersection_area / min_area
        return overlap_ratio > threshold


# Global detector instance
_detector: Optional[ElementDetector] = None


def get_element_detector() -> ElementDetector:
    """Get the global element detector instance."""
    global _detector
    if _detector is None:
        _detector = ElementDetector()
    return _detector
