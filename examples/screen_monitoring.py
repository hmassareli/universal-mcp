"""
Example: Screen Monitoring

This example demonstrates how to monitor the screen for changes
and react to specific UI elements appearing.
"""

import time
from mcp_desktop_visual.engine import DesktopVisualEngine


def monitor_for_element(engine: DesktopVisualEngine, target_label: str, timeout: float = 30.0):
    """
    Monitor the screen and wait for a specific element to appear.
    
    Args:
        engine: The desktop visual engine
        target_label: Label of element to watch for
        timeout: Maximum time to wait in seconds
    
    Returns:
        The element if found, None if timeout
    """
    print(f"   Watching for '{target_label}'...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Capture and analyze
        diff = engine.capture_and_analyze()
        
        if diff.has_changes:
            print(f"   📸 Screen changed ({diff.total_added} added, {diff.total_removed} removed)")
            
            # Check if target appeared
            elem = engine.find_element_by_label(target_label)
            if elem:
                return elem
        
        time.sleep(0.5)
    
    return None


def monitor_changes(engine: DesktopVisualEngine, duration: float = 10.0):
    """
    Monitor screen changes for a period of time.
    
    Args:
        engine: The desktop visual engine
        duration: How long to monitor in seconds
    """
    print(f"   Monitoring for {duration} seconds...")
    start_time = time.time()
    change_count = 0
    
    while time.time() - start_time < duration:
        diff = engine.capture_and_analyze()
        
        if diff.has_changes:
            change_count += 1
            print(f"\n   Change #{change_count}:")
            
            for region in diff.changed_regions:
                print(f"      Region: {region.bounds.to_tuple()}")
                
                for elem in region.added_elements:
                    print(f"         + Added: {elem.type.value} - {elem.label or elem.text or '(no text)'}")
                
                for elem in region.removed_elements:
                    print(f"         - Removed: {elem.type.value} - {elem.label or elem.text or '(no text)'}")
        
        time.sleep(0.5)
    
    print(f"\n   Total changes: {change_count}")


def main():
    print("👁️  Screen Monitoring Example")
    print("=" * 50)
    print()
    print("This example monitors the screen for changes.")
    print("Try moving windows or clicking buttons while it runs.")
    print()
    
    with DesktopVisualEngine() as engine:
        # Initial capture
        print("🔍 Initial screen capture...")
        state = engine.get_state()
        print(f"   {len(state.elements)} elements, {len(state.windows)} windows")
        
        # Monitor for changes
        print("\n📡 Monitoring screen changes...")
        monitor_changes(engine, duration=15.0)
        
        # Example: Wait for specific element
        # print("\n⏳ Waiting for 'Success' message...")
        # elem = monitor_for_element(engine, "Success", timeout=30.0)
        # if elem:
        #     print(f"   Found at {elem.bounds.center}!")
        # else:
        #     print("   Timeout - element not found")
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
