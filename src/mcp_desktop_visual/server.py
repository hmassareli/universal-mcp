"""
MCP Desktop Visual Server

Main MCP server implementation that exposes desktop visual tools.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

from .engine import DesktopVisualEngine, get_engine, start_engine
from .models import ElementType, UIElement, ScreenState, VisualDiff


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("mcp-desktop-visual")


# ==================== System Prompt ====================

SYSTEM_PROMPT = """
# MCP Desktop Visual - Guia de Uso

Você tem acesso a ferramentas para ver e interagir com a tela do computador do usuário.

## Fluxo Básico
1. Use `screen_capture` para ver o que está na tela
2. Identifique o elemento desejado pelo texto/label
3. Use `mouse_click(target="texto do botão")` para clicar
4. Use `keyboard_type(text="...")` para digitar
5. Repita conforme necessário

## Ferramentas Principais

### Visualização
- `screen_capture` - Captura e analisa a tela. Retorna textos visíveis, botões, links, campos. (Tente usar entre ações quando necessário para se atualizar)
- `screen_state` - Retorna o estado atual sem recapturar.
- `wait_for_change` - Aguarda mudanças na tela (útil após clicar).

### Cliques
- `mouse_click(target="texto")` - Clica em elemento pelo texto/label.
- `mouse_click(target=[x, y])` - Clica em coordenada específica (raro).
- Para botões duplicados, use o #id mostrado: `mouse_click(target="elem_a1b2")`

### Teclado
- `keyboard_type(text="...")` - Digita texto.
- `keyboard_press(key="enter")` - Pressiona tecla (enter, tab, escape, etc).
- `keyboard_hotkey(keys=["ctrl", "c"])` - Atalhos como Ctrl+C.

### Digitação em Campos
- `keyboard_type_in(target="nome do campo", text="valor")` - Clica no campo e digita.

## Dicas
- Sempre faça `screen_capture` primeiro para entender a tela.
- Após clicar, use `wait_for_change` para esperar a resposta.
- Se não achar um elemento, pode ser que precisa rolar: `mouse_scroll(clicks=-3)`.
- Use `keyboard_hotkey(keys=["win"])` para abrir o menu iniciar.
- Use `keyboard_hotkey(keys=["alt", "tab"])` para trocar janelas.

