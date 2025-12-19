"""Debug script to test MCP engine."""
import sys
sys.path.insert(0, 'src')

import logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s: %(message)s')

from mcp_desktop_visual.engine import DesktopVisualEngine

print("Creating engine...")
e = DesktopVisualEngine()

print("Starting engine...")
e.start()

print(f"Provider: {e._last_provider_name}")
print(f"Elements in cache: {len(e._cache.current_state.elements)}")

if e._cache.current_state.elements:
    print("First 5 elements:")
    for elem in e._cache.current_state.elements[:5]:
        print(f"  - {elem.type.value}: {elem.text[:40] if elem.text else 'N/A'}")

e.stop()
print("Done!")
