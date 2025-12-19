"""
Data models for MCP Desktop Visual.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime
import uuid


class ElementType(str, Enum):
    """Types of UI elements that can be detected."""
    
    BUTTON = "button"
    TEXT = "text"
    INPUT = "input"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    LINK = "link"
    ICON = "icon"
    IMAGE = "image"
    WINDOW = "window"
    MENU = "menu"
    MENU_ITEM = "menu_item"
    TAB = "tab"
    LIST_ITEM = "list_item"
    DROPDOWN = "dropdown"
    SCROLLBAR = "scrollbar"
    TOOLBAR = "toolbar"
    UNKNOWN = "unknown"


class ActionType(str, Enum):
    """Types of actions that can be performed."""
    
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    DRAG = "drag"
    DROP = "drop"
    TYPE = "type"
    PRESS_KEY = "press_key"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    MOVE = "move"
    HOVER = "hover"


class ChangeType(str, Enum):
    """Types of changes detected in visual state."""
    
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    MOVED = "moved"


@dataclass
class BoundingBox:
    """Represents a rectangular region on screen."""
    
    x: int
    y: int
    width: int
    height: int
    
    @property
    def x2(self) -> int:
        """Right edge x coordinate."""
        return self.x + self.width
    
    @property
    def y2(self) -> int:
        """Bottom edge y coordinate."""
        return self.y + self.height
    
    @property
    def center(self) -> tuple[int, int]:
        """Center point of the bounding box."""
        return (self.x + self.width // 2, self.y + self.height // 2)
    
    @property
    def area(self) -> int:
        """Area of the bounding box."""
        return self.width * self.height
    
    def contains(self, x: int, y: int) -> bool:
        """Check if a point is inside the bounding box."""
        return self.x <= x <= self.x2 and self.y <= y <= self.y2
    
    def intersects(self, other: "BoundingBox") -> bool:
        """Check if this bounding box intersects with another."""
        return not (
            self.x2 < other.x or
            other.x2 < self.x or
            self.y2 < other.y or
            other.y2 < self.y
        )
    
    def intersection(self, other: "BoundingBox") -> Optional["BoundingBox"]:
        """Get the intersection of two bounding boxes."""
        if not self.intersects(other):
            return None
        
        x = max(self.x, other.x)
        y = max(self.y, other.y)
        x2 = min(self.x2, other.x2)
        y2 = min(self.y2, other.y2)
        
        return BoundingBox(x, y, x2 - x, y2 - y)
    
    def union(self, other: "BoundingBox") -> "BoundingBox":
        """Get the union (smallest enclosing box) of two bounding boxes."""
        x = min(self.x, other.x)
        y = min(self.y, other.y)
        x2 = max(self.x2, other.x2)
        y2 = max(self.y2, other.y2)
        
        return BoundingBox(x, y, x2 - x, y2 - y)
    
    def to_tuple(self) -> tuple[int, int, int, int]:
        """Convert to tuple (x, y, width, height)."""
        return (self.x, self.y, self.width, self.height)
    
    def to_region(self) -> tuple[int, int, int, int]:
        """Convert to region tuple (x, y, x2, y2)."""
        return (self.x, self.y, self.x2, self.y2)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }
    
    @classmethod
    def from_region(cls, x1: int, y1: int, x2: int, y2: int) -> "BoundingBox":
        """Create from region coordinates (x1, y1, x2, y2)."""
        return cls(x1, y1, x2 - x1, y2 - y1)
    
    @classmethod
    def from_dict(cls, data: dict) -> "BoundingBox":
        """Create from dictionary."""
        return cls(
            x=data["x"],
            y=data["y"],
            width=data["width"],
            height=data["height"],
        )


@dataclass
class UIElement:
    """Represents a detected UI element on screen."""
    
    id: str
    type: ElementType
    bounds: BoundingBox
    label: Optional[str] = None
    text: Optional[str] = None
    confidence: float = 1.0
    is_enabled: bool = True
    is_visible: bool = True
    is_focused: bool = False
    parent_id: Optional[str] = None
    window_title: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    detected_at: datetime = field(default_factory=datetime.now)
    
    @staticmethod
    def _generate_stable_id(
        type: "ElementType",
        bounds: "BoundingBox",
        label: Optional[str] = None,
        text: Optional[str] = None,
    ) -> str:
        """
        Generate a stable ID based on element position only.
        
        We ignore text because OCR is not deterministic - the same
        image can produce slightly different text each time.
        Position is more stable for identifying "the same" element.
        """
        import hashlib
        # Use position rounded to grid cells (20px tolerance)
        # This allows small position variations without changing ID
        grid_size = 20
        pos_key = f"{bounds.x // grid_size}_{bounds.y // grid_size}_{bounds.width // grid_size}_{bounds.height // grid_size}"
        content = f"{type.value}:{pos_key}"
        hash_hex = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"elem_{hash_hex}"
    
    @classmethod
    def create(
        cls,
        type: ElementType,
        bounds: BoundingBox,
        label: Optional[str] = None,
        text: Optional[str] = None,
        **kwargs
    ) -> "UIElement":
        """Create a new UI element with stable ID based on position."""
        return cls(
            id=cls._generate_stable_id(type, bounds, label, text),
            type=type,
            bounds=bounds,
            label=label,
            text=text,
            **kwargs
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "bounds": self.bounds.to_dict(),
            "label": self.label,
            "text": self.text,
            "confidence": self.confidence,
            "is_enabled": self.is_enabled,
            "is_visible": self.is_visible,
            "is_focused": self.is_focused,
            "parent_id": self.parent_id,
            "window_title": self.window_title,
            "metadata": self.metadata,
            "position": list(self.bounds.center),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "UIElement":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            type=ElementType(data["type"]),
            bounds=BoundingBox.from_dict(data["bounds"]),
            label=data.get("label"),
            text=data.get("text"),
            confidence=data.get("confidence", 1.0),
            is_enabled=data.get("is_enabled", True),
            is_visible=data.get("is_visible", True),
            is_focused=data.get("is_focused", False),
            parent_id=data.get("parent_id"),
            window_title=data.get("window_title"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WindowInfo:
    """Information about a window."""
    
    handle: int
    title: str
    bounds: BoundingBox
    class_name: str = ""
    process_name: str = ""
    process_id: int = 0
    is_active: bool = False
    is_visible: bool = True
    is_minimized: bool = False
    is_maximized: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "handle": self.handle,
            "title": self.title,
            "bounds": self.bounds.to_dict(),
            "class_name": self.class_name,
            "process_name": self.process_name,
            "process_id": self.process_id,
            "is_active": self.is_active,
            "is_visible": self.is_visible,
            "is_minimized": self.is_minimized,
            "is_maximized": self.is_maximized,
        }


@dataclass
class ChangedRegion:
    """Represents a region of the screen that has changed."""
    
    bounds: BoundingBox
    change_type: ChangeType
    added_elements: list[UIElement] = field(default_factory=list)
    removed_elements: list[UIElement] = field(default_factory=list)
    modified_elements: list[UIElement] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "region": self.bounds.to_region(),
            "change_type": self.change_type.value,
            "added": [e.to_dict() for e in self.added_elements],
            "removed": [e.to_dict() for e in self.removed_elements],
            "modified": [e.to_dict() for e in self.modified_elements],
        }


@dataclass
class VisualDiff:
    """Represents changes between two visual states."""
    
    timestamp: datetime
    changed_regions: list[ChangedRegion] = field(default_factory=list)
    total_added: int = 0
    total_removed: int = 0
    total_modified: int = 0
    
    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return len(self.changed_regions) > 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "changed": [r.to_dict() for r in self.changed_regions],
            "summary": {
                "total_added": self.total_added,
                "total_removed": self.total_removed,
                "total_modified": self.total_modified,
            },
        }


@dataclass
class ScreenState:
    """Complete state of the screen at a point in time."""
    
    timestamp: datetime
    elements: list[UIElement] = field(default_factory=list)
    windows: list[WindowInfo] = field(default_factory=list)
    active_window: Optional[str] = None
    screen_size: tuple[int, int] = (1920, 1080)
    
    def get_element_by_id(self, element_id: str) -> Optional[UIElement]:
        """Find element by ID."""
        for elem in self.elements:
            if elem.id == element_id:
                return elem
        return None
    
    def get_element_by_label(self, label: str) -> Optional[UIElement]:
        """Find element by label (case-insensitive partial match)."""
        label_lower = label.lower()
        for elem in self.elements:
            if elem.label and label_lower in elem.label.lower():
                return elem
        return None
    
    def get_elements_by_type(self, element_type: ElementType) -> list[UIElement]:
        """Get all elements of a specific type."""
        return [e for e in self.elements if e.type == element_type]
    
    def get_element_at(self, x: int, y: int) -> Optional[UIElement]:
        """Find element at position."""
        # Return the smallest element containing the point
        matching = [e for e in self.elements if e.bounds.contains(x, y)]
        if not matching:
            return None
        return min(matching, key=lambda e: e.bounds.area)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "elements": [e.to_dict() for e in self.elements],
            "windows": [w.to_dict() for w in self.windows],
            "active_window": self.active_window,
            "screen_size": list(self.screen_size),
            "element_count": len(self.elements),
        }


@dataclass
class ActionResult:
    """Result of performing an action."""
    
    success: bool
    action_type: ActionType
    target_element: Optional[str] = None
    position: Optional[tuple[int, int]] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "action": self.action_type.value,
            "target": self.target_element,
            "position": list(self.position) if self.position else None,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }
