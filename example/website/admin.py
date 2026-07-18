"""Django admin integration for the Tiptap editor.

djpress registers its own PostAdmin (fieldsets, role-based readonly fields,
author defaulting), so rather than registering from scratch, subclass it and
swap only the content field's widget. The widget's Media class makes the
admin include the editor bundle and CSS on the add/change pages.

This module must be imported after djpress's admin registration, which
admin.autodiscover() guarantees as long as "website" is listed after
"djpress" in INSTALLED_APPS.
"""

from django.contrib import admin
from djpress.admin import PostAdmin
from djpress.models import Post

from djpress_tiptap.widgets import DjTiptapWidget

admin.site.unregister(Post)


@admin.register(Post)
class TiptapPostAdmin(PostAdmin):
    """djpress's Post admin with the content field edited via Tiptap."""

    def get_form(self, request, obj=None, change=False, **kwargs):  # noqa: ANN001, ANN003, ANN201, FBT002
        """Swap in the Tiptap widget for content only.

        The widgets kwarg flows through to modelform_factory, and calling
        super() keeps djpress's own get_form behaviour (author initial).
        """
        kwargs["widgets"] = {"content": DjTiptapWidget()}
        return super().get_form(request, obj, change, **kwargs)
