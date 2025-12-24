"""
Configuration management for MCP Desktop Visual.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json
import os


@dataclass
class CaptureConfig:
    """Screen capture configuration."""
    
    # Monitor to capture (None = primary monitor)
    monitor: Optional[int] = None
    
    # Capture interval in seconds for continuous monitoring
    capture_interval: float = 0.5
    
    # Minimum difference threshold for detecting changes (0-255)
    diff_threshold: int = 30
    
    # Minimum area size (pixels) to consider as a changed region
    min_region_area: int = 100
    
    # Maximum number of regions to track
    max_regions: int = 50
    
    # Downscale factor for diff comparison (1 = full resolution)
    diff_scale: float = 0.5


@dataclass
class OCRConfig:
    """OCR configuration."""
    
    # Path to Tesseract executable (None = auto-detect)
    tesseract_path: Optional[str] = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    
    # OCR language(s) - por+eng for Portuguese and English
    language: str = "por+eng"
    
    # Page segmentation mode (6 = assume uniform block of text, 11 = sparse text)
    psm: int = 11
    
    # OCR confidence threshold (0-100) - lower = more results but more noise
    confidence_threshold: int = 50
    
    # Enable preprocessing (lighter preprocessing in fast mode)
    preprocessing: bool = True


@dataclass 
class ElementDetectionConfig:
    """UI element detection configuration."""
    
    # Enable button detection (disabled by default in fast mode - shapes only)
    detect_buttons: bool = False
    
    # Enable text input detection
    detect_inputs: bool = False
    
    # Enable checkbox/radio detection
    detect_checkboxes: bool = False
    
    # Enable icon detection
    detect_icons: bool = False
    
    # Minimum element size (width, height)
    min_element_size: tuple[int, int] = (15, 10)
    
    # Maximum element size (width, height)
    max_element_size: tuple[int, int] = (1500, 800)
    
    # Edge detection sensitivity
    edge_sensitivity: int = 50


@dataclass
class InputConfig:
    """Mouse and keyboard input configuration."""
    
    # Click delay in seconds
    click_delay: float = 0.1
    
    # Typing delay between characters in seconds
    typing_delay: float = 0.02
    
    # Mouse movement duration in seconds
    move_duration: float = 0.2
    
    # Enable fail-safe (move mouse to corner to abort)
    # Disabled to allow clicking in corners of the screen
    failsafe: bool = False
    
    # Pause after each action in seconds
    pause_after_action: float = 0.1


@dataclass
class CacheConfig:
    """Visual state cache configuration."""
    
    # Maximum number of elements to cache
    max_elements: int = 1000
    
    # Maximum history states to keep
    max_history: int = 10
    
    # Element position tolerance for matching (pixels)
    position_tolerance: int = 5
    
    # Enable element grouping by window
    group_by_window: bool = True


@dataclass
class ServerConfig:
    """MCP server configuration."""
    
    # Server name
    name: str = "desktop-visual"
    
    # Server version
    version: str = "1.0.0"
    
    # Enable debug logging
    debug: bool = False
    
    # Log file path (None = console only)
    log_file: Optional[str] = None
    
    # Maximum concurrent operations
    max_concurrent: int = 5

    # Browser extension WebSocket bridge (127.0.0.1 only)
    browser_ws_host: str = "127.0.0.1"
    browser_ws_port: int = 8765


@dataclass
class Config:
    """Main configuration container."""
    
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    element_detection: ElementDetectionConfig = field(default_factory=ElementDetectionConfig)
    input: InputConfig = field(default_factory=InputConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    
    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """Load configuration from file or use defaults."""
        if path is None:
            # Try common locations
            candidates = [
                Path.cwd() / "mcp-desktop-config.json",
                Path.home() / ".mcp-desktop" / "config.json",
                Path(os.getenv("APPDATA", "")) / "mcp-desktop" / "config.json",
            ]
            for candidate in candidates:
                if candidate.exists():
                    path = candidate
                    break
        
        if path and path.exists():
            return cls.from_json(path)
        
        return cls()
    
    @classmethod
    def from_json(cls, path: Path) -> "Config":
        """Load configuration from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        config = cls()
        
        if "capture" in data:
            for key, value in data["capture"].items():
                if hasattr(config.capture, key):
                    setattr(config.capture, key, value)
        
        if "ocr" in data:
            for key, value in data["ocr"].items():
                if hasattr(config.ocr, key):
                    setattr(config.ocr, key, value)
        
        if "element_detection" in data:
            for key, value in data["element_detection"].items():
                if hasattr(config.element_detection, key):
                    if key in ("min_element_size", "max_element_size"):
                        value = tuple(value)
                    setattr(config.element_detection, key, value)
        
        if "input" in data:
            for key, value in data["input"].items():
                if hasattr(config.input, key):
                    setattr(config.input, key, value)
        
        if "cache" in data:
            for key, value in data["cache"].items():
                if hasattr(config.cache, key):
                    setattr(config.cache, key, value)
        
        if "server" in data:
            for key, value in data["server"].items():
                if hasattr(config.server, key):
                    setattr(config.server, key, value)
        
        return config
    
    def to_json(self, path: Path) -> None:
        """Save configuration to JSON file."""
        data = {
            "capture": {
                "monitor": self.capture.monitor,
                "capture_interval": self.capture.capture_interval,
                "diff_threshold": self.capture.diff_threshold,
                "min_region_area": self.capture.min_region_area,
                "max_regions": self.capture.max_regions,
                "diff_scale": self.capture.diff_scale,
            },
            "ocr": {
                "tesseract_path": self.ocr.tesseract_path,
                "language": self.ocr.language,
                "psm": self.ocr.psm,
                "confidence_threshold": self.ocr.confidence_threshold,
                "preprocessing": self.ocr.preprocessing,
            },
            "element_detection": {
                "detect_buttons": self.element_detection.detect_buttons,
                "detect_inputs": self.element_detection.detect_inputs,
                "detect_checkboxes": self.element_detection.detect_checkboxes,
                "detect_icons": self.element_detection.detect_icons,
                "min_element_size": list(self.element_detection.min_element_size),
                "max_element_size": list(self.element_detection.max_element_size),
                "edge_sensitivity": self.element_detection.edge_sensitivity,
            },
            "input": {
                "click_delay": self.input.click_delay,
                "typing_delay": self.input.typing_delay,
                "move_duration": self.input.move_duration,
                "failsafe": self.input.failsafe,
                "pause_after_action": self.input.pause_after_action,
            },
            "cache": {
                "max_elements": self.cache.max_elements,
                "max_history": self.cache.max_history,
                "position_tolerance": self.cache.position_tolerance,
                "group_by_window": self.cache.group_by_window,
            },
            "server": {
                "name": self.server.name,
                "version": self.server.version,
                "debug": self.server.debug,
                "log_file": self.server.log_file,
                "max_concurrent": self.server.max_concurrent,
            },
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
