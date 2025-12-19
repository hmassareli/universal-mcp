"""Test CDP Provider with Chrome."""
import time

# Wait for Chrome to be ready
time.sleep(1)

from src.mcp_desktop_visual.providers import CDPProvider

# Test CDP
cdp = CDPProvider(default_port=9222)

print("Testing CDP connection...")
print(f"Port 9222 open: {cdp._check_debug_port(9222)}")
print(f"CDP available: {cdp.is_available()}")

if cdp.is_available():
    print("\nCDP is available! Testing detection...")
    result = cdp.detect()
    print(f"Success: {result.success}")
    print(f"Elements found: {len(result.elements)}")
    print(f"Time: {result.detection_time_ms:.1f}ms")
    
    if result.elements:
        print("\nFirst 10 elements:")
        for i, elem in enumerate(result.elements[:10]):
            label = elem.label[:40] if elem.label else "(no label)"
            print(f"  {i+1}. [{elem.type.value}] {label}")
            print(f"      Position: ({elem.bounds.x}, {elem.bounds.y}) Size: {elem.bounds.width}x{elem.bounds.height}")
else:
    print("\nCDP not available.")
    print("Make sure Chrome is running with --remote-debugging-port=9222")
