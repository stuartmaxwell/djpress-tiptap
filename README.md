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

## Django admin

The widget works in the Django admin: its `Media` class makes the admin pull in the editor bundle and CSS
automatically. DJ Press registers its own `PostAdmin`, so unregister it and subclass, swapping only the content
field's widget (see `example/website/admin.py` for the reference implementation):

```python
from django.contrib import admin
from djpress.admin import PostAdmin
from djpress.models import Post
from djpress_tiptap.widgets import DjTiptapWidget

admin.site.unregister(Post)


@admin.register(Post)
class TiptapPostAdmin(PostAdmin):
    def get_form(self, request, obj=None, change=False, **kwargs):
        kwargs["widgets"] = {"content": DjTiptapWidget()}
        return super().get_form(request, obj, change, **kwargs)
```

The app with this `admin.py` must come after `djpress` in `INSTALLED_APPS` (unregister needs djpress's registration
to have run first), and the package URLs must be included for the upload/browse endpoints to resolve. Note the admin's
dark theme is not yet supported: the editor keeps its light styling.

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

If the report flags `div, span` on posts with fenced code blocks, your `MARKDOWN_EXTENSIONS` includes `codehilite`,
which bakes Pygments highlighting markup into the HTML — markup the editor strips on the first edit, taking the
language information with it. Remove `codehilite` from `MARKDOWN_EXTENSIONS` for the conversion run: plain
`fenced_code` produces `<pre><code class="language-python">`, the exact form the editor round-trips losslessly. Public
pages then need client-side highlighting instead of Pygments — include this package's `content.bundle.js` and
`content.css` (highlight.js) on the post templates, as the example project does.