## Exemplo: Abrir Chrome e navegar
1. `keyboard_hotkey(keys=["win"])` - Abre menu iniciar
2. `keyboard_type(text="chrome")` - Pesquisa Chrome
3. `keyboard_press(key="enter")` - Abre Chrome
4. `wait_for_change(timeout=3)` - Aguarda abrir
5. `keyboard_type(text="google.com")` - Digita URL
6. `keyboard_press(key="enter")` - Navega
"""


# Create the MCP server
app = Server("desktop-visual")

# Global engine instance
_engine: Optional[DesktopVisualEngine] = None


def get_or_start_engine() -> DesktopVisualEngine:
    """Get or start the desktop visual engine."""
    global _engine
    if _engine is None:
        _engine = DesktopVisualEngine()
        _engine.start()
        logger.info("Desktop Visual Engine started")
    return _engine


# ==================== Simplification Layer ====================

def _simplify_element(elem: UIElement) -> dict:
    """Simplify a UI element for LLM consumption."""
    result = {"id": elem.id, "type": elem.type.value}
    
    # Only include text/label if present
    if elem.text:
        result["text"] = elem.text
    elif elem.label:
        result["text"] = elem.label
    
    return result


def _simplify_screen_state(state: ScreenState) -> dict:
    """
    Simplify screen state for LLM consumption.
    
    Returns a clean, readable summary with only actionable information.
    Filters out noise and groups related text.
    """
    # Track text lines by Y position (group nearby text into lines)
    text_lines: dict[int, list[tuple[int, str]]] = {}  # y_bucket -> [(x, text), ...]
    buttons = []
    inputs = []
    
    label_counts = {}
    y_bucket_size = 30  # Group text within 30px vertically
    
    for elem in state.elements:
        text_content = (elem.text or elem.label or "").strip()
        
        # Skip very short or noisy text
        if not text_content or len(text_content) < 2:
            continue
        
        # Skip common UI noise patterns
        if text_content in {"", "-", "|", ".", "...", "●", "•", "○", "□", "■"}:
            continue
        
        if elem.type.value == "text":
            # Group text by Y position to form lines
            y_bucket = elem.bounds.y // y_bucket_size
            if y_bucket not in text_lines:
                text_lines[y_bucket] = []
            text_lines[y_bucket].append((elem.bounds.x, text_content))
        
        elif elem.type.value == "button" and len(text_content) >= 2:
            label_counts[text_content] = label_counts.get(text_content, 0) + 1
            buttons.append({"label": text_content, "id": elem.id})
        
        elif elem.type.value == "input":
            short_id = elem.id.split("_")[1][:4] if "_" in elem.id else elem.id[:4]
            inputs.append({
                "id": short_id,
                "conteudo": text_content if text_content else "(vazio)"
            })
    
    # Build text output - join nearby text into lines
    result = {"janela_ativa": state.active_window}
    
    if text_lines:
        # Sort lines by Y, then sort words in each line by X
        sorted_buckets = sorted(text_lines.keys())
        lines = []
        for bucket in sorted_buckets[:40]:  # Limit lines
            words = text_lines[bucket]
            words.sort(key=lambda w: w[0])  # Sort by X
            line = " ".join(w[1] for w in words)
            if len(line) > 3:  # Skip very short lines
                lines.append(line)
        
        if lines:
            # Join lines with newline for readability
            result["texto_na_tela"] = "\n".join(lines[:30])
    
    # Buttons - only with useful labels, show ID for duplicates
    if buttons:
        simplified_buttons = []
        seen_labels = set()
        for btn in buttons:
            if btn["label"] in seen_labels:
                continue
            seen_labels.add(btn["label"])
            
            if label_counts.get(btn["label"], 0) > 1:
                short_id = btn["id"].split("_")[1][:4] if "_" in btn["id"] else btn["id"][:4]
                simplified_buttons.append(f"{btn['label']} (#{short_id})")
            else:
                simplified_buttons.append(btn["label"])
        
        if simplified_buttons:
            result["botoes"] = simplified_buttons[:15]
    
    if inputs:
        result["campos"] = inputs[:8]
    
    result["total_elementos"] = len(state.elements)
    result["dica"] = "Use mouse_click(target='texto') para clicar"
    
    return result


def _simplify_diff(diff: VisualDiff) -> dict:
    """
    Simplify visual diff for LLM consumption.
    
    Returns only what actually changed in a readable format.
    """
    if not diff.has_changes:
        return {"mudou": False}
    
    # Collect meaningful changes (only elements with text)
    novos_textos = []
    novos_botoes = []
    removidos = []
    
    for region in diff.changed_regions:
        for elem in region.added_elements:
            text = (elem.text or elem.label or "").strip()
            if text and len(text) >= 2:
                if elem.type.value == "text":
                    novos_textos.append(text)
                elif elem.type.value == "button":
                    novos_botoes.append(text)
        
        for elem in region.removed_elements:
            text = (elem.text or elem.label or "").strip()
            if text and len(text) >= 2:
                removidos.append(text)
    
    result = {"mudou": True}
    
    if novos_textos:
        result["novos_textos"] = list(dict.fromkeys(novos_textos))[:15]
    if novos_botoes:
        result["novos_botoes"] = list(dict.fromkeys(novos_botoes))[:10]
    if removidos:
        result["removidos"] = list(dict.fromkeys(removidos))[:10]
    
    return result


def _check_ocr_status(engine: DesktopVisualEngine) -> dict:
    """Check OCR engine status."""
    ocr = engine._ocr
    return {
        "tesseract_available": ocr.is_available,
        "tesseract_path": ocr._tesseract_path,
        "language": ocr.config.language,
        "preprocessing": ocr.config.preprocessing,
    }


# ==================== Tool Definitions ====================

TOOLS = [
    # Screen State Tools
    Tool(
        name="screen_capture",
        description="""Capture and analyze the screen, returning what changed since the last capture.
        
