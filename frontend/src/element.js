// <djpress-tiptap-editor> — a form-associated custom element that hosts Tiptap.
//
// `static formAssociated = true` plus ElementInternals.setFormValue() make the
// browser treat this element as a native form control: its value is submitted
// under its `name` attribute with no hidden input needed, and it takes part in
// form reset and <fieldset disabled>.

import { Editor } from "@tiptap/core";
import { extensions } from "./extensions.js";
import { initToolbar } from "./toolbar.js";
import { createFileHandler } from "./attachments.js";
import { MORE_TAG, MORE_ATTR, MORE_VALUE } from "./more.js";

// `<!--more-->` is invisible to the editor's schema (see more.js), so it's
// swapped for the `more` node's sentinel element on the way in, and back
// again on the way out — the DB and DJ Press only ever see the real comment.
const MORE_COMMENT = "<!--more-->";
const MORE_ELEMENT_RE = new RegExp(
  `<${MORE_TAG} ${MORE_ATTR}="${MORE_VALUE}"[^>]*>.*?</${MORE_TAG}>`,
  "g",
);

function toEditorHTML(html) {
  return html.replaceAll(
    MORE_COMMENT,
    `<${MORE_TAG} ${MORE_ATTR}="${MORE_VALUE}"></${MORE_TAG}>`,
  );
}

function fromEditorHTML(html) {
  return html.replace(MORE_ELEMENT_RE, MORE_COMMENT);
}

export default class DjTiptapEditor extends HTMLElement {
  static formAssociated = true;

  #internals;
  #editor = null;
  #initialContent = "";

  constructor() {
    super();
    this.#internals = this.attachInternals();
  }

  // Expose the Tiptap instance to collaborators (the Alpine toolbar).
  get editor() {
    return this.#editor;
  }

  connectedCallback() {
    if (this.#editor) return; // re-fires if the element is moved in the DOM

    // When the element is upgraded during the initial page parse, its children
    // (the initial value) haven't been parsed yet — wait for the full document.
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () => this.#mount(), {
        once: true,
      });
    } else {
      this.#mount();
    }
  }

  disconnectedCallback() {
    this.#editor?.destroy();
    this.#editor = null;
  }

  // Called by the browser when the surrounding form is reset.
  formResetCallback() {
    this.#editor?.commands.setContent(toEditorHTML(this.#initialContent));
    this.#syncFormValue();
  }

  // Called by the browser when this element or an ancestor fieldset is disabled.
  formDisabledCallback(disabled) {
    this.#editor?.setEditable(!disabled);
  }

  #mount() {
    // The server renders the initial value HTML-escaped as this element's text
    // content; reading textContent decodes it, like a <textarea> does natively.
    this.#initialContent = this.textContent.trim();
    this.replaceChildren();

    // Django endpoint URLs arrive as data attributes on this element. The
    // CSRF token is read from the surrounding form's {% csrf_token %} input
    // (a function, so it's read fresh per request), which works even with
    // CSRF_COOKIE_HTTPONLY.
    // Comma-separated mime types, e.g. "image/jpeg,image/png" — defined once
    // in conf.py and forwarded by the widget as data-accept-image /
    // data-accept-video. Kept separate so each upload button's file picker
    // only offers its own kind; combined for the drag-drop/paste filter.
    const acceptImage = this.dataset.acceptImage;
    const acceptVideo = this.dataset.acceptVideo;

    const config = {
      // Note: dataset is the browser's built-in view of data-* attributes: data-upload-url="..." on the element becomes this.dataset.uploadUrl (kebab-case → camelCase is automatic).
      uploadUrl: this.dataset.uploadUrl,
      browseUrl: this.dataset.browseUrl,
      acceptImage,
      acceptVideo,
      accept: [acceptImage, acceptVideo].filter(Boolean).join(","),

      // Lambda function to read the csrf token fresh each time the upload happens
      csrfToken: () =>
        this.closest("form")?.querySelector('input[name="csrfmiddlewaretoken"]')
          ?.value ?? "",
    };

    this.#editor = new Editor({
      element: this,
      // Drag-drop/paste upload only makes sense when an upload endpoint was
      // configured on the element.
      // If config.uploadUrl is set, build a new list of extensions with the FileHandler added, or else just retunr the extensions.
      extensions: config.uploadUrl
        ? [...extensions, createFileHandler(config)]
        : extensions,

      content: toEditorHTML(this.#initialContent),
      // These callbacks receive the editor as an argument, and must use it
      // instead of this.#editor: the first events can fire *inside* the
      // `new Editor()` call, before the assignment to this.#editor has
      // happened. That's not theoretical — when the initial content ends with
      // an atom block (e.g. a post ending in a <video>), the TrailingNode
      // plugin dispatches a fix-up transaction during construction, which
      // emits `update` synchronously while this.#editor is still null.
      // Reading it here would then throw, aborting the constructor and
      // leaving the element permanently without an editor.
      onCreate: ({ editor }) => this.#syncFormValue(editor),
      onUpdate: ({ editor }) => this.#syncFormValue(editor),
    });

    const toolbar = this.parentElement?.querySelector(
      "[data-djpress-tiptap-toolbar]",
    );
    if (toolbar) {
      initToolbar(toolbar, this.#editor, config);
    }
  }

  #syncFormValue(editor = this.#editor) {
    this.#internals.setFormValue(fromEditorHTML(editor.getHTML()));
  }
}
