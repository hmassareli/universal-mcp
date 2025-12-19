"""
OCR (Optical Character Recognition) module.

Extracts text from screen regions using Tesseract OCR.
"""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import numpy as np
import cv2

from .config import get_config, OCRConfig
from .models import BoundingBox


@dataclass
class OCRResult:
    """Result of OCR on a region."""
    
    text: str
    confidence: float
    bounds: BoundingBox
    words: list["WordResult"]
    
    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "bounds": self.bounds.to_dict(),
            "words": [w.to_dict() for w in self.words],
        }


@dataclass
class WordResult:
    """Individual word from OCR."""
    
    text: str
    confidence: float
    bounds: BoundingBox
    
    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "bounds": self.bounds.to_dict(),
        }


class OCREngine:
    """
    OCR engine using Tesseract.
    
    Provides text extraction from images with preprocessing
    for improved accuracy.
    """
    
    def __init__(self, config: Optional[OCRConfig] = None):
        self.config = config or get_config().ocr
        self._tesseract_path: Optional[str] = None
        self._tesseract_available = False
        self._check_tesseract()
    
    def _check_tesseract(self) -> None:
        """Check if Tesseract is available."""
        # Try configured path first
        if self.config.tesseract_path:
            if Path(self.config.tesseract_path).exists():
                self._tesseract_path = self.config.tesseract_path
                self._tesseract_available = True
                return
        
        # Try common Windows locations
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        ]
        
        for path in common_paths:
            if Path(path).exists():
                self._tesseract_path = path
                self._tesseract_available = True
                return
        
        # Try system PATH
        try:
            result = subprocess.run(
                ["tesseract", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                self._tesseract_path = "tesseract"
                self._tesseract_available = True
                return
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        self._tesseract_available = False
    
    @property
    def is_available(self) -> bool:
        """Check if OCR is available."""
        return self._tesseract_available
    
    def preprocess(self, image: np.ndarray, fast_mode: bool = False) -> np.ndarray:
        """
        Preprocess image for better OCR accuracy.
        
        Args:
            image: Input image
            fast_mode: If True, use lightweight preprocessing (faster but less accurate)
        """
        if not self.config.preprocessing:
            return image
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Resize if too small (OCR works better with larger text)
        h, w = gray.shape[:2]
        if h < 50 or w < 50:
            scale = max(50 / h, 50 / w, 2.0)
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        
        if fast_mode:
            # Fast mode: minimal preprocessing for screen captures (already clean)
            # Just apply CLAHE for contrast enhancement
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            return clahe.apply(gray)
        
        # Full mode: more processing for noisy images
        # Apply bilateral filter to reduce noise while keeping edges
        gray = cv2.bilateralFilter(gray, 5, 50, 50)  # Reduced params for speed
        
        # Increase contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        
        return gray
    
    def extract_text(
        self,
        image: np.ndarray,
        region_offset: tuple[int, int] = (0, 0),
        fast_mode: bool = True,
        get_positions: bool = True
    ) -> OCRResult:
        """
        Extract text from an image using Tesseract directly via subprocess.
        
        Args:
            image: Image as numpy array (BGR or grayscale)
            region_offset: Offset to add to word positions (x, y)
            fast_mode: Use fast preprocessing (default True for screen captures)
            get_positions: Get word bounding boxes (slower, uses TSV output)
        
        Returns:
            OCRResult with extracted text and word positions
        """
        if not self._tesseract_available:
            return OCRResult(
                text="",
                confidence=0.0,
                bounds=BoundingBox(0, 0, image.shape[1], image.shape[0]),
                words=[],
            )
        
        try:
            import tempfile
            
            # Preprocess image - use fast mode for screen captures
            processed = self.preprocess(image, fast_mode=fast_mode)
            
            # Save to temp file (tesseract needs a file)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                temp_path = f.name
                cv2.imwrite(temp_path, processed)
            
            try:
                # Run tesseract with TSV output for word positions
                result = subprocess.run(
                    [
                        self._tesseract_path,
                        temp_path,
                        'stdout',
                        '--psm', str(self.config.psm),
                        '-l', self.config.language,
                        '--oem', '3',
                        '-c', 'tessedit_create_tsv=1'
                    ],
                    capture_output=True,
                    timeout=30,
                    encoding='utf-8',
                    errors='replace',
                )
                
                words: list[WordResult] = []
                full_text_parts: list[str] = []
                total_confidence = 0.0
                word_count = 0
                offset_x, offset_y = region_offset
                
                # Parse TSV output
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # Skip header
                    for line in lines[1:]:
                        parts = line.split('\t')
                        if len(parts) >= 12:
                            try:
                                conf = float(parts[10]) if parts[10] != '-1' else 0
                                text = parts[11].strip() if len(parts) > 11 else ""
                                
                                if not text or conf < self.config.confidence_threshold:
                                    continue
                                
                                x = int(parts[6]) + offset_x
                                y = int(parts[7]) + offset_y
                                w = int(parts[8])
                                h = int(parts[9])
                                
                                words.append(WordResult(
                                    text=text,
                                    confidence=conf / 100.0,
                                    bounds=BoundingBox(x, y, w, h),
                                ))
                                
                                full_text_parts.append(text)
                                total_confidence += conf
                                word_count += 1
                            except (ValueError, IndexError):
                                continue
                
                avg_confidence = total_confidence / word_count if word_count > 0 else 0.0
                
                return OCRResult(
                    text=" ".join(full_text_parts),
                    confidence=avg_confidence / 100.0,
                    bounds=BoundingBox(
                        offset_x, offset_y, image.shape[1], image.shape[0]
                    ),
                    words=words,
                )
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_path)
                except:
                    pass
        
        except Exception as e:
            # OCR failed
            return OCRResult(
                text="",
                confidence=0.0,
                bounds=BoundingBox(0, 0, image.shape[1], image.shape[0]),
                words=[],
            )
    
    def extract_text_simple(self, image: np.ndarray, fast: bool = True) -> str:
        """Simple text extraction without word positions using subprocess."""
        if not self._tesseract_available:
            return ""
        
        try:
            import tempfile
            
            processed = self.preprocess(image, fast_mode=fast)
            
            # PSM 7 = single line, PSM 6 = block - use 7 for small regions (faster)
            psm = 7 if (image.shape[0] < 100 and image.shape[1] < 300) else self.config.psm
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                temp_path = f.name
                cv2.imwrite(temp_path, processed)
            
            try:
                result = subprocess.run(
                    [
                        self._tesseract_path,
                        temp_path,
                        'stdout',
                        '--psm', str(psm),
                        '-l', self.config.language,
                        '--oem', '3'
                    ],
                    capture_output=True,
                    timeout=15,
                    encoding='utf-8',
                    errors='replace',
                )
                return result.stdout.strip()
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass
        
        except Exception:
            return ""


# Global OCR engine instance
_ocr_engine: Optional[OCREngine] = None


def get_ocr_engine() -> OCREngine:
    """Get the global OCR engine instance."""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = OCREngine()
    return _ocr_engine
