import { Extension } from "@tiptap/core";
import { Plugin } from "@tiptap/pm/state";
import { closeHistory } from "@tiptap/pm/history";

const markdownBlocks = new Set([
  "heading",
  "bulletList",
  "orderedList",
  "blockquote",
  "codeBlock",
  "horizontalRule",
  "table",
  "more",
]);

// Use the existing parser to recognize actual Markdown structure, rather than
// guessing from asterisks or backticks that may just be ordinary prose.
function hasMarkdownFormatting(nodes) {
  return nodes.some(
    (node) =>
      markdownBlocks.has(node.type) ||
      node.type === "image" ||
      node.marks?.length > 0 ||
      (node.content && hasMarkdownFormatting(node.content)),
  );
}

export const PasteMarkdown = Extension.create({
  name: "pasteMarkdown",
  priority: 1100,

  addProseMirrorPlugins() {
    const editor = this.editor;
    // ClipboardEvent does not expose modifier keys. Track Shift through DOM
    // events so the browser's Ctrl/Cmd+Shift+V remains a literal paste.
    let shiftDown = false;
    return [
      new Plugin({
        props: {
          handleDOMEvents: {
            keydown(_view, event) {
              shiftDown = event.shiftKey;
              return false;
            },
            keyup(_view, event) {
              shiftDown = event.shiftKey;
              return false;
            },
            blur() {
              shiftDown = false;
              return false;
            },
          },
          handlePaste(view, event, slice) {
            const clipboard = event.clipboardData;
            const text = clipboard?.getData("text/plain");
            if (!editor.isEditable || !text || clipboard.files.length)
              return false;
            // Let ProseMirror paste literal text inside code, and let the existing
            // file handler and rich HTML clipboard path keep their own behavior.
            for (
              let depth = view.state.selection.$from.depth;
              depth > 0;
              depth--
            ) {
              if (view.state.selection.$from.node(depth).type.spec.code)
                return false;
            }
            if (shiftDown) {
              // Use ProseMirror's plain-text slice, but skip Tiptap's inline paste
              // rules too: **bold** must remain literal in this explicit mode.
              view.dispatch(
                closeHistory(
                  view.state.tr.replaceSelection(slice).scrollIntoView(),
                ),
              );
              view.dispatch(closeHistory(view.state.tr));
              return true;
            }
            if (clipboard.getData("text/html") || !editor.markdown)
              return false;

            const nodes =
              editor.markdown.parse(text.replace(/\r\n?/g, "\n")).content ?? [];
            if (!hasMarkdownFormatting(nodes)) return false;
            // A single Markdown paragraph is an inline paste when the caret is
            // in text. Do not split the surrounding sentence into three blocks.
            const content =
              nodes.length === 1 &&
              nodes[0].type === "paragraph" &&
              view.state.selection.$from.parent.isTextblock
                ? (nodes[0].content ?? [])
                : nodes;
            const inserted = editor
              .chain()
              .command(({ tr }) => {
                closeHistory(tr);
                return true;
              })
              .insertContent(content)
              .run();
            if (inserted) view.dispatch(closeHistory(view.state.tr));
            return inserted;
          },
        },
      }),
    ];
  },
});
