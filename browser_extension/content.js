function ok(result) {
  return { ok: true, result };
}

function err(error) {
  return { ok: false, error: String(error) };
}

function getElement(selector) {
  if (!selector || typeof selector !== "string") return null;
  return document.querySelector(selector);
}

function isVisible(el) {
  if (!el) return false;
  const rects = el.getClientRects();
  if (!rects || rects.length === 0) return false;
  const style = window.getComputedStyle(el);
  if (!style) return true;
  if (style.visibility === "hidden" || style.display === "none") return false;
  if (Number(style.opacity) === 0) return false;
  const rect = el.getBoundingClientRect();
  if (rect.width < 2 || rect.height < 2) return false;
  return true;
}

function cssEscape(value) {
  // Minimal escape; good enough for common ids/names.
  return String(value).replace(/([ #;?%&,.+*~\':!^$\[\]()=>|\/\\])/g, "\\$1");
}

function uniqueSelectorFor(el) {
  if (!(el instanceof Element)) return null;

  // Prefer id
  const id = el.getAttribute("id");
  if (id) {
    const sel = `#${cssEscape(id)}`;
    if (document.querySelectorAll(sel).length === 1) return sel;
  }

  // Prefer data-testid
  const testId = el.getAttribute("data-testid");
  if (testId) {
    const sel = `[data-testid=\"${cssEscape(testId)}\"]`;
    if (document.querySelectorAll(sel).length === 1) return sel;
  }

  // Prefer name for inputs
  const name = el.getAttribute("name");
  if (name) {
    const tag = el.tagName.toLowerCase();
    const sel = `${tag}[name=\"${cssEscape(name)}\"]`;
    if (document.querySelectorAll(sel).length === 1) return sel;
  }

  // Prefer aria-label
  const aria = el.getAttribute("aria-label");
  if (aria) {
    const tag = el.tagName.toLowerCase();
    const sel = `${tag}[aria-label=\"${cssEscape(aria)}\"]`;
    if (document.querySelectorAll(sel).length === 1) return sel;
  }

  // Prefer placeholder
  const placeholder = el.getAttribute("placeholder");
  if (placeholder) {
    const tag = el.tagName.toLowerCase();
    const sel = `${tag}[placeholder=\"${cssEscape(placeholder)}\"]`;
    if (document.querySelectorAll(sel).length === 1) return sel;
  }

  // Fallback: short path
  const parts = [];
  let cur = el;
  for (let i = 0; i < 5 && cur && cur.nodeType === 1; i++) {
    const tag = cur.tagName.toLowerCase();
    let part = tag;
    const cls = (cur.getAttribute("class") || "").trim();
    if (cls) {
      const first = cls.split(/\s+/)[0];
      if (first) part += `.${cssEscape(first)}`;
    }
    const parent = cur.parentElement;
    if (parent) {
      const siblings = Array.from(parent.children).filter((c) => c.tagName === cur.tagName);
      if (siblings.length > 1) {
        const idx = siblings.indexOf(cur) + 1;
        part += `:nth-of-type(${idx})`;
      }
    }
    parts.unshift(part);
    const sel = parts.join(" > ");
    if (document.querySelectorAll(sel).length === 1) return sel;
    cur = parent;
  }
  return parts.join(" > ") || null;
}

function elementLabel(el) {
  if (!el) return "";
  const aria = (el.getAttribute("aria-label") || "").trim();
  if (aria) return aria;

  const placeholder = (el.getAttribute("placeholder") || "").trim();
  if (placeholder) return placeholder;

  const title = (el.getAttribute("title") || "").trim();
  if (title) return title;

  const txt = (el.innerText || el.textContent || "").trim();
  return txt.replace(/\s+/g, " ").slice(0, 160);
}

function isClickable(el) {
  if (!(el instanceof Element)) return false;
  const tag = el.tagName.toLowerCase();
  if (tag === "button") return true;
  if (tag === "a" && el.hasAttribute("href")) return true;
  if (tag === "input") {
    const t = (el.getAttribute("type") || "").toLowerCase();
    return t === "button" || t === "submit";
  }
  const role = (el.getAttribute("role") || "").toLowerCase();
  return role === "button";
}

function closestClickable(el) {
  let cur = el;
  for (let i = 0; i < 8 && cur && cur.nodeType === 1; i++) {
    if (isClickable(cur)) return cur;
    cur = cur.parentElement;
  }
  return null;
}

function ancestorBreadcrumbs(el, depth = 3) {
  const crumbs = [];
  let cur = el;
  for (let i = 0; i < depth && cur && cur.nodeType === 1; i++) {
    const tag = cur.tagName.toLowerCase();
    const label = elementLabel(cur);
    const role = (cur.getAttribute("role") || "").toLowerCase() || undefined;
    crumbs.push({ tag, role, label });
    cur = cur.parentElement;
  }
  return crumbs;
}

function collectDomScreenState(options = {}) {
  const limit = typeof options.limit === "number" ? options.limit : 200;
  const includeTexts = options.include_texts !== false; // default true for backwards compat
  const includeButtons = options.include_buttons !== false;
  const includeInputs = options.include_inputs !== false;
  const maxTextLen = typeof options.max_text_length === "number" ? options.max_text_length : 200;
  const includeHierarchy = options.include_hierarchy !== false;
  const hierarchyDepth = typeof options.hierarchy_depth === "number" ? options.hierarchy_depth : 3;

  const result = {
    title: document.title,
    url: location.href,
    readyState: document.readyState,
    texts: [],
    buttons: [],
    inputs: [],
  };

  if (includeTexts) {
    // Visible texts (keep it simple to avoid huge payload)
    const textNodes = Array.from(document.querySelectorAll("h1,h2,h3,p,li,span"));
    for (const el of textNodes) {
      if (!isVisible(el)) continue;
      const t = (el.innerText || "").trim().replace(/\s+/g, " ");
      if (!t || t.length < 3) continue;
      result.texts.push(t.slice(0, maxTextLen));
      if (limit > 0 && result.texts.length >= Math.min(limit, 200)) break;
    }
  }

  if (includeButtons) {
    const buttonCandidates = Array.from(
      document.querySelectorAll("button, a[href], [role='button'], input[type='button'], input[type='submit']")
    );
    for (const el of buttonCandidates) {
      if (!isVisible(el)) continue;
      const label = elementLabel(el);
      if (!label) continue;
      const actionEl = closestClickable(el) || el;
      const selector = uniqueSelectorFor(actionEl);
      if (!selector) continue;
      const item = { label, selector };

      // If element itself isn't the clickable target, expose the inner selector too
      const innerSelector = uniqueSelectorFor(el);
      if (innerSelector && innerSelector !== selector) item.inner_selector = innerSelector;

      if (includeHierarchy) item.hierarchy = ancestorBreadcrumbs(el, hierarchyDepth);
      result.buttons.push(item);
      if (limit > 0 && result.buttons.length >= limit) break;
    }
  }

  if (includeInputs) {
    const inputCandidates = Array.from(document.querySelectorAll("input, textarea, select"));
    for (const el of inputCandidates) {
      if (!isVisible(el)) continue;
      const tag = el.tagName.toLowerCase();
      const type = tag === "input" ? (el.getAttribute("type") || "text") : tag;
      const label = elementLabel(el);
      const selector = uniqueSelectorFor(el);
      if (!selector) continue;
      const item = { label, selector, type };
      if (includeHierarchy) item.hierarchy = ancestorBreadcrumbs(el, hierarchyDepth);
      result.inputs.push(item);
      if (limit > 0 && result.inputs.length >= limit) break;
    }
  }

  // Dedupe texts/buttons/inputs a bit
  result.texts = Array.from(new Set(result.texts)).slice(0, 200);
  {
    const seen = new Set();
    result.buttons = result.buttons.filter((b) => {
      const key = `${b.label}@@${b.selector}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }
  {
    const seen = new Set();
    result.inputs = result.inputs.filter((i) => {
      const key = `${i.label}@@${i.selector}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  return result;
}

async function handleCommand(method, params) {
  switch (method) {
    case "get_state":
      return ok({
        title: document.title,
        url: location.href,
        readyState: document.readyState,
      });

    case "screen_state": {
      const options = params && typeof params === "object" ? params : {};
      return ok(collectDomScreenState(options));
    }

    case "navigate": {
      const url = params && params.url;
      if (!url || typeof url !== "string") return err("Missing params.url");
      location.href = url;
      return ok({ navigated: true, url });
    }

    case "click": {
      const selector = params && params.selector;
      const el = getElement(selector);
      if (!el) return err(`Element not found for selector: ${selector}`);
      el.scrollIntoView({ block: "center", inline: "center" });
      el.click();
      return ok({ clicked: true, selector });
    }

    case "type": {
      const selector = params && params.selector;
      const text = params && params.text;
      const clear = !!(params && params.clear);
      const el = getElement(selector);
      if (!el) return err(`Element not found for selector: ${selector}`);
      if (typeof el.focus === "function") el.focus();

      // Inputs/textareas: set value and dispatch events
      if ("value" in el) {
        if (clear) el.value = "";
        el.value = (el.value || "") + (typeof text === "string" ? text : "");
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
        return ok({ typed: true, selector });
      }

      // Fallback: try setting textContent
      if (clear) el.textContent = "";
      el.textContent = (el.textContent || "") + (typeof text === "string" ? text : "");
      return ok({ typed: true, selector });
    }

    case "query": {
      const selector = params && params.selector;
      const el = getElement(selector);
      if (!el) return err(`Element not found for selector: ${selector}`);
      const rect = el.getBoundingClientRect();
      return ok({
        selector,
        text: (el.innerText || el.textContent || "").trim().slice(0, 2000),
        value: "value" in el ? el.value : undefined,
        rect: {
          x: rect.x,
          y: rect.y,
          width: rect.width,
          height: rect.height,
        },
      });
    }

    default:
      return err(`Unknown method: ${method}`);
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || message.type !== "browser_command") return;

  handleCommand(message.method, message.params)
    .then((result) => sendResponse(result))
    .catch((e) => sendResponse(err(e)));

  return true; // async
});
