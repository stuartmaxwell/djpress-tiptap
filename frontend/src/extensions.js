// Extension list and configuration
//
import { Extension, generateHTML } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import { CodeBlockWithLanguage } from "./code-block.js";
import { common, createLowlight } from "lowlight";
import Image from "@tiptap/extension-image";
import Strike from "@tiptap/extension-strike";
import {
  Table,
  TableCell,
  TableHeader,
  TableRow,
  renderTableToMarkdown,
} from "@tiptap/extension-table";
import Underline from "@tiptap/extension-underline";
import { Markdown } from "@tiptap/markdown";
import { Placeholder } from "@tiptap/extensions";
import { Typography } from "@tiptap/extension-typography";
import { More } from "./more.js";
import { Video } from "./video.js";
import { PasteMarkdown } from "./paste-markdown.js";

// The `common` set is ~37 mainstream languages; `all` (~190) triples the
// bundle. Individual grammars can also be registered one by one if even
// common proves too heavy.
const lowlight = createLowlight(common);

function escapeAttribute(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

const PortableImage = Image.extend({
  renderMarkdown(node) {
    const attrs = node.attrs ?? {};
    if (attrs.width || attrs.height) {
      const attributes = ["src", "alt", "title", "width", "height"]
        .filter((name) => attrs[name] != null && attrs[name] !== "")
        .map((name) => ` ${name}="${escapeAttribute(attrs[name])}"`)
        .join("");
      return `<img${attributes}>`;
    }

    const src = attrs.src ?? "";
    const alt = attrs.alt ?? "";
    const title = attrs.title ? ` "${attrs.title}"` : "";
    return `![${alt}](${src}${title})`;
  },
});

// The Markdown manager's generic HTML fallback currently loses non-standard
// image attributes. Intercept raw <img> tokens so the width/height escape
// hatch used above is genuinely bidirectional.
const SizedImageMarkdown = Extension.create({
  name: "sizedImageMarkdown",
  markdownTokenName: "html",
  parseMarkdown(token, helpers) {
    if (!/^\s*<img(?:\s|>)/i.test(token.raw ?? "")) return null;

    const template = document.createElement("template");
    template.innerHTML = token.raw.trim();
    const image = template.content.querySelector("img");
    if (!image) return null;

    const attrs = Object.fromEntries(
      ["src", "alt", "title", "width", "height"]
        .map((name) => [name, image.getAttribute(name)])
        .filter(([, value]) => value != null),
    );
    return helpers.createNode("image", attrs);
  },
});

// Tiptap's stock underline Markdown syntax is ++text++. Raw <u> is more
// portable to other Markdown implementations, while its inherited tokenizer
// still accepts ++text++ when loading older Markdown.
const PortableUnderline = Underline.extend({
  renderMarkdown(node, helpers) {
    return `<u>${helpers.renderChildren(node)}</u>`;
  },
});

// Strikethrough is not part of core Markdown, and DJ Press's default Python
// Markdown renderer leaves ~~text~~ untouched. Inline <del> works without an
// extra renderer dependency, while the inherited tokenizer still accepts
// existing ~~text~~ content.
const PortableStrike = Strike.extend({
  renderMarkdown(node, helpers) {
    return `<del>${helpers.renderChildren(node)}</del>`;
  },
});

function tableNeedsHTML(node) {
  return (node.content ?? []).some((row) =>
    (row.content ?? []).some((cell) => {
      const attrs = cell.attrs ?? {};
      return (
        attrs.colwidth?.some(Boolean) ||
        attrs.colspan > 1 ||
        attrs.rowspan > 1 ||
        cell.content?.length !== 1 ||
        cell.content?.[0]?.type !== "paragraph"
      );
    }),
  );
}

const PortableTable = Table.extend({
  renderMarkdown(node, helpers) {
    if (!tableNeedsHTML(node)) return renderTableToMarkdown(node, helpers);

    return generateHTML({ type: "doc", content: [node] }, htmlExtensions);
  },
});

const htmlExtensions = [
  StarterKit.configure({
    // Clicking a link inside the editor should select it for editing,
    // not navigate away from the form (openOnClick defaults to true).
    link: { openOnClick: false },
    dropcursor: { width: 2 },
    // Disable the built-in code block: CodeBlockLowlight below replaces it,
    // and both register under the same extension name ("codeBlock").
    codeBlock: false,
    // Replaced below so Markdown saves portable <u> markup rather than the
    // Tiptap-specific ++text++ extension syntax.
    underline: false,
    // Replaced below so strikethrough works with DJ Press's default Markdown
    // renderer instead of requiring a third-party ~~text~~ extension.
    strike: false,
  }),
  CodeBlockWithLanguage.configure({
    lowlight,
  }),
  // resize wraps each image in a node view with draggable corner handles
  // (styled in editor.css) and stores the result as width/height attributes
  // on the <img>. Aspect ratio is always kept: free-form distortion is never
  // what you want for a photo.
  PortableImage.configure({
    resize: {
      enabled: true,
      alwaysPreserveAspectRatio: true,
      minWidth: 50,
      minHeight: 50,
    },
  }),
  SizedImageMarkdown,
  PortableTable.configure({ resizable: true }),
  TableRow,
  TableHeader,
  TableCell,
  PortableUnderline,
  PortableStrike,
  // Renders as a data-placeholder attribute + is-editor-empty class on the
  // first paragraph while the document is empty; styled in editor.css.
  Placeholder.configure({
    placeholder: "Write something…",
  }),
  // Smart punctuation as you type: -- → —, ... → …, straight → curly quotes,
  // (c) → ©, -> → →, 1/2 → ½, etc. Each rule can be disabled or overridden
  // via configure (e.g. { emDash: false }).
  Typography,
  // DJ Press's "Read more" excerpt marker — see more.js for why this can't
  // just be a raw `<!--more-->` comment inside the schema.
  More,
  // Self-hosted HTML5 <video> for uploaded clips; see video.js.
  Video,
];

export const extensions = [
  ...htmlExtensions,
  Markdown.configure({ markedOptions: { gfm: true } }),
  PasteMarkdown,
];
