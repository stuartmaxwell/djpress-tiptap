# DJ Tiptap

Opinionated TipTap editor implementation for Django sites.

Docs are still a work in progress.
See the example app for usage.

## Settings

All settings are optional; the package works with sensible defaults. Upload
and browse buttons only appear in the toolbar when the corresponding URL is
configured.

| Setting                                   | Default                       | Purpose                                                                                              |
| ----------------------------------------- | ----------------------------- | ---------------------------------------------------------------------------------------------------- |
| `DJPRESS_TIPTAP_UPLOAD_URL`               | unset (uploads disabled)      | URL name or path of the attachment upload endpoint                                                   |
| `DJPRESS_TIPTAP_BROWSE_URL`               | unset (library disabled)      | URL name or path of the media-library browse endpoint                                                |
| `DJPRESS_TIPTAP_MAX_UPLOAD_SIZE_MB`       | `10`                          | Maximum image upload size                                                                            |
| `DJPRESS_TIPTAP_MAX_VIDEO_UPLOAD_SIZE_MB` | `100`                         | Maximum video upload size                                                                            |
| `DJPRESS_TIPTAP_ALLOWED_IMAGE_TYPES`      | JPEG/PNG/GIF/WebP             | Dict of Pillow format → mime type accepted by the upload view                                        |
| `DJPRESS_TIPTAP_ALLOWED_VIDEO_TYPES`      | `{"video/mp4", "video/webm"}` | Set of video mime types accepted by the upload view; set to `set()` to disable video uploads         |
| `DJPRESS_TIPTAP_STORAGE_FORMAT`           | `"markdown"`                  | Canonical content format; deprecated `"html"` mode exists temporarily for sites upgrading from 0.2.x |

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
to have run first), and the package URLs must be included for the upload/browse endpoints to resolve. The editor pins
its content styles against the host page's CSS (the admin's global element styles, list bullets, heading bars, form
font sizes, don't bleed in). Note the admin's dark theme is not yet supported: the editor keeps its light styling.

## Content renderer

The editor stores Markdown in `Post.content`, matching DJ Press's standard behaviour. Features that Markdown cannot
represent losslessly use embedded HTML: videos, resized images, resized/complex tables, underline and strikethrough.

Use DJ Press's default content renderer and enable the extensions needed by the corresponding editor toolbar features:

```python
DJPRESS_SETTINGS = {
    "MARKDOWN_EXTENSIONS": ["fenced_code", "tables"],
}
```

When DJ Press's default renderer is active, the `djpress_tiptap.W002` system check warns if its effective configuration
cannot render fenced code blocks or tables. Equivalent extension bundles such as `extra` are detected by capability,
not by name.

## Upgrading from djpress-tiptap 0.2.x

Versions 0.2.x stored content as HTML and used `djpress_tiptap.renderers.html_renderer`. On upgrade, select
compatibility mode first so existing posts continue to load and save as HTML. Django's system checks will emit
`djpress_tiptap.W001` until the deprecated compatibility mode is removed:

```python
DJPRESS_TIPTAP_STORAGE_FORMAT = "html"

DJPRESS_SETTINGS = {
    "CONTENT_RENDERER": "djpress_tiptap.renderers.html_renderer",
}
```

Back up the database, then audit and convert the existing HTML. The command is a dry run unless `--apply` is passed:

```sh
python manage.py djpress_tiptap_convert_to_markdown
python manage.py djpress_tiptap_convert_to_markdown --apply
```

The converter produces portable Markdown and retains HTML for video, resized media and complex tables. Other HTML
outside the editor schema is preserved and reported for manual review. It does not change post `updated_at` timestamps.

After conversion, remove `DJPRESS_TIPTAP_STORAGE_FORMAT` (or set it to `"markdown"`), remove the pass-through
`CONTENT_RENDERER`, and enable `MARKDOWN_EXTENSIONS` as shown above. Do not leave Markdown posts in HTML mode or HTML
posts in Markdown mode; format auto-detection is intentionally avoided because valid Markdown may contain HTML. The
`djpress_tiptap.E001` system check prevents Markdown storage from being used with the legacy pass-through renderer.

## Legacy Markdown-to-HTML command

`djpress_tiptap_convert` is retained for compatibility with the old HTML-storage workflow. It renders each post with
the configured Markdown renderer and writes the resulting HTML back to `Post.content`:

```sh
python manage.py djpress_tiptap_convert           # dry run: reports what would change
python manage.py djpress_tiptap_convert --apply   # write the converted content
```

If the setting was already switched, pass `--renderer djpress.markdown_renderer.default_renderer`. Back up the
database first. The command's report also flags posts containing HTML the editor's schema doesn't model
(iframes, definition lists, ...): those render fine on the public site, but the flagged tags would be dropped the first
time such a post is edited and saved.

If the report flags `div, span` on posts with fenced code blocks, your `MARKDOWN_EXTENSIONS` includes `codehilite`,
which bakes Pygments highlighting markup into the HTML — markup the editor strips on the first edit, taking the
language information with it. Remove `codehilite` from `MARKDOWN_EXTENSIONS` for the conversion run: plain
`fenced_code` produces `<pre><code class="language-python">`, the exact form the editor round-trips losslessly. Public
pages then need client-side highlighting instead of Pygments — include this package's `content.bundle.js` and
`content.css` (highlight.js) on the post templates, as the example project does.
