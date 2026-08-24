"""Conversion of the constrained HTML emitted by djpress-tiptap 0.2.

Version 0.2 of djpress-tiptap stored content as HTML and also included a converter to conver existing Markdown content
to HTML. This converter undoes that and converts HTML back to Markdown.

It keeps HTML for structures that Markdown cannot represent losslessly (video, resized images, and complex tables).

This converter will be removed in a future version.
"""

import re
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser

VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
KNOWN_ELEMENTS = {
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "col",
    "colgroup",
    "del",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "source",
    "strike",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
    "video",
}


@dataclass
class Element:
    """A small HTML tree sufficient for Tiptap's normalized output."""

    tag: str
    attrs: list[tuple[str, str | None]] = field(default_factory=list)
    children: list[Element | Comment | str] = field(default_factory=list)

    def get(self, name: str) -> str | None:
        """Return an attribute value, or ``None`` when it is absent."""
        return next((value for key, value in self.attrs if key == name), None)


@dataclass
class Comment:
    """An HTML comment in the parsed fragment."""

    text: str


class TreeParser(HTMLParser):
    """Parse a fragment without importing a production HTML dependency."""

    def __init__(self) -> None:
        """Create a parser with a synthetic root for fragment content."""
        super().__init__(convert_charrefs=True)
        self.root = Element("__root__")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Add an opening element and make non-void elements current."""
        element = Element(tag.lower(), attrs)
        self.stack[-1].children.append(element)
        if element.tag not in VOID_ELEMENTS:
            self.stack.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Add a self-closing element to the current node."""
        self.stack[-1].children.append(Element(tag.lower(), attrs))

    def handle_endtag(self, tag: str) -> None:
        """Close the matching element, tolerating malformed fragments."""
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        """Add text to the current element."""
        self.stack[-1].children.append(data)

    def handle_comment(self, data: str) -> None:
        """Add an HTML comment to the current element."""
        self.stack[-1].children.append(Comment(data))


def parse_fragment(content: str) -> Element:
    """Parse an HTML fragment beneath a synthetic root element."""
    parser = TreeParser()
    parser.feed(content)
    parser.close()
    return parser.root


def _outer_html(node: Element | Comment | str) -> str:
    if isinstance(node, str):
        return escape(node, quote=False)
    if isinstance(node, Comment):
        return f"<!--{node.text}-->"

    attrs = "".join(
        f" {name}" if value is None else f' {name}="{escape(value, quote=True)}"' for name, value in node.attrs
    )
    if node.tag in VOID_ELEMENTS:
        return f"<{node.tag}{attrs}>"
    children = "".join(_outer_html(child) for child in node.children)
    return f"<{node.tag}{attrs}>{children}</{node.tag}>"


def _text_content(node: Element | Comment | str) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, Comment):
        return ""
    return "".join(_text_content(child) for child in node.children)


def _escape_markdown(text: str) -> str:
    text = re.sub(r"([\\`*_\[\]~])", r"\\\1", text)
    return re.sub(r"(?m)^(\s*)([#>]|[-+*]\s|\d+[.)]\s)", r"\1\\\2", text)


def _inline_code(text: str) -> str:
    fence = "`" * (max((len(match) for match in re.findall(r"`+", text)), default=0) + 1)
    padding = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{padding}{text}{padding}{fence}"


def _render_list(node: Element, *, ordered: bool) -> str:
    lines: list[str] = []
    item_number = 1
    for child in node.children:
        if not isinstance(child, Element) or child.tag != "li":
            continue
        marker = f"{item_number}. " if ordered else "- "
        if ordered:
            item_number += 1
        content = _render_children(child).strip()
        content_lines = content.splitlines() or [""]
        lines.append(marker + content_lines[0])
        lines.extend("  " + line for line in content_lines[1:])
    return "\n".join(lines) + "\n\n"


def _render_children(node: Element) -> str:
    return "".join(_render(child) for child in node.children)


def _render(node: Element | Comment | str) -> str:  # noqa: C901, PLR0911, PLR0912
    if isinstance(node, str):
        return _escape_markdown(node)
    if isinstance(node, Comment):
        return "<!--more-->\n\n" if node.text.strip() == "more" else _outer_html(node)

    tag = node.tag
    content = _render_children(node)
    if tag == "__root__":
        return content
    if tag == "p":
        return content.strip() + "\n\n"
    if re.fullmatch(r"h[1-6]", tag):
        return f"{'#' * int(tag[1])} {content.strip()}\n\n"
    if tag in {"strong", "b"}:
        return f"**{content}**"
    if tag in {"em", "i"}:
        return f"*{content}*"
    if tag in {"s", "strike", "del"}:
        return f"<del>{content}</del>"
    if tag == "code":
        return _inline_code(_text_content(node))
    if tag == "pre":
        code = next((child for child in node.children if isinstance(child, Element) and child.tag == "code"), None)
        language = ""
        if code:
            match = re.search(r"(?:^|\s)language-([^\s]+)", code.get("class") or "")
            language = match.group(1) if match else ""
        body = _text_content(code or node).rstrip("\n")
        fence = "`" * max(3, max((len(match) for match in re.findall(r"`+", body)), default=0) + 1)
        return f"{fence}{language}\n{body}\n{fence}\n\n"
    if tag == "a":
        href = node.get("href") or ""
        title = f' "{node.get("title")}"' if node.get("title") else ""
        return f"[{content}]({href}{title})"
    if tag == "blockquote":
        body = content.strip()
        return "\n".join(f"> {line}" if line else ">" for line in body.splitlines()) + "\n\n"
    if tag == "ul":
        return _render_list(node, ordered=False)
    if tag == "ol":
        return _render_list(node, ordered=True)
    if tag == "li":
        return content
    if tag == "br":
        return "  \n"
    if tag == "hr":
        return "---\n\n"
    if tag == "img" and not (node.get("width") or node.get("height")):
        alt = node.get("alt") or ""
        src = node.get("src") or ""
        title = f' "{node.get("title")}"' if node.get("title") else ""
        return f"![{alt}]({src}{title})\n\n"
    if tag in {"img", "video", "table", "u"}:
        return _outer_html(node) + ("" if tag == "u" else "\n\n")

    # Preserve anything outside the known Tiptap schema instead of silently
    # destroying it. The management command reports these tags for review.
    return _outer_html(node) + "\n\n"


def html_to_markdown(content: str) -> str:
    """Convert Tiptap's normalized HTML to portable hybrid Markdown."""
    rendered = _render(parse_fragment(content))
    return re.sub(r"\n{3,}", "\n\n", rendered).strip()


def html_tags(content: str) -> set[str]:
    """Return element names present in an HTML fragment."""
    root = parse_fragment(content)
    tags: set[str] = set()

    def visit(node: Element) -> None:
        for child in node.children:
            if isinstance(child, Element):
                tags.add(child.tag)
                visit(child)

    visit(root)
    return tags


def unsupported_tags(content: str) -> set[str]:
    """Return tags the editor schema cannot model on a subsequent edit."""
    return html_tags(content) - KNOWN_ELEMENTS
