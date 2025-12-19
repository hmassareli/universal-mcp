"""
Quick test script for MCP Desktop Visual.

Run this to verify everything is working correctly.
"""

import sys
import time


def test_imports():
    """Test that all modules can be imported."""
    print("📦 Testing imports...")
    
    try:
        from mcp_desktop_visual import __version__
        print(f"   ✅ mcp_desktop_visual v{__version__}")
    except ImportError as e:
        print(f"   ❌ Failed to import mcp_desktop_visual: {e}")
        return False
    
    try:
        from mcp_desktop_visual.capture import ScreenCapture
        print("   ✅ capture module")
    except ImportError as e:
        print(f"   ❌ Failed to import capture: {e}")
        return False
    
    try:
        from mcp_desktop_visual.ocr import OCREngine
        print("   ✅ ocr module")
    except ImportError as e:
        print(f"   ❌ Failed to import ocr: {e}")
        return False
    
    try:
        from mcp_desktop_visual.detector import ElementDetector
        print("   ✅ detector module")
    except ImportError as e:
        print(f"   ❌ Failed to import detector: {e}")
        return False
    
    try:
        from mcp_desktop_visual.input import InputController
        print("   ✅ input module")
    except ImportError as e:
        print(f"   ❌ Failed to import input: {e}")
        return False
    
    try:
        from mcp_desktop_visual.cache import VisualStateCache
        print("   ✅ cache module")
    except ImportError as e:
        print(f"   ❌ Failed to import cache: {e}")
        return False
    
    try:
        from mcp_desktop_visual.engine import DesktopVisualEngine
        print("   ✅ engine module")
    except ImportError as e:
        print(f"   ❌ Failed to import engine: {e}")
        return False
    
    try:
        from mcp_desktop_visual.windows import get_all_windows
        print("   ✅ windows module")
    except ImportError as e:
        print(f"   ❌ Failed to import windows: {e}")
        return False
    
    return True


def test_screen_capture():
    """Test screen capture functionality."""
    print("\n📷 Testing screen capture...")
    
    try:
        from mcp_desktop_visual.capture import ScreenCapture
        
        with ScreenCapture() as cap:
            # Full capture
            frame = cap.capture_full()
            print(f"   ✅ Full capture: {frame.width}x{frame.height}")
            
            # Incremental capture
            result1 = cap.capture_incremental()
            print(f"   ✅ First incremental: is_full={result1.is_full_capture}")
            
            time.sleep(0.1)
            
            result2 = cap.capture_incremental()
            print(f"   ✅ Second incremental: {len(result2.dirty_regions)} dirty regions")
        
        return True
    except Exception as e:
        print(f"   ❌ Screen capture failed: {e}")
        return False


def test_ocr():
    """Test OCR functionality."""
    print("\n🔤 Testing OCR...")
    
    try:
        from mcp_desktop_visual.ocr import OCREngine
        
        engine = OCREngine()
        
        if engine.is_available:
            print("   ✅ Tesseract OCR is available")
        else:
            print("   ⚠️  Tesseract OCR not found (text recognition disabled)")
            print("      Install from: https://github.com/UB-Mannheim/tesseract/wiki")
        
        return True
    except Exception as e:
        print(f"   ❌ OCR test failed: {e}")
        return False


def test_windows():
    """Test Windows API integration."""
    print("\n🪟 Testing Windows integration...")
    
    try:
        from mcp_desktop_visual.windows import (
            get_all_windows,
            get_screen_size,
            get_cursor_position,
        )
        
        # Get screen size
        width, height = get_screen_size()
        print(f"   ✅ Screen size: {width}x{height}")
        
        # Get cursor position
        x, y = get_cursor_position()
        print(f"   ✅ Cursor position: ({x}, {y})")
        
        # List windows
        windows = get_all_windows()
        print(f"   ✅ Found {len(windows)} windows")
        
        # Show first few
        for i, win in enumerate(windows[:3]):
            print(f"      - {win.title[:50]}...")
        
        return True
    except Exception as e:
        print(f"   ❌ Windows test failed: {e}")
        return False


def test_element_detection():
    """Test element detection."""
    print("\n🔍 Testing element detection...")
    
    try:
        from mcp_desktop_visual.capture import ScreenCapture
        from mcp_desktop_visual.detector import ElementDetector
        
        with ScreenCapture() as cap:
            frame = cap.capture_full()
        
        detector = ElementDetector()
        result = detector.detect(frame.image)
        
        print(f"   ✅ Detected {len(result.elements)} elements in {result.processing_time_ms:.1f}ms")
        
        # Count by type
        type_counts = {}
        for elem in result.elements:
            type_name = elem.type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        for type_name, count in type_counts.items():
            print(f"      - {type_name}: {count}")
        
        return True
    except Exception as e:
        print(f"   ❌ Element detection failed: {e}")
        return False


def test_engine():
    """Test the main engine."""
    print("\n🚀 Testing Desktop Visual Engine...")
    
    try:
        from mcp_desktop_visual.engine import DesktopVisualEngine
        
        with DesktopVisualEngine() as engine:
            # Get state
            state = engine.get_state()
            print(f"   ✅ Initial state: {len(state.elements)} elements, {len(state.windows)} windows")
            
            # Get summary
            summary = engine.get_state_summary()
            print(f"   ✅ Summary: {summary['total_elements']} cached elements")
            
            # Get stats
            stats = engine.get_stats()
            print(f"   ✅ OCR available: {stats['ocr_available']}")
        
        return True
    except Exception as e:
        print(f"   ❌ Engine test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("🖥️  MCP Desktop Visual - Test Suite")
    print("=" * 50)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Screen Capture", test_screen_capture()))
    results.append(("OCR", test_ocr()))
    results.append(("Windows", test_windows()))
    results.append(("Element Detection", test_element_detection()))
    results.append(("Engine", test_engine()))
    
    print("\n" + "=" * 50)
    print("📊 Test Results")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    
    if all_passed:
        print("🎉 All tests passed! MCP Desktop Visual is ready to use.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
