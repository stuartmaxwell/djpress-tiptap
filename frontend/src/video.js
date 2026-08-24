// HTML5 <video> as a block node, for self-hosted uploads (mp4/webm).
//
// Tiptap has no official video extension (its YouTube extension is
// iframe-based), so this is a minimal custom node following the same shape
// as extension-image: one atom block with a src attribute, inserted via a
// setVideo command. The stored HTML is a plain <video controls src="...">
// element, playable on public pages with no JS — except for pre-existing
// multi-source markup, which keeps its <source> children (see parseHTML).
import { Node, mergeAttributes } from "@tiptap/core";

function escapeAttribute(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function attribute(name, value) {
  return value == null || value === ""
    ? ""
    : ` ${name}="${escapeAttribute(value)}"`;
}

function videoAttributes(element) {
  const title = element.getAttribute("title");
  const src = element.getAttribute("src");
  if (src) return { src, title };

  const sources = Array.from(element.querySelectorAll("source"))
    .filter((source) => source.getAttribute("src"))
    .map((source) => ({
      src: source.getAttribute("src"),
      type: source.getAttribute("type"),
    }));

  if (sources.length < 2) return { src: sources[0]?.src, title };
  return { sources, title };
}

export const Video = Node.create({
  name: "video",
  group: "block",
  atom: true,
  draggable: true,

  addAttributes() {
    return {
      src: { default: null },
      title: { default: null },
      // Hand-written multi-source markup: [{ src, type }, ...] parsed from
      // <source> children. Serialized back as children, not as an attribute.
      sources: { default: null, renderHTML: () => ({}) },
    };
  },

  parseHTML() {
    return [
      {
        tag: "video",
        getAttrs: videoAttributes,
      },
    ];
  },

  renderHTML({ node, HTMLAttributes }) {
    // preload="metadata" fetches just enough for dimensions and duration, so
    // a post with several videos doesn't download them all on page load.
    const attributes = mergeAttributes(HTMLAttributes, {
      controls: "controls",
      preload: "metadata",
    });

    if (node.attrs.sources?.length) {
      return [
        "video",
        attributes,
        ...node.attrs.sources.map(({ src, type }) => [
          "source",
          type ? { src, type } : { src },
        ]),
      ];
    }
    return ["video", attributes];
  },

  markdownTokenName: "video",

  parseMarkdown(token, helpers) {
    const template = document.createElement("template");
    template.innerHTML = token.raw.trim();
    const element = template.content.querySelector("video");
    return element
      ? helpers.createNode("video", videoAttributes(element))
      : null;
  },

  // HTML is Markdown's portable escape hatch for media it cannot express.
  // Keeping it explicit also preserves ordered <source> fallbacks.
  renderMarkdown(node) {
    const attrs = node.attrs ?? {};
    const sources = attrs.sources?.length
      ? attrs.sources
          .map(
            ({ src, type }) =>
              `<source${attribute("src", src)}${attribute("type", type)}>`,
          )
          .join("")
      : "";
    return `<video${attribute("src", attrs.src)}${attribute("title", attrs.title)} controls="controls" preload="metadata">${sources}</video>`;
  },

  // <video> is not one of Marked's block HTML tags, so without this tokenizer
  // it is wrapped in a paragraph and cannot become our block atom node.
  markdownTokenizer: {
    name: "video",
    level: "block",
    start(src) {
      return src.search(/<video(?:\s|>)/i);
    },
    tokenize(src) {
      const match =
        /^<video(?:\s[^>]*)?>[\s\S]*?<\/video>[\t ]*(?:\r?\n|$)/i.exec(src);
      if (!match) return undefined;
      return { type: "video", raw: match[0], text: match[0] };
    },
  },

  addCommands() {
    return {
      setVideo:
        (attrs) =>
        ({ commands }) =>
          commands.insertContent({ type: this.name, attrs }),
    };
  },
});

export default Video;
