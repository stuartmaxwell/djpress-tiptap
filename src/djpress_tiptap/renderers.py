"""Content renderers for DJ Press.

DJ Press passes `Post.content` through the `CONTENT_RENDERER` callable on every page view, and its default renderer
converts Markdown to HTML. The Tiptap editor stores HTML in the database already, so a site using this package should
configure the pass-through renderer instead:

```
DJPRESS_SETTINGS = {
    "CONTENT_RENDERER": "djpress_tiptap.renderers.html_renderer",
}
```

Sites with existing Markdown content must convert all content before switching, see the `djpress_tiptap_convert`
management command.
"""


def html_renderer(content: str) -> str:
    """Return the stored HTML content unchanged.

    A pass-through, because the Tiptap editor already produces the final HTML.

    Args:
        content: The post content, as stored in the database.

    Returns:
        The content unchanged.
    """
    return content