Returns a diff with:
- changed_regions: Areas that changed
- added/removed/modified elements
- summary statistics

Use force_full=true to do a complete re-analysis.""",
        inputSchema={
            "type": "object",
            "properties": {
                "force_full": {
                    "type": "boolean",
                    "description": "Force a full screen analysis instead of incremental",
                    "default": False,
                },
            },
        },
    ),
    Tool(
        name="screen_state",
        description="""Get the current cached screen state.
        
Returns:
- All detected elements (buttons, inputs, text, etc.)
- All windows
- Active window
- Screen size

Use this instead of screen_capture when you just need to query the current state without recapturing.""",
        inputSchema={
            "type": "object",
            "properties": {
                "summary_only": {
                    "type": "boolean",
                    "description": "Return only a summary instead of full element list",
                    "default": False,
                },
            },
        },
    ),
    Tool(
        name="screen_query",
        description="""Query elements on screen with filters.
        
Can filter by:
- label: Text/label of the element (partial match)
- element_type: button, input, text, checkbox, etc.
- window_title: Filter by containing window

Returns matching elements with their positions.""",
        inputSchema={
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Filter by element label (partial match)",
                },
                "element_type": {
                    "type": "string",
                    "description": "Filter by element type",
                    "enum": ["button", "text", "input", "checkbox", "radio", "link", "icon", "image", "window", "menu", "menu_item", "tab", "list_item", "dropdown"],
                },
                "window_title": {
                    "type": "string",
                    "description": "Filter by window title (partial match)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return",
                    "default": 20,
                },
            },
        },
    ),
    Tool(
        name="find_element",
        description="""Find a specific element by ID or label.
        
Returns the element if found with its:
- id, type, bounds (position and size)
- label, text content
- confidence score
- center position for clicking""",
        inputSchema={
            "type": "object",
            "properties": {
                "element_id": {
                    "type": "string",
                    "description": "The element ID to find",
                },
                "label": {
                    "type": "string",
                    "description": "The label/text to search for (fuzzy match)",
                },
            },
        },
    ),
    Tool(
        name="element_at_position",
        description="""Get the element at a specific screen position.
        
Returns the smallest (most specific) element containing that position.""",
        inputSchema={
            "type": "object",
            "properties": {
                "x": {
                    "type": "integer",
                    "description": "X coordinate",
                },
                "y": {
                    "type": "integer",
                    "description": "Y coordinate",
                },
            },
            "required": ["x", "y"],
        },
    ),
    
    # Mouse Tools
    Tool(
        name="mouse_click",
        description="""Click on a target.
        
Target can be:
- Element ID (e.g., "elem_abc123")
- Element label/text (e.g., "Save", "OK", "Submit")
- Coordinates as [x, y]

Returns success status and final click position.""",
        inputSchema={
            "type": "object",
            "properties": {
                "target": {
                    "oneOf": [
                        {"type": "string", "description": "Element ID or label"},
                        {
                            "type": "array",
                            "items": {"type": "integer"},
                            "minItems": 2,
                            "maxItems": 2,
                            "description": "Coordinates [x, y]",
                        },
                    ],
                    "description": "Target to click on",
                },
                "button": {
                    "type": "string",
                    "enum": ["left", "right", "middle"],
                    "default": "left",
                },
                "double_click": {
                    "type": "boolean",
                    "default": False,
                },
            },
            "required": ["target"],
        },
    ),
    Tool(
        name="mouse_move",
        description="""Move the mouse to a target without clicking.
        
