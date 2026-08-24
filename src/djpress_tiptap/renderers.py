"""Legacy content renderer for sites upgrading from djpress-tiptap 0.2.

Note: this will be removed in a future version.

Current versions store Markdown and use DJ Press's default renderer. Sites that still have HTML created by 0.2 can
temporarily configure this pass-through renderer together with ``DJPRESS_TIPTAP_STORAGE_FORMAT = "html"``:

```
DJPRESS_SETTINGS = {
    "CONTENT_RENDERER": "djpress_tiptap.renderers.html_renderer",
}
```

Use ``djpress_tiptap_convert_to_markdown`` to leave compatibility mode.
"""


def html_renderer(content: str) -> str:
    """Return the stored HTML content unchanged.

    A pass-through for content created by the legacy HTML-storage mode.

    Args:
        content: The post content, as stored in the database.

    Returns:
        The content unchanged.
    """
    return content
