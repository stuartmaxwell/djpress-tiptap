"""DJ Tiptap custom form widgets."""

from django import forms

from djpress_tiptap import conf


class DjTiptapWidget(forms.Widget):
    """Tiptap rich-text editor rendered as a form-associated custom element.

    The <djpress-tiptap-editor> element registers itself as a form control via ElementInternals, so it submits its
    Markdown under the field name directly without the need for a hidden input. An explicit legacy setting can retain
    HTML while a site migrates content created by djpress-tiptap 0.2.

    The attachment endpoints are configurable per instance
    (DjTiptapWidget(upload_url=..., browse_url=...)), per project
    (DJPRESS_TIPTAP_UPLOAD_URL / DJPRESS_TIPTAP_BROWSE_URL settings), or fall back to
    the built-in views. Values may be URL names or paths, like LOGIN_URL.
    """

    template_name = "djpress_tiptap/widgets/djpress_tiptap_editor.html"

    def __init__(self, attrs=None, upload_url=None, browse_url=None):
        """Store per-instance endpoint overrides; None means "use setting or default"."""
        super().__init__(attrs)
        self.upload_url = upload_url
        self.browse_url = browse_url

    def use_required_attribute(self, initial):
        """Constraint validation is left to the server; the element doesn't render a required attribute."""
        return False

    def get_context(self, name, value, attrs):
        """Expose the attachment endpoint URLs to the editor JS as data attributes."""
        context = super().get_context(name, value, attrs)
        # Resolved at render time, so the URLconf is fully loaded by then
        context["widget"]["upload_url"] = conf.upload_url(self.upload_url)
        context["widget"]["browse_url"] = conf.browse_url(self.browse_url)
        # Comma-separated mime types for the JS file pickers and drag-drop
        # filter, so the accepted types are defined only in conf.py. Image and
        # video lists stay separate so each upload button's file picker only
        # offers its own kind; the JS combines them for the drag-drop filter.
        context["widget"]["accept_image"] = ",".join(conf.allowed_image_types().values())
        context["widget"]["accept_video"] = ",".join(sorted(conf.allowed_video_types()))
        context["widget"]["storage_format"] = conf.storage_format()
        return context

    def value_from_datadict(self, data, files, name):
        """Return LF Markdown after HTML form line-break normalization."""
        value = super().value_from_datadict(data, files, name)
        if conf.storage_format() == "markdown" and isinstance(value, str):
            return value.replace("\r\n", "\n").replace("\r", "\n")
        return value

    class Media:
        js = ["djpress_tiptap/djtiptap.bundle.js"]
        css = {"all": ["djpress_tiptap/djtiptap.css"]}
