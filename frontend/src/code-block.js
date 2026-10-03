import CodeBlockLowlight from "@tiptap/extension-code-block-lowlight";
import { closeHistory } from "@tiptap/pm/history";

// The node view is editor chrome only. The inherited HTML/Markdown serializers
// still write just the code and its language, never the dropdown or wrapper.
export const CodeBlockWithLanguage = CodeBlockLowlight.extend({
  addNodeView() {
    const languages = this.options.lowlight.listLanguages().sort();

    return ({ node, editor, getPos }) => {
      let currentNode = node;
      const dom = document.createElement("div");
      dom.className = "djpress-tiptap-code-block";

      const header = document.createElement("div");
      header.className = "djpress-tiptap-code-header";
      header.contentEditable = "false";

      const label = document.createElement("label");
      label.textContent = "Language ";
      const select = document.createElement("select");
      select.setAttribute("aria-label", "Code block language");
      select.append(new Option("Unspecified", ""));
      for (const language of languages) {
        select.append(new Option(language, language));
      }
      label.append(select);
      header.append(label);

      const pre = document.createElement("pre");
      const code = document.createElement("code");
      pre.append(code);
      dom.append(header, pre);

      let customOption;
      const refresh = () => {
        const language = currentNode.attrs.language || "";
        customOption?.remove();
        customOption = undefined;
        // Preserve aliases (e.g. js) and languages outside the bundled set.
        // Simply opening a post must never replace its existing fence label.
        if (language && !languages.includes(language)) {
          customOption = new Option(language, language);
          select.append(customOption);
        }
        select.value = language;
        select.disabled = !editor.isEditable;
        code.className = language
          ? `${this.options.languageClassPrefix || ""}${language}`
          : "";
      };
      refresh();

      select.addEventListener("change", () => {
        const pos = getPos();
        if (typeof pos !== "number" || !editor.isEditable) return;
        // Address this node directly: the editor selection may be in another
        // block when someone clicks this dropdown.
        editor.view.dispatch(
          closeHistory(
            editor.state.tr.setNodeMarkup(pos, undefined, {
              ...currentNode.attrs,
              language: select.value || null,
            }),
          ),
        );
        // Keep subsequent typing out of this language-change undo step too.
        editor.view.dispatch(closeHistory(editor.state.tr));
      });

      return {
        dom,
        contentDOM: code,
        update(updatedNode) {
          if (updatedNode.type !== currentNode.type) return false;
          currentNode = updatedNode;
          refresh();
          return true;
        },
        stopEvent(event) {
          return header.contains(event.target);
        },
        ignoreMutation(mutation) {
          if (mutation.type === "selection") return false;
          return !code.contains(mutation.target);
        },
      };
    };
  },
});