Target can be element ID, label, or [x, y] coordinates.""",
        inputSchema={
            "type": "object",
            "properties": {
                "target": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                    ],
                },
            },
            "required": ["target"],
        },
    ),
    Tool(
        name="mouse_drag",
        description="""Drag from one position to another.
        
Both start and end can be element IDs, labels, or [x, y] coordinates.""",
        inputSchema={
            "type": "object",
            "properties": {
                "start": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                    ],
                },
                "end": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                    ],
                },
            },
            "required": ["start", "end"],
        },
    ),
    Tool(
        name="mouse_scroll",
        description="""Scroll the mouse wheel.
        
clicks: Positive = scroll up, Negative = scroll down
target: Optional position to scroll at""",
        inputSchema={
            "type": "object",
            "properties": {
                "clicks": {
                    "type": "integer",
                    "description": "Number of scroll clicks (positive=up, negative=down)",
                },
                "target": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                    ],
                    "description": "Optional target to scroll at",
                },
            },
            "required": ["clicks"],
        },
    ),
    Tool(
        name="mouse_position",
        description="Get the current mouse cursor position.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    
    # Keyboard Tools
    Tool(
        name="keyboard_type",
        description="""Type text at the current cursor position.
        
Supports Unicode characters. For special keys, use keyboard_press.""",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to type",
                },
            },
            "required": ["text"],
        },
    ),
    Tool(
        name="keyboard_type_in",
        description="""Click on a target element and type text.
        
First clicks the target to focus it, then types the text.
Use clear_first=true to select all and replace existing text.""",
        inputSchema={
            "type": "object",
            "properties": {
                "target": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                    ],
                    "description": "Element to type in (ID, label, or coordinates)",
                },
                "text": {
                    "type": "string",
                    "description": "Text to type",
                },
                "clear_first": {
                    "type": "boolean",
                    "description": "Clear existing text first (Ctrl+A)",
                    "default": False,
                },
            },
            "required": ["target", "text"],
        },
    ),
    Tool(
        name="keyboard_press",
        description="""Press a single key.
        
Key names: enter, tab, escape, space, backspace, delete,
up, down, left, right, home, end, pageup, pagedown,
f1-f12, a-z, 0-9, etc.""",
        inputSchema={
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Key name to press",
                },
            },
            "required": ["key"],
        },
    ),
    Tool(
        name="keyboard_hotkey",
        description="""Press a key combination.
        
Examples:
- ["ctrl", "c"] for Ctrl+C (copy)
- ["ctrl", "v"] for Ctrl+V (paste)
- ["alt", "f4"] for Alt+F4 (close window)
- ["ctrl", "shift", "s"] for Ctrl+Shift+S (save as)""",
        inputSchema={
            "type": "object",
            "properties": {
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keys to press together",
                },
            },
            "required": ["keys"],
        },
    ),
    
    # Window Tools
    Tool(
        name="window_list",
        description="Get a list of all visible windows with their titles and positions.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="window_find",
        description="""Find a window by title.
        
Returns window info including position, size, and active state.""",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Window title to search for (partial match)",
                },
            },
            "required": ["title"],
        },
    ),
    Tool(
        name="window_active",
        description="Get information about the currently active window.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="window_activate",
        description="""Activate (bring to foreground) a window by title.
        
Use this to switch to a specific window, like switching to Chrome or another app.
The title is a partial match - 'Chrome' will match 'Google - Google Chrome'.""",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Window title to activate (partial match). Examples: 'Chrome', 'Facebook', 'VS Code'",
                },
            },
            "required": ["title"],
        },
    ),
    
    # Utility Tools
    Tool(
        name="wait_for_element",
        description="""Wait for an element with a specific label to appear.
        
