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

Images are inserted as `<img>` and validated with Pillow; videos are inserted
as HTML5 `<video controls>` elements and validated by magic bytes with
[puremagic](https://github.com/cdgriffith/puremagic). The upload endpoint
lives in the host project (see `example/website/views.py` for the reference
implementation) — its JSON response's `content_type` field tells the editor
which element to insert.
