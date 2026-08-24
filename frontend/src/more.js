// The "Read more" split marker used by DJ Press: a standalone `<!--more-->`
// line in Markdown tells DJ Press where to truncate the excerpt.
//
// ProseMirror's DOM parser only reads element and text nodes (see
// addDOM in prosemirror-model) — comment nodes are silently dropped, so a
// raw `<!--more-->` can never round-trip through the DOM schema. Instead this
// node renders as a sentinel element, `<div data-type="more">`, inside the
// editor. Its Markdown tokenizer/parser/renderer maps that node to the exact
// marker DJ Press expects. element.js retains the older HTML-boundary swap
// only for sites temporarily using legacy HTML storage.
import {
  Node,
  mergeAttributes,
  canInsertNode,
  isNodeSelection,
} from "@tiptap/core";
import { NodeSelection, TextSelection } from "@tiptap/pm/state";

// Kept in one place so element.js's HTML-boundary conversion and this
// node's parseHTML/renderHTML can't drift apart.
export const MORE_TAG = "div";
export const MORE_ATTR = "data-type";
export const MORE_VALUE = "more";
export const MORE_COMMENT = "<!--more-->";

export const More = Node.create({
  name: "more",
  group: "block",
  atom: true,
  selectable: true,

  parseHTML() {
    return [{ tag: `${MORE_TAG}[${MORE_ATTR}="${MORE_VALUE}"]` }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      MORE_TAG,
      mergeAttributes(HTMLAttributes, { [MORE_ATTR]: MORE_VALUE }),
      "Read more",
    ];
  },

  markdownTokenName: "more",

  parseMarkdown(_token, helpers) {
    return helpers.createNode("more");
  },

  renderMarkdown() {
    return MORE_COMMENT;
  },

  // Marked treats HTML comments as generic HTML. Registering this exact,
  // block-level token keeps the DJ Press marker out of that lossy fallback
  // while leaving comments in inline/fenced code untouched.
  markdownTokenizer: {
    name: "more",
    level: "block",
    start(src) {
      return src.search(/^[\t ]*<!--more-->[\t ]*(?:\r?\n|$)/m);
    },
    tokenize(src) {
      const match = /^[\t ]*<!--more-->[\t ]*(?:\r?\n|$)/.exec(src);
      if (!match) return undefined;

      return {
        type: "more",
        raw: match[0],
        text: MORE_COMMENT,
      };
    },
  },

  addCommands() {
    return {
      // Mirrors StarterKit's setHorizontalRule: insert the node, then land
      // the cursor just after it (adding a paragraph to land in if the
      // marker was inserted at the very end of the document).
      setMore:
        () =>
        ({ chain, state }) => {
          let alreadyPresent = false;
          state.doc.descendants((node) => {
            if (node.type.name === this.name) alreadyPresent = true;
          });
          if (alreadyPresent) return false;

          if (!canInsertNode(state, state.schema.nodes[this.name])) {
            return false;
          }

          const { selection } = state;
          const { $to } = selection;
          const currentChain = chain();

          if (isNodeSelection(selection)) {
            currentChain.insertContentAt($to.pos, { type: this.name });
          } else {
            currentChain.insertContent({ type: this.name });
          }

          return currentChain
            .command(({ tr, dispatch }) => {
              if (dispatch) {
                const { $to: posTo } = tr.selection;
                const posAfter = posTo.end();

                if (posTo.nodeAfter) {
                  if (posTo.nodeAfter.isTextblock) {
                    tr.setSelection(
                      TextSelection.create(tr.doc, posTo.pos + 1),
                    );
                  } else if (posTo.nodeAfter.isBlock) {
                    tr.setSelection(NodeSelection.create(tr.doc, posTo.pos));
                  } else {
                    tr.setSelection(TextSelection.create(tr.doc, posTo.pos));
                  }
                } else {
                  const paragraph =
                    tr.doc.type.schema.nodes.paragraph?.create();
                  if (paragraph) {
                    tr.insert(posAfter, paragraph);
                    tr.setSelection(TextSelection.create(tr.doc, posAfter + 1));
                  }
                }
                tr.scrollIntoView();
              }
              return true;
            })
            .run();
        },
    };
  },
});

export default More;
