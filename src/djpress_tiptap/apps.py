"""Django app configuration for DJ Tiptap."""

from django.apps import AppConfig


class DjTiptapBaseConfig(AppConfig):
    """App configuration for DJ Tiptap."""

    name = "djpress_tiptap"
    verbose_name = "DJ Press Tiptap"

    def ready(self) -> None:
        """Register DJ Press Tiptap's Django system checks."""
        from djpress_tiptap import checks  # noqa: F401, PLC0415
