const DEFAULT_WS_URL = "ws://127.0.0.1:8765";

let ws = null;
let wsUrl = DEFAULT_WS_URL;
let reconnectTimer = null;

function log(...args) {
  // eslint-disable-next-line no-console
  console.log("[universal-mcp-bridge]", ...args);
}

async function getActiveTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs && tabs.length ? tabs[0] : null;
}

async function sendToActiveTab(message) {
  const tab = await getActiveTab();
  if (!tab || typeof tab.id !== "number") {
    return { ok: false, error: "No active tab" };
  }

  try {
    const result = await chrome.tabs.sendMessage(tab.id, message);
    return { ok: true, result };
  } catch (e) {
    // Most common when content script can't run (chrome://, extension pages, etc.)
    return { ok: false, error: String(e && e.message ? e.message : e) };
  }
}

async function listTabs(params = {}) {
  const currentWindow = params && params.currentWindow !== false;
  const queryInfo = currentWindow ? { currentWindow: true } : {};

  const tabs = await chrome.tabs.query(queryInfo);
  const result = (tabs || []).map((t) => ({
    id: t.id,
    windowId: t.windowId,
    index: t.index,
    active: !!t.active,
    pinned: !!t.pinned,
    title: t.title,
    url: t.url,
  }));

  return { ok: true, result: { tabs: result } };
}

async function activateTab(params = {}) {
  const tabId = params && params.tabId;
  if (typeof tabId !== "number") {
    return { ok: false, error: "Missing params.tabId (number)" };
  }

  const tab = await chrome.tabs.get(tabId);
  if (!tab) return { ok: false, error: "Tab not found" };

  if (typeof tab.windowId === "number") {
    try {
      await chrome.windows.update(tab.windowId, { focused: true });
    } catch {
      // ignore
    }
  }

  await chrome.tabs.update(tabId, { active: true });
  return { ok: true, result: { activated: true, tabId } };
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, 1500);
}

function connect() {
  try {
    if (ws) {
      ws.close();
      ws = null;
    }

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      log("WS connected", wsUrl);
      ws.send(
        JSON.stringify({
          type: "hello",
          name: "universal-mcp-browser-bridge",
          version: "0.1.0",
          userAgent: navigator.userAgent,
        })
      );
    };

    ws.onclose = () => {
      log("WS closed; reconnecting...");
      scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will schedule reconnect
    };

    ws.onmessage = async (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }

      if (!msg || !msg.id || !msg.method) return;

      const response = {
        id: msg.id,
        type: "response",
        ok: false,
      };

      let tabResult;
      if (msg.method === "list_tabs") {
        try {
          tabResult = await listTabs(msg.params || {});
        } catch (e) {
          tabResult = { ok: false, error: String(e && e.message ? e.message : e) };
        }
      } else if (msg.method === "activate_tab") {
        try {
          tabResult = await activateTab(msg.params || {});
        } catch (e) {
          tabResult = { ok: false, error: String(e && e.message ? e.message : e) };
        }
      } else {
        tabResult = await sendToActiveTab({
          type: "browser_command",
          method: msg.method,
          params: msg.params || {},
        });
      }

      response.ok = tabResult.ok;
      if (tabResult.ok) response.result = tabResult.result;
      else response.error = tabResult.error;

      try {
        ws.send(JSON.stringify(response));
      } catch {
        // ignore
      }
    };
  } catch (e) {
    log("WS connect failed", e);
    scheduleReconnect();
  }
}

chrome.runtime.onInstalled.addListener(() => {
  connect();
});

chrome.runtime.onStartup.addListener(() => {
  connect();
});

// Simple settings hook (optional)
chrome.storage.local.get(["wsUrl"]).then((res) => {
  if (res && typeof res.wsUrl === "string" && res.wsUrl.trim()) {
    wsUrl = res.wsUrl.trim();
  }
  connect();
});
