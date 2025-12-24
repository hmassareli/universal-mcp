# MCP Desktop Visual

> 🖥️ **Control and understand your Windows desktop through MCP**

A powerful MCP (Model Context Protocol) server that allows LLMs to see and interact with your Windows desktop. It captures the screen, detects UI elements (buttons, inputs, text), and provides tools for mouse and keyboard control.

## ✨ Features

- **Incremental Screen Capture**: Only processes regions that changed, dramatically reducing token usage
- **UI Element Detection**: Automatically detects buttons, inputs, text, checkboxes, and more
- **OCR Text Extraction**: Reads text from the screen using Tesseract OCR
- **Visual State Cache**: Maintains a "Virtual Desktop DOM" for efficient queries
- **Mouse Control**: Click, double-click, right-click, drag, scroll, hover
- **Keyboard Control**: Type text (including Unicode), press keys, hotkeys
- **Window Management**: List, find, and track windows

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10+** - [Download](https://www.python.org/downloads/)
2. **Tesseract OCR** (optional, for text recognition) - [Download for Windows](https://github.com/UB-Mannheim/tesseract/wiki)

### Installation

Run the automated setup script:

```powershell
# Clone or download the project
cd universal-mcp

# Run setup (creates venv, installs dependencies, configures VS Code)
.\setup.ps1
```

This will:
- Create a virtual environment (`.venv`)
- Install all dependencies
- Check/install Tesseract OCR
- Create VS Code configuration (`.vscode/mcp.json`)
- Create default config (`mcp-desktop-config.json`)

### Manual Installation (Alternative)

If you prefer manual setup:

```powershell
# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -e .
```

### Configure VS Code

The setup script creates `.vscode/mcp.json` automatically. If you did manual installation, create it manually:

```json
{
  "servers": {
    "desktop-visual": {
      "command": "C:/path/to/universal-mcp/.venv/Scripts/python.exe",
      "args": ["-m", "mcp_desktop_visual.server"]
    }
  }
}
```

Or add to your global VS Code `settings.json`:

```json
{
  "mcp": {
    "servers": {
      "desktop-visual": {
        "command": "python",
        "args": ["-m", "mcp_desktop_visual.server"],
        "cwd": "C:/path/to/universal-mcp"
      }
    }
  }
}
```

## 📚 Available Tools

### Screen State Tools

| Tool                  | Description                                       |
| --------------------- | ------------------------------------------------- |
| `screen_capture`      | Capture screen and get changes since last capture |
| `screen_state`        | Get current cached screen state (all elements)    |
| `screen_query`        | Query elements by label, type, or window          |
| `find_element`        | Find a specific element by ID or label            |
| `element_at_position` | Get element at specific coordinates               |

### Mouse Tools

| Tool             | Description                                         |
| ---------------- | --------------------------------------------------- |
| `mouse_click`    | Click on target (element ID, label, or coordinates) |
| `mouse_move`     | Move mouse to target                                |
| `mouse_drag`     | Drag from one position to another                   |
| `mouse_scroll`   | Scroll up/down at position                          |
| `mouse_position` | Get current cursor position                         |

### Keyboard Tools

| Tool               | Description                          |
| ------------------ | ------------------------------------ |
| `keyboard_type`    | Type text at current position        |
| `keyboard_type_in` | Click element and type text          |
| `keyboard_press`   | Press a single key                   |
| `keyboard_hotkey`  | Press key combination (e.g., Ctrl+C) |

### Window Tools

| Tool            | Description              |
| --------------- | ------------------------ |
| `window_list`   | List all visible windows |
| `window_find`   | Find window by title     |
| `window_active` | Get active window info   |
| `window_activate` | Activate window by title |

### Utility Tools

| Tool               | Description                |
| ------------------ | -------------------------- |
| `wait_for_element` | Wait for element to appear |
| `wait_for_change`  | Wait for any screen change |
| `engine_stats`     | Get engine statistics      |

## 🎯 Usage Examples

### Example: Click a Button

```json
// Find and click a button by label
{ "tool": "mouse_click", "target": "Save" }

// Or by coordinates
{ "tool": "mouse_click", "target": [500, 300] }
```

### Example: Fill a Form

```json
// Type in an input field
{ "tool": "keyboard_type_in", "target": "Username", "text": "myuser" }

// Press Tab to move to next field
{ "tool": "keyboard_press", "key": "tab" }

// Type password
{ "tool": "keyboard_type", "text": "mypassword" }

// Click submit
{ "tool": "mouse_click", "target": "Submit" }
```

### Example: Use Keyboard Shortcuts

```json
// Copy (Ctrl+C)
{ "tool": "keyboard_hotkey", "keys": ["ctrl", "c"] }

// Save (Ctrl+S)
{ "tool": "keyboard_hotkey", "keys": ["ctrl", "s"] }

// Close window (Alt+F4)
{ "tool": "keyboard_hotkey", "keys": ["alt", "f4"] }
```

### Example: Window Management

```json
// List all windows
{ "tool": "window_list" }

// Find a specific window
{ "tool": "window_find", "title": "Chrome" }

// Activate a window
{ "tool": "window_activate", "title": "VS Code" }

// Get active window info
{ "tool": "window_active" }
```

### Example: Query Screen State

```json
// Get all buttons
{ "tool": "screen_query", "element_type": "button" }

// Find elements by text
{ "tool": "screen_query", "label": "Settings" }

// Get incremental changes
{ "tool": "screen_capture" }
```

## 📁 Examples

The `examples/` folder contains sample scripts demonstrating common use cases:

- **`basic_usage.py`** - Basic screen capture and element detection
- **`form_filling.py`** - Automated form filling with keyboard input
- **`screen_monitoring.py`** - Continuous screen monitoring and change detection

Run an example:

```powershell
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Run basic usage example
python examples/basic_usage.py
```

## ⚙️ Configuration

Create `mcp-desktop-config.json` in your project or home directory:

```json
{
  "capture": {
    "diff_threshold": 30,
    "min_region_area": 100,
    "capture_interval": 0.5
  },
  "ocr": {
    "tesseract_path": "C:/Program Files/Tesseract-OCR/tesseract.exe",
    "language": "eng",
    "confidence_threshold": 60
  },
  "input": {
    "click_delay": 0.1,
    "typing_delay": 0.02,
    "failsafe": true
  },
  "cache": {
    "max_elements": 1000,
    "max_history": 10
  }
}
```

## 🔧 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Server (stdio)                       │
├─────────────────────────────────────────────────────────────┤
│                    Desktop Visual Engine                     │
├─────────────┬──────────────┬──────────────┬────────────────┤
│   Screen    │   Element    │    Input     │   Visual State │
│   Capture   │   Detector   │  Controller  │     Cache      │
│ (MSS/OpenCV)│  (OCR/CV)    │ (PyAutoGUI)  │ (Virtual DOM)  │
└─────────────┴──────────────┴──────────────┴────────────────┘
```

### Incremental Processing Flow

1. **Capture**: Take screenshot
2. **Diff**: Compare with previous frame, find changed regions
3. **Detect**: Run OCR/element detection only on changed regions
4. **Cache**: Update the virtual DOM with new elements
5. **Return**: Send JSON diff to LLM (only what changed!)

This approach typically reduces processing by 80-95% compared to full-screen analysis every time.

## 🧪 Testing

Run the test suite:

```powershell
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Or run specific test files
python test_mcp.py

\> Nota: a integração via Chrome DevTools Protocol (CDP) foi removida. Para automação dentro do navegador, use a extensão em `browser_extension/`.
```

## 🐛 Troubleshooting

### Tesseract Not Found

If OCR isn't working, make sure Tesseract is installed and accessible:

```powershell
# Test Tesseract
tesseract --version

# Or specify path in config
{
  "ocr": {
    "tesseract_path": "C:/Program Files/Tesseract-OCR/tesseract.exe"
  }
}
```

### Permission Issues

On some systems, you may need to run VS Code as administrator for input control to work properly.

### Screen Capture Issues

Make sure no screen recording or DRM protection is active, as these can block screen capture.

## 📝 License

MIT License - See [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
