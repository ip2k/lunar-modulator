// SPDX-License-Identifier: MIT
// Minimal DOM fake shared by the installer page tests.
export class Element {
  constructor(tagName, ownerDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.listeners = new Map();
    this.attributes = new Map();
    this.checked = false;
    this.disabled = false;
    this._textContent = '';
  }
  append(...children) {
    for (const child of children) {
      if (typeof child === 'string') { const text = new Element('#text', this.ownerDocument); text.textContent = child; this.children.push(text); } else this.children.push(child);
    }
  }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  addEventListener(name, callback) {
    if (!this.listeners.has(name)) this.listeners.set(name, []);
    this.listeners.get(name).push(callback);
  }
  async dispatch(name) {
    await Promise.all((this.listeners.get(name) ?? []).map((callback) => callback({ target: this })));
  }
  click() { this.wasClicked = true; }
  remove() { this.removed = true; }
  get textContent() { return this._textContent + this.children.map((child) => child.textContent).join(''); }
  set textContent(value) { this._textContent = String(value); this.children = []; }
}

export class Document {
  constructor() { this.nodes = new Map(); this.defaultView = { location: { origin: 'https://lunar.test' } }; this.serviceMarker = null; }
  querySelector(selector) { return selector === 'meta[name="lunar-installer-build-service"]' ? this.serviceMarker : null; }
  createElement(tagName) { return new Element(tagName, this); }
  createTextNode(value) { const node = new Element('#text', this); node.textContent = value; return node; }
  getElementById(id) { return this.nodes.get(id) ?? null; }
}

export function walk(root) { return [root, ...root.children.flatMap(walk)]; }

