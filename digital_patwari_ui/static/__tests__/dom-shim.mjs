// Minimal fake DOM sufficient to exercise dom.js / i18n.js / evidence.js
// under `node --test`, without adding jsdom or any other dependency. Only
// implements the handful of DOM surface those modules actually touch.

class FakeText {
  constructor(data) {
    this.nodeType = 3;
    this.data = String(data);
  }
  get textContent() {
    return this.data;
  }
}

class FakeElement {
  constructor(tag) {
    this.nodeType = 1;
    this.tagName = String(tag).toUpperCase();
    this._attrs = new Map();
    this.children = [];
    this.parentNode = null;
    this._listeners = {};
    this.dataset = {};
    this.style = { cssText: "" };
    this.className = "";
  }
  setAttribute(key, value) {
    this._attrs.set(key, String(value));
    if (key === "class") this.className = String(value);
  }
  getAttribute(key) {
    if (key === "class") return this.className || null;
    return this._attrs.has(key) ? this._attrs.get(key) : null;
  }
  hasAttribute(key) {
    return this._attrs.has(key);
  }
  appendChild(child) {
    this.children.push(child);
    child.parentNode = this;
    return child;
  }
  removeChild(child) {
    this.children = this.children.filter((c) => c !== child);
    return child;
  }
  replaceChildren(...nodes) {
    this.children = nodes;
    nodes.forEach((n) => (n.parentNode = this));
  }
  replaceWith(...nodes) {
    if (!this.parentNode) return;
    const index = this.parentNode.children.indexOf(this);
    if (index === -1) return;
    this.parentNode.children.splice(index, 1, ...nodes);
    nodes.forEach((n) => (n.parentNode = this.parentNode));
    this.parentNode = null;
  }
  addEventListener(type, handler) {
    (this._listeners[type] ??= []).push(handler);
  }
  dispatch(type, event = {}) {
    (this._listeners[type] || []).forEach((handler) => handler(event));
  }
  get firstChild() {
    return this.children[0] || null;
  }
  querySelector() {
    return null;
  }
  querySelectorAll() {
    return [];
  }
  scrollIntoView() {}
  focus() {}
  get textContent() {
    return this.children.map((c) => c.textContent).join("");
  }
  set textContent(value) {
    this.children = [new FakeText(value)];
  }
}

export function installFakeDom() {
  const documentElement = new FakeElement("html");
  const body = new FakeElement("body");
  const fakeDocument = {
    documentElement,
    body,
    createElement: (tag) => new FakeElement(tag),
    createTextNode: (data) => new FakeText(data),
    getElementById: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
  };
  const fakeWindow = {
    dispatchEvent: () => {},
    addEventListener: () => {},
    location: { hash: "" },
  };
  const store = {};
  const fakeLocalStorage = {
    getItem: (key) => (key in store ? store[key] : null),
    setItem: (key, value) => {
      store[key] = String(value);
    },
  };

  globalThis.document = fakeDocument;
  globalThis.window = fakeWindow;
  globalThis.localStorage = fakeLocalStorage;
  globalThis.CustomEvent = class CustomEvent {
    constructor(type, opts = {}) {
      this.type = type;
      this.detail = opts.detail;
    }
  };

  return { document: fakeDocument, window: fakeWindow, FakeElement, FakeText };
}
