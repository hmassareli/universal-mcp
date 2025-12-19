"""
Provider Registry - Manages and selects the best provider for each window.
"""

from typing import Optional
from .base import ElementProvider, ProviderResult


class ProviderRegistry:
    """
    Registry of available element detection providers.
    
    Automatically selects the best provider based on the active window.
    """
    
    def __init__(self):
        self._providers: list[ElementProvider] = []
        self._initialized = False
    
    def register(self, provider: ElementProvider) -> None:
        """Register a provider."""
        self._providers.append(provider)
        # Keep sorted by priority (highest first)
        self._providers.sort(key=lambda p: p.priority, reverse=True)
    
    def get_provider(
        self,
        process_name: str,
        window_title: str,
        window_class: str
    ) -> Optional[ElementProvider]:
        """
        Get the best available provider for a window.
        
        Returns the highest-priority provider that:
        1. Is available (dependencies installed)
        2. Can handle this window type
        """
        for provider in self._providers:
            if provider.is_available() and provider.can_handle(process_name, window_title, window_class):
                return provider
        return None
    
    def get_all_providers(self) -> list[ElementProvider]:
        """Get all registered providers."""
        return self._providers.copy()
    
    def initialize(self) -> None:
        """Initialize all registered providers."""
        if self._initialized:
            return
        
        # Import and register providers here to avoid circular imports
        from .cdp import CDPProvider
        from .uia import UIAProvider
        from .ocr_provider import OCRProvider
        
        # Register in order of preference
        self.register(CDPProvider())
        self.register(UIAProvider())
        self.register(OCRProvider())
        
        self._initialized = True


# Global registry instance
_registry: Optional[ProviderRegistry] = None


def get_registry() -> ProviderRegistry:
    """Get the global provider registry."""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
        _registry.initialize()
    return _registry


def get_provider_for_window(
    process_name: str,
    window_title: str,
    window_class: str
) -> Optional[ElementProvider]:
    """
    Get the best provider for a specific window.
    
    Convenience function that uses the global registry.
    """
    return get_registry().get_provider(process_name, window_title, window_class)
