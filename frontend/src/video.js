// HTML5 <video> as a block node, for self-hosted uploads (mp4/webm).
//
// Tiptap has no official video extension (its YouTube extension is
// iframe-based), so this is a minimal custom node following the same shape
// as extension-image: one atom block with a src attribute, inserted via a
// setVideo command. The stored HTML is a plain <video controls src="...">
// element, playable on public pages with no JS — except for pre-existing
// multi-source markup, which keeps its <source> children (see parseHTML).
import { Node, mergeAttributes } from "@tiptap/core";

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
        getAttrs: (element) => {
          const title = element.getAttribute("title");

          // Browsers ignore <source> children when the src attribute is
          // present, so nothing observable is lost by dropping them here.
          const src = element.getAttribute("src");
          if (src) return { src, title };

          const sources = Array.from(element.querySelectorAll("source"))
            .filter((source) => source.getAttribute("src"))
            .map((source) => ({
              src: source.getAttribute("src"),
              type: source.getAttribute("type"),
            }));

          // A lone <source> offers the browser no choice, so it collapses
          // into the canonical attribute form. Two or more are the format
          // fallback (e.g. webm + mp4) and must survive verbatim, in order.
          if (sources.length < 2) return { src: sources[0]?.src, title };
          return { sources, title };
        },
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
