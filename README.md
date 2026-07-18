# DJ Tiptap

Opinionated TipTap editor implementation for Django sites.

Docs are still a work in progress.
See the example app for usage.

## Settings

All settings are optional; the package works with sensible defaults. Upload
and browse buttons only appear in the toolbar when the corresponding URL is
configured.

| Setting | Default | Purpose |
| --- | --- | --- |
| `DJPRESS_TIPTAP_UPLOAD_URL` | unset (uploads disabled) | URL name or path of the attachment upload endpoint |
| `DJPRESS_TIPTAP_BROWSE_URL` | unset (library disabled) | URL name or path of the media-library browse endpoint |
| `DJPRESS_TIPTAP_MAX_UPLOAD_SIZE_MB` | `10` | Maximum image upload size |
| `DJPRESS_TIPTAP_MAX_VIDEO_UPLOAD_SIZE_MB` | `100` | Maximum video upload size |
| `DJPRESS_TIPTAP_ALLOWED_IMAGE_TYPES` | JPEG/PNG/GIF/WebP | Dict of Pillow format → mime type accepted by the upload view |
| `DJPRESS_TIPTAP_ALLOWED_VIDEO_TYPES` | `{"video/mp4", "video/webm"}` | Set of video mime types accepted by the upload view; set to `set()` to disable video uploads |

Images are inserted as `<img>` and validated with Pillow; videos are inserted as HTML5 `<video controls>` elements and
validated by magic bytes with [puremagic](https://github.com/cdgriffith/puremagic). The upload endpoint lives in the
host project (see `example/website/views.py` for the reference implementation) - its JSON response's `content_type`
field tells the editor which element to insert.

## Content renderer

The editor stores HTML in `Post.content`, but DJ Press's default `CONTENT_RENDERER` converts Markdown. Sites using this
package should switch to the bundled pass-through renderer:

```python
DJPRESS_SETTINGS = {
    "CONTENT_RENDERER": "djpress_tiptap.renderers.html_renderer",
}
```

## Migrating an existing Markdown site

Existing posts stored as Markdown must be converted to HTML before they can be edited with this widget. The
`djpress_tiptap_convert` management command renders each post with the site's configured Markdown renderer, so the
public pages are unchanged, and writes the HTML back to `Post.content`:

```sh
python manage.py djpress_tiptap_convert           # dry run: reports what would change
python manage.py djpress_tiptap_convert --apply   # write the converted content
```

Convert first (while `CONTENT_RENDERER` is still the Markdown renderer), then switch the setting; if the setting was
already switched, pass `--renderer djpress.markdown_renderer.default_renderer`. The conversion is one-way:
**back up the database first**. The command's report also flags posts containing HTML the editor's schema doesn't model
(iframes, definition lists, ...): those render fine on the public site, but the flagged tags would be dropped the first
time such a post is edited and saved.