Continuously captures and searches until element is found or timeout.""",
        inputSchema={
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Label to wait for",
                },
                "timeout": {
                    "type": "number",
                    "description": "Maximum wait time in seconds",
                    "default": 10.0,
                },
            },
            "required": ["label"],
        },
    ),
    Tool(
        name="wait_for_change",
        description="""Wait for any visual change on screen.
        
Useful after clicking a button to wait for the result.""",
        inputSchema={
            "type": "object",
            "properties": {
                "timeout": {
                    "type": "number",
                    "description": "Maximum wait time in seconds",
                    "default": 10.0,
                },
            },
        },
    ),
    Tool(
        name="engine_stats",
        description="Get statistics about the desktop visual engine.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    
    # Browser Tab Tools
    Tool(
        name="chrome_start",
        description="""Start Chrome with debug port (--remote-debugging-port=9222).
        
This must be run first before using chrome_get_tabs or chrome_switch_tab.
Automatically kills existing Chrome instances and starts a fresh one with
proper profile syncing (cookies, passwords, etc.).""",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="chrome_get_tabs",
        description="""Get list of all open tabs in Chrome.
        
Requires Chrome to be running with --remote-debugging-port=9222.
Use chrome_start first to open Chrome correctly.
Returns list of tabs with their id, title, url, and active status.""",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="chrome_switch_tab",
        description="""Switch to a specific Chrome tab by its ID.
        
