"""
Visual State Cache - The "Virtual Desktop DOM"

Maintains a persistent cache of the visual state, enabling
incremental updates and efficient element lookups.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from rapidfuzz import fuzz

from .config import get_config, CacheConfig
from .models import (
    UIElement, WindowInfo, ScreenState, VisualDiff,
    ChangedRegion, ChangeType, BoundingBox, ElementType
)


@dataclass
class CacheStats:
    """Statistics about the cache."""
    
    total_elements: int
    total_windows: int
    history_size: int
    last_update: Optional[datetime]
    updates_count: int
    cache_hits: int
    cache_misses: int
    
    def to_dict(self) -> dict:
        return {
            "total_elements": self.total_elements,
            "total_windows": self.total_windows,
            "history_size": self.history_size,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "updates_count": self.updates_count,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
        }


class VisualStateCache:
    """
    Maintains the visual state of the desktop.
    
    Acts like a "Virtual DOM" for the desktop, tracking all visible
    elements and their positions. Supports incremental updates and
    efficient lookups.
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or get_config().cache
        
        # Current state
        self._elements: dict[str, UIElement] = {}
        self._windows: dict[int, WindowInfo] = {}
        self._active_window: Optional[str] = None
        self._screen_size: tuple[int, int] = (1920, 1080)
        self._last_update: Optional[datetime] = None
        
        # Indexes for fast lookups
        self._elements_by_label: dict[str, list[str]] = {}
        self._elements_by_type: dict[ElementType, list[str]] = {}
        self._elements_by_window: dict[str, list[str]] = {}
        
        # History for undo/comparison
        self._history: deque[ScreenState] = deque(maxlen=self.config.max_history)
        
        # Statistics
        self._updates_count = 0
        self._cache_hits = 0
        self._cache_misses = 0
    
    @property
    def current_state(self) -> ScreenState:
        """Get the current screen state."""
        return ScreenState(
            timestamp=self._last_update or datetime.now(),
            elements=list(self._elements.values()),
            windows=list(self._windows.values()),
            active_window=self._active_window,
            screen_size=self._screen_size,
        )
    
    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return CacheStats(
            total_elements=len(self._elements),
            total_windows=len(self._windows),
            history_size=len(self._history),
            last_update=self._last_update,
            updates_count=self._updates_count,
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses,
        )
    
    def update_full(self, state: ScreenState) -> VisualDiff:
        """
        Perform a full update of the cache.
        
        Compares the new state with the current state and returns
        a diff of what changed.
        """
        # Save current state to history
        if self._elements:
            self._history.append(self.current_state)
        
        # Compute diff
        diff = self._compute_diff(state)
        
        # Clear and rebuild cache
        self._elements.clear()
        self._elements_by_label.clear()
        self._elements_by_type.clear()
        self._elements_by_window.clear()
        
        for element in state.elements:
            self._add_element(element)
        
        self._windows = {w.handle: w for w in state.windows}
        self._active_window = state.active_window
        self._screen_size = state.screen_size
        self._last_update = state.timestamp
        self._updates_count += 1
        
        return diff
    
    def update_incremental(
        self,
        added: list[UIElement],
        removed: list[str],
        modified: list[UIElement]
    ) -> VisualDiff:
        """
        Perform an incremental update to the cache.
        
        Only processes the elements that changed.
        """
        # Save current state to history
        if self._elements:
            self._history.append(self.current_state)
        
        changed_regions: list[ChangedRegion] = []
        
        # Process removals
        for elem_id in removed:
            if elem_id in self._elements:
                elem = self._elements[elem_id]
                changed_regions.append(ChangedRegion(
                    bounds=elem.bounds,
                    change_type=ChangeType.REMOVED,
                    removed_elements=[elem],
                ))
                self._remove_element(elem_id)
        
        # Process additions
        for elem in added:
            self._add_element(elem)
            changed_regions.append(ChangedRegion(
                bounds=elem.bounds,
                change_type=ChangeType.ADDED,
                added_elements=[elem],
            ))
        
        # Process modifications
        for elem in modified:
            if elem.id in self._elements:
                old_elem = self._elements[elem.id]
                self._remove_element(elem.id)
                self._add_element(elem)
                changed_regions.append(ChangedRegion(
                    bounds=elem.bounds.union(old_elem.bounds),
                    change_type=ChangeType.MODIFIED,
                    modified_elements=[elem],
                ))
            else:
                # Treat as addition if not found
                self._add_element(elem)
                changed_regions.append(ChangedRegion(
                    bounds=elem.bounds,
                    change_type=ChangeType.ADDED,
                    added_elements=[elem],
                ))
        
        self._last_update = datetime.now()
        self._updates_count += 1
        
        # Merge overlapping regions
        changed_regions = self._merge_changed_regions(changed_regions)
        
        return VisualDiff(
            timestamp=self._last_update,
            changed_regions=changed_regions,
            total_added=len(added),
            total_removed=len(removed),
            total_modified=len(modified),
        )
    
    def _add_element(self, element: UIElement) -> None:
        """Add an element to the cache."""
        # Enforce max elements
        if len(self._elements) >= self.config.max_elements:
            # Remove oldest element (first added)
            oldest_id = next(iter(self._elements))
            self._remove_element(oldest_id)
        
        self._elements[element.id] = element
        
        # Index by label
        if element.label:
            label_lower = element.label.lower()
            if label_lower not in self._elements_by_label:
                self._elements_by_label[label_lower] = []
            self._elements_by_label[label_lower].append(element.id)
        
        # Index by type
        if element.type not in self._elements_by_type:
            self._elements_by_type[element.type] = []
        self._elements_by_type[element.type].append(element.id)
        
        # Index by window
        if element.window_title:
            if element.window_title not in self._elements_by_window:
                self._elements_by_window[element.window_title] = []
            self._elements_by_window[element.window_title].append(element.id)
    
    def _remove_element(self, element_id: str) -> None:
        """Remove an element from the cache."""
        if element_id not in self._elements:
            return
        
        element = self._elements[element_id]
        
        # Remove from indexes
        if element.label:
            label_lower = element.label.lower()
            if label_lower in self._elements_by_label:
                try:
                    self._elements_by_label[label_lower].remove(element_id)
                except ValueError:
                    pass
        
        if element.type in self._elements_by_type:
            try:
                self._elements_by_type[element.type].remove(element_id)
            except ValueError:
                pass
        
        if element.window_title and element.window_title in self._elements_by_window:
            try:
                self._elements_by_window[element.window_title].remove(element_id)
            except ValueError:
                pass
        
        del self._elements[element_id]
    
    def _compute_diff(self, new_state: ScreenState) -> VisualDiff:
        """Compute the difference between current state and new state."""
        old_ids = set(self._elements.keys())
        new_elements = {e.id: e for e in new_state.elements}
        new_ids = set(new_elements.keys())
        
        added_ids = new_ids - old_ids
        removed_ids = old_ids - new_ids
        common_ids = old_ids & new_ids
        
        added = [new_elements[id] for id in added_ids]
        removed = [self._elements[id] for id in removed_ids]
        modified = []
        
        for id in common_ids:
            old_elem = self._elements[id]
            new_elem = new_elements[id]
            if self._element_changed(old_elem, new_elem):
                modified.append(new_elem)
        
        changed_regions: list[ChangedRegion] = []
        
        if added:
            for elem in added:
                changed_regions.append(ChangedRegion(
                    bounds=elem.bounds,
                    change_type=ChangeType.ADDED,
                    added_elements=[elem],
                ))
        
        if removed:
            for elem in removed:
                changed_regions.append(ChangedRegion(
                    bounds=elem.bounds,
                    change_type=ChangeType.REMOVED,
                    removed_elements=[elem],
                ))
        
        if modified:
            for elem in modified:
                old_elem = self._elements[elem.id]
                changed_regions.append(ChangedRegion(
                    bounds=elem.bounds.union(old_elem.bounds),
                    change_type=ChangeType.MODIFIED,
                    modified_elements=[elem],
                ))
        
        # Merge overlapping regions
        changed_regions = self._merge_changed_regions(changed_regions)
        
        return VisualDiff(
            timestamp=new_state.timestamp,
            changed_regions=changed_regions,
            total_added=len(added),
            total_removed=len(removed),
            total_modified=len(modified),
        )
    
    def _element_changed(self, old: UIElement, new: UIElement) -> bool:
        """Check if an element has changed significantly."""
        tolerance = self.config.position_tolerance
        
        # Check position change
        if (abs(old.bounds.x - new.bounds.x) > tolerance or
            abs(old.bounds.y - new.bounds.y) > tolerance or
            abs(old.bounds.width - new.bounds.width) > tolerance or
            abs(old.bounds.height - new.bounds.height) > tolerance):
            return True
        
        # Check text/label change
        if old.label != new.label or old.text != new.text:
            return True
        
        # Check state change
        if (old.is_enabled != new.is_enabled or
            old.is_visible != new.is_visible or
            old.is_focused != new.is_focused):
            return True
        
        return False
    
    def _merge_changed_regions(
        self,
        regions: list[ChangedRegion]
    ) -> list[ChangedRegion]:
        """Merge overlapping changed regions."""
        if len(regions) <= 1:
            return regions
        
        # Sort by position
        regions.sort(key=lambda r: (r.bounds.y, r.bounds.x))
        
        merged = []
        current = regions[0]
        
        for region in regions[1:]:
            if current.bounds.intersects(region.bounds):
                # Merge regions
                current = ChangedRegion(
                    bounds=current.bounds.union(region.bounds),
                    change_type=ChangeType.MODIFIED,
                    added_elements=current.added_elements + region.added_elements,
                    removed_elements=current.removed_elements + region.removed_elements,
                    modified_elements=current.modified_elements + region.modified_elements,
                )
            else:
                merged.append(current)
                current = region
        
        merged.append(current)
        return merged
    
    # ==================== Query Methods ====================
    
    def get_element_by_id(self, element_id: str) -> Optional[UIElement]:
        """Get an element by its ID."""
        elem = self._elements.get(element_id)
        if elem:
            self._cache_hits += 1
        else:
            self._cache_misses += 1
        return elem
    
    def get_element_by_label(
        self,
        label: str,
        fuzzy: bool = True,
        threshold: int = 80
    ) -> Optional[UIElement]:
        """
        Get an element by its label.
        
        Args:
            label: Label to search for
            fuzzy: Use fuzzy matching
            threshold: Minimum similarity score (0-100)
        """
        label_lower = label.lower()
        
        # Try exact match first
        if label_lower in self._elements_by_label:
            elem_ids = self._elements_by_label[label_lower]
            if elem_ids:
                self._cache_hits += 1
                return self._elements.get(elem_ids[0])
        
        # Try fuzzy matching
        if fuzzy:
            best_match = None
            best_score = 0
            
            for elem in self._elements.values():
                if elem.label:
                    score = fuzz.ratio(label_lower, elem.label.lower())
                    if score > best_score and score >= threshold:
                        best_score = score
                        best_match = elem
            
            if best_match:
                self._cache_hits += 1
                return best_match
        
        self._cache_misses += 1
        return None
    
    def query_elements(
        self,
        label: Optional[str] = None,
        element_type: Optional[ElementType] = None,
        window_title: Optional[str] = None,
        bounds: Optional[BoundingBox] = None,
        limit: int = 50
    ) -> list[UIElement]:
        """
        Query elements with multiple filters.
        
        Args:
            label: Filter by label (partial match)
            element_type: Filter by element type
            window_title: Filter by window title
            bounds: Filter by region (elements within bounds)
            limit: Maximum results to return
        """
        results: list[UIElement] = []
        
        # Start with type filter if specified (usually smallest set)
        if element_type is not None:
            elem_ids = self._elements_by_type.get(element_type, [])
            candidates = [self._elements[id] for id in elem_ids if id in self._elements]
        else:
            candidates = list(self._elements.values())
        
        for elem in candidates:
            if len(results) >= limit:
                break
            
            # Apply filters
            if label is not None:
                if not elem.label or label.lower() not in elem.label.lower():
                    continue
            
            if window_title is not None:
                if not elem.window_title or window_title.lower() not in elem.window_title.lower():
                    continue
            
            if bounds is not None:
                if not bounds.intersects(elem.bounds):
                    continue
            
            results.append(elem)
        
        return results
    
    def get_element_at(self, x: int, y: int) -> Optional[UIElement]:
        """Get the element at a specific position."""
        matching = [
            elem for elem in self._elements.values()
            if elem.bounds.contains(x, y)
        ]
        
        if not matching:
            self._cache_misses += 1
            return None
        
        # Return smallest element (most specific)
        self._cache_hits += 1
        return min(matching, key=lambda e: e.bounds.area)
    
    def get_elements_by_type(self, element_type: ElementType) -> list[UIElement]:
        """Get all elements of a specific type."""
        elem_ids = self._elements_by_type.get(element_type, [])
        return [self._elements[id] for id in elem_ids if id in self._elements]
    
    def get_all_buttons(self) -> list[UIElement]:
        """Get all button elements."""
        return self.get_elements_by_type(ElementType.BUTTON)
    
    def get_all_inputs(self) -> list[UIElement]:
        """Get all input elements."""
        return self.get_elements_by_type(ElementType.INPUT)
    
    def get_all_text(self) -> list[UIElement]:
        """Get all text elements."""
        return self.get_elements_by_type(ElementType.TEXT)
    
    # ==================== Window Methods ====================
    
    def update_windows(self, windows: list[WindowInfo]) -> None:
        """Update the window list."""
        self._windows = {w.handle: w for w in windows}
        
        # Update active window
        for window in windows:
            if window.is_active:
                self._active_window = window.title
                break
    
    def get_window_by_title(
        self,
        title: str,
        fuzzy: bool = True
    ) -> Optional[WindowInfo]:
        """Find a window by title."""
        title_lower = title.lower()
        
        for window in self._windows.values():
            if title_lower in window.title.lower():
                return window
        
        if fuzzy:
            best_match = None
            best_score = 0
            
            for window in self._windows.values():
                score = fuzz.ratio(title_lower, window.title.lower())
                if score > best_score and score >= 60:
                    best_score = score
                    best_match = window
            
            return best_match
        
        return None
    
    def get_all_windows(self) -> list[WindowInfo]:
        """Get all windows."""
        return list(self._windows.values())
    
    def get_active_window(self) -> Optional[WindowInfo]:
        """Get the active window."""
        for window in self._windows.values():
            if window.is_active:
                return window
        return None
    
    # ==================== Utility Methods ====================
    
    def clear(self) -> None:
        """Clear all cached data."""
        self._elements.clear()
        self._windows.clear()
        self._elements_by_label.clear()
        self._elements_by_type.clear()
        self._elements_by_window.clear()
        self._history.clear()
        self._active_window = None
        self._last_update = None
    
    def get_summary(self) -> dict:
        """Get a summary of the current state."""
        type_counts = {}
        for elem_type, elem_ids in self._elements_by_type.items():
            type_counts[elem_type.value] = len(elem_ids)
        
        return {
            "timestamp": self._last_update.isoformat() if self._last_update else None,
            "screen_size": list(self._screen_size),
            "total_elements": len(self._elements),
            "total_windows": len(self._windows),
            "active_window": self._active_window,
            "elements_by_type": type_counts,
            "stats": self.stats.to_dict(),
        }


# Global cache instance
_cache: Optional[VisualStateCache] = None


def get_visual_cache() -> VisualStateCache:
    """Get the global visual state cache instance."""
    global _cache
    if _cache is None:
        _cache = VisualStateCache()
    return _cache
