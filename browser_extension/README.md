# Universal MCP Browser Extension (Unpacked)

Esta extensão é um **bridge local** (MV3) que conecta o navegador ao seu servidor via **WebSocket**.

## Como carregar (Chrome/Edge)

1. Abra `chrome://extensions` (ou `edge://extensions`)
2. Ative **Developer mode**
3. Clique em **Load unpacked**
4. Selecione a pasta `browser_extension/` deste repositório

## Como funciona

- A extensão abre um WebSocket para `ws://127.0.0.1:8765` (configurável via `chrome.storage.local` chave `wsUrl`).
- O service worker recebe comandos e encaminha para a **aba ativa** via `chrome.tabs.sendMessage`.
- O content script executa ações simples no DOM (navigate/click/type/query/get_state) e responde.

### Métodos suportados

- `get_state` → {title,url,readyState}
- `list_tabs` → lista abas abertas ({id,title,url,active,windowId,index,pinned})
- `activate_tab` → ativa uma aba pelo `tabId`
- `screen_state` → resumo de textos/botões/inputs visíveis + selectors

`screen_state` foi pensado para ser um resumo (não é árvore DOM). Ele retorna listas deduplicadas e aceita opções como `limit`, `include_texts`, `include_buttons`, `include_inputs`.

Para lidar com hierarquia (ex: texto dentro de div clicável), itens podem incluir:
- `inner_selector` (quando o alvo clicável é um ancestral)
- `hierarchy` (breadcrumbs simples com tag/role/label)
- `navigate` → navega pra URL
- `click` → clica por CSS selector
- `type` → digita em input/textarea por CSS selector
- `query` → extrai texto/value/rect por CSS selector

## Observações

- Não roda em páginas especiais (`chrome://`, Web Store, etc.).
- A automação aqui é por **CSS selector** (ex: `input[name=email]`).