Use chrome_get_tabs first to get the list of available tabs and their IDs.""",
        inputSchema={
            "type": "object",
            "properties": {
                "tab_id": {
                    "type": "string",
                    "description": "The tab ID to switch to (from chrome_get_tabs)",
                },
            },
            "required": ["tab_id"],
        },
    ),
]


# ==================== MCP Prompts ====================

@app.list_prompts()
async def list_prompts():
    """List available prompts."""
    from mcp.types import Prompt
    return [
        Prompt(
            name="usage-guide",
            description="Guia de como usar o MCP Desktop Visual para automação de tela",
        )
    ]


@app.get_prompt()
async def get_prompt(name: str):
    """Get a specific prompt by name."""
    from mcp.types import GetPromptResult, PromptMessage, TextContent as PromptTextContent
    
    if name == "usage-guide":
        return GetPromptResult(
            description="Guia de uso do MCP Desktop Visual",
            messages=[
                PromptMessage(
                    role="user",
                    content=PromptTextContent(type="text", text=SYSTEM_PROMPT.strip()),
                )
            ],
        )
    
    raise ValueError(f"Prompt não encontrado: {name}")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        engine = get_or_start_engine()
        result = await _handle_tool(engine, name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        logger.exception(f"Error handling tool {name}")
        return [TextContent(
            type="text",
            text=json.dumps({"error": str(e), "tool": name}, indent=2),
        )]


async def _handle_tool(
    engine: DesktopVisualEngine,
    name: str,
    args: dict[str, Any]
) -> dict[str, Any]:
    """Handle individual tool calls."""
    
    # Screen State Tools
    if name == "screen_capture":
        force_full = args.get("force_full", False)
        diff = engine.capture_and_analyze(force_full=force_full)
        state = engine.get_state()
        
        # Merge diff info with screen state for a single clean output
        result = _simplify_screen_state(state)
        
        # Add provider info (CDP, UIA, or OCR)
        result["provider"] = engine._last_provider_name
        
        # Add change info
        diff_info = _simplify_diff(diff)
        result["mudou"] = diff_info.get("mudou", False)
        if diff_info.get("novos_textos"):
            result["novos_textos"] = diff_info["novos_textos"]
        if diff_info.get("novos_botoes"):
            result["novos_botoes"] = diff_info["novos_botoes"]
        if diff_info.get("removidos"):
            result["removidos"] = diff_info["removidos"]
        
        # Only show OCR status if using OCR and there's a problem
        if engine._last_provider_name == "OCR":
            ocr_status = _check_ocr_status(engine)
            if not ocr_status.get("tesseract_available"):
                result["aviso"] = "Tesseract OCR não disponível - textos não serão detectados"
        
        return result
    
    elif name == "screen_state":
        state = engine.get_state()
        result = _simplify_screen_state(state)
        
        # Only show OCR status if there's a problem
        ocr_status = _check_ocr_status(engine)
        if not ocr_status.get("tesseract_available"):
            result["aviso"] = "Tesseract OCR não disponível"
        
        return result
    
    elif name == "screen_query":
        elements = engine.query_elements(
            label=args.get("label"),
            element_type=args.get("element_type"),
            window_title=args.get("window_title"),
            limit=args.get("limit", 20),
        )
        # Simplified elements list
        return {
            "count": len(elements),
            "elements": [_simplify_element(e) for e in elements],
        }
    
    elif name == "find_element":
        elem = None
        if "element_id" in args:
            elem = engine.find_element_by_id(args["element_id"])
        elif "label" in args:
            elem = engine.find_element_by_label(args["label"])
        
        if elem:
            return {"found": True, "element": _simplify_element(elem)}
        else:
            return {"found": False, "element": None}
    
    elif name == "element_at_position":
        elem = engine.find_element_at(args["x"], args["y"])
        if elem:
            return {"found": True, "element": _simplify_element(elem)}
        else:
            return {"found": False, "element": None}
    
    # Mouse Tools
    elif name == "mouse_click":
        target = args["target"]
        if isinstance(target, list):
            target = tuple(target)
        
        button = args.get("button", "left")
        
        if args.get("double_click"):
            result = engine.double_click(target)
        elif button == "right":
            result = engine.right_click(target)
        else:
            result = engine.click(target, button=button)
        
        return result.to_dict()
    
    elif name == "mouse_move":
        target = args["target"]
        if isinstance(target, list):
            target = tuple(target)
        result = engine.move_to(target)
        return result.to_dict()
    
    elif name == "mouse_drag":
        start = args["start"]
        end = args["end"]
        if isinstance(start, list):
            start = tuple(start)
        if isinstance(end, list):
            end = tuple(end)
        result = engine.drag(start, end)
        return result.to_dict()
    
    elif name == "mouse_scroll":
        target = args.get("target")
        if isinstance(target, list):
            target = tuple(target)
        result = engine.scroll(args["clicks"], target)
        return result.to_dict()
    
    elif name == "mouse_position":
        pos = engine.get_mouse_position()
        return {"x": pos[0], "y": pos[1]}
    
    # Keyboard Tools
    elif name == "keyboard_type":
        result = engine.type_text(args["text"])
        return result.to_dict()
    
    elif name == "keyboard_type_in":
        target = args["target"]
        if isinstance(target, list):
            target = tuple(target)
        result = engine.type_in(
            target,
            args["text"],
            clear_first=args.get("clear_first", False),
        )
        return result.to_dict()
    
    elif name == "keyboard_press":
        result = engine.press_key(args["key"])
        return result.to_dict()
    
    elif name == "keyboard_hotkey":
        result = engine.hotkey(*args["keys"])
        return result.to_dict()
    
    # Window Tools
    elif name == "window_list":
        windows = engine.get_all_windows()
        return {
            "count": len(windows),
            "windows": [w.to_dict() for w in windows],
        }
    
    elif name == "window_find":
        cache = engine._cache
        window = cache.get_window_by_title(args["title"])
        if window:
            return {"found": True, "window": window.to_dict()}
        else:
            return {"found": False, "window": None}
    
    elif name == "window_active":
        window = engine.get_active_window()
        if window:
            return {"found": True, "window": window.to_dict()}
        else:
            return {"found": False, "window": None}
    
    elif name == "window_activate":
        from .windows import get_all_windows
        import ctypes
        import time
        import pyautogui
        
        title_search = args["title"].lower()
        windows = get_all_windows()
        
        # Find window by partial title match
        target_window = None
        for w in windows:
            if title_search in w.title.lower() and w.is_visible and not w.is_minimized:
                target_window = w
                break
        
        if target_window:
            user32 = ctypes.windll.user32
            hwnd = target_window.handle
            
            # Check if already active
            current_hwnd = user32.GetForegroundWindow()
            if current_hwnd == hwnd:
                return {
                    "success": True,
                    "window": target_window.to_dict(),
                    "message": "Window already active"
                }
            
            # The most reliable method: click on the window in the taskbar
            # Or use pygetwindow to activate
            try:
                import pygetwindow as gw
                windows_with_title = gw.getWindowsWithTitle(target_window.title)
                if windows_with_title:
                    windows_with_title[0].activate()
                    time.sleep(0.3)
                    
                    new_foreground = user32.GetForegroundWindow()
                    success = new_foreground == hwnd
                    
                    return {
                        "success": success,
                        "window": target_window.to_dict(),
                    }
            except Exception as e:
                pass
            
            # Fallback: Use shell COM to activate
            try:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys('%')  # Send Alt key
                time.sleep(0.05)
                user32.SetForegroundWindow(hwnd)
                time.sleep(0.3)
                
                new_foreground = user32.GetForegroundWindow()
                success = new_foreground == hwnd
                
                return {
                    "success": success,
                    "window": target_window.to_dict(),
                }
            except Exception as e:
                pass
            
            # Last resort: just report we tried
            return {
                "success": False,
                "window": target_window.to_dict(),
                "message": "Could not activate window - Windows restrictions"
            }
        else:
            available = [w.title for w in windows if w.is_visible and not w.is_minimized][:5]
            return {
                "success": False,
                "error": f"Window with '{args['title']}' not found",
                "available_windows": available,
            }
    
    # Utility Tools
    elif name == "wait_for_element":
        elem = engine.wait_for_element(
            args["label"],
            timeout=args.get("timeout", 10.0),
        )
        if elem:
            return {"found": True, "element": elem.to_dict()}
        else:
            return {"found": False, "timeout": True}
    
    elif name == "wait_for_change":
        changed = engine.wait_for_change(
            timeout=args.get("timeout", 10.0),
        )
        return {"changed": changed}
    
    elif name == "engine_stats":
        return engine.get_stats()
    
    elif name == "chrome_start":
        # Get the CDP provider from the engine
        cdp_provider = engine.registry.get_provider_for_process("chrome.exe", "", "")
        if cdp_provider:
            success = cdp_provider.start_chrome_with_debug()
            if success:
                return {"success": True, "message": "Chrome started with debug port 9222"}
            else:
                return {"success": False, "error": "Failed to start Chrome"}
        else:
            return {"success": False, "error": "CDP provider not available"}
    
    elif name == "chrome_get_tabs":
        # Get the CDP provider from the engine
        cdp_provider = engine.registry.get_provider_for_process("chrome.exe", "", "")
        if cdp_provider:
            tabs = cdp_provider.get_tabs()
            return {"success": True, "tabs": tabs, "count": len(tabs)}
        else:
            return {"success": False, "error": "CDP provider not available or Chrome not running"}
    
    elif name == "chrome_switch_tab":
        tab_id = args.get("tab_id")
        if not tab_id:
            return {"success": False, "error": "tab_id is required"}
        
        # Get the CDP provider from the engine
        cdp_provider = engine.registry.get_provider_for_process("chrome.exe", "", "")
        if cdp_provider:
            success = cdp_provider.switch_tab(tab_id)
            return {"success": success, "tab_id": tab_id}
        else:
            return {"success": False, "error": "CDP provider not available or Chrome not running"}
    
    else:
        return {"error": f"Unknown tool: {name}"}


async def run_server():
    """Run the MCP server."""
    logger.info("Starting MCP Desktop Visual Server...")
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def main():
    """Main entry point."""
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
