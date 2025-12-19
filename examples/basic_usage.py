"""
Example usage of MCP Desktop Visual (programmatic API).

This shows how to use the engine directly from Python.
For MCP tool usage, see the README.md.
"""

from mcp_desktop_visual.engine import DesktopVisualEngine
import time


def main():
    print("🖥️  MCP Desktop Visual - Example")
    print("=" * 50)
    
    # Create and start the engine
    with DesktopVisualEngine() as engine:
        # Get screen state
        print("\n📸 Getting screen state...")
        state = engine.get_state()
        print(f"   Found {len(state.elements)} elements")
        print(f"   Found {len(state.windows)} windows")
        print(f"   Screen size: {state.screen_size}")
        
        # List some buttons
        print("\n🔘 Buttons on screen:")
        buttons = engine.get_all_buttons()
        for btn in buttons[:5]:
            label = btn.label or "(no label)"
            pos = btn.bounds.center
            print(f"   - {label} at ({pos[0]}, {pos[1]})")
        
        if len(buttons) > 5:
            print(f"   ... and {len(buttons) - 5} more")
        
        # List windows
        print("\n🪟 Windows:")
        windows = engine.get_all_windows()
        for win in windows[:5]:
            status = "[Active]" if win.is_active else ""
            print(f"   - {win.title[:50]} {status}")
        
        # Get mouse position
        print("\n🖱️  Mouse position:")
        pos = engine.get_mouse_position()
        print(f"   ({pos[0]}, {pos[1]})")
        
        # Find element at mouse
        elem = engine.find_element_at(pos[0], pos[1])
        if elem:
            print(f"   Element under cursor: {elem.type.value} - {elem.label or elem.text or '(no text)'}")
        
        # Example: Query elements by label (uncomment to test)
        # print("\n🔍 Searching for 'Settings'...")
        # results = engine.query_elements(label="Settings")
        # for elem in results:
        #     print(f"   - {elem.type.value}: {elem.label} at {elem.bounds.center}")
        
        # Example: Wait for changes (uncomment to test)
        # print("\n⏳ Waiting for screen changes (move a window)...")
        # if engine.wait_for_change(timeout=5.0):
        #     print("   Change detected!")
        # else:
        #     print("   No changes in 5 seconds")
        
        # Example: Click on element by label (uncomment to test)
        # print("\n🖱️ Clicking 'OK' button...")
        # result = engine.click("OK")
        # if result.success:
        #     print(f"   Clicked at {result.position}")
        # else:
        #     print(f"   Failed: {result.error}")
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
