"""
Example: Automated Form Filling

This example demonstrates how to automate filling out a form
using the MCP Desktop Visual engine.
"""

import time
from mcp_desktop_visual.engine import DesktopVisualEngine


def fill_form(engine: DesktopVisualEngine, form_data: dict):
    """
    Fill a form with the given data.
    
    Args:
        engine: The desktop visual engine
        form_data: Dictionary mapping field labels to values
    """
    for field_label, value in form_data.items():
        print(f"   Filling '{field_label}' with '{value}'...")
        
        # Find the input field
        elem = engine.find_element_by_label(field_label)
        
        if elem is None:
            # Try refreshing and searching again
            engine.refresh()
            elem = engine.find_element_by_label(field_label)
        
        if elem:
            # Type in the field
            result = engine.type_in(elem.id, value, clear_first=True)
            
            if result.success:
                print(f"      ✅ Done")
            else:
                print(f"      ❌ Failed: {result.error}")
        else:
            print(f"      ⚠️ Field not found")
        
        time.sleep(0.2)  # Brief pause between fields


def main():
    print("📝 Form Filling Example")
    print("=" * 50)
    print()
    print("This example will attempt to fill form fields on screen.")
    print("Make sure you have a form open before running.")
    print()
    input("Press Enter to continue...")
    
    # Example form data
    form_data = {
        "Username": "testuser",
        "Email": "test@example.com",
        "Password": "securepassword123",
    }
    
    with DesktopVisualEngine() as engine:
        # Initial capture
        print("\n🔍 Analyzing screen...")
        engine.refresh()
        
        # List available inputs
        inputs = engine.get_all_inputs()
        print(f"   Found {len(inputs)} input fields:")
        for inp in inputs[:10]:
            label = inp.label or inp.text or "(no label)"
            print(f"      - {label}")
        
        # Fill the form
        print("\n✏️ Filling form...")
        fill_form(engine, form_data)
        
        # Optionally submit
        print("\n🔘 Looking for submit button...")
        for label in ["Submit", "Sign Up", "Register", "OK", "Send"]:
            btn = engine.find_element_by_label(label)
            if btn:
                print(f"   Found: {label}")
                # Uncomment to actually click
                # result = engine.click(btn.id)
                # print(f"   Clicked: {result.success}")
                break
        else:
            print("   No submit button found")
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
