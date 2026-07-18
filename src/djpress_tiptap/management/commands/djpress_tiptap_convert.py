"""One-time, in-place conversion of stored Markdown post content to HTML.

For a site switching to the Tiptap editor: each post's Markdown is rendered
with the site's configured Markdown renderer — so the resulting HTML is
exactly what the site already serves publicly — and written back to
``Post.content``. Afterwards, set ``CONTENT_RENDERER`` to
``djpress_tiptap.renderers.html_renderer``.

The default run is a dry run that reports what would change; pass ``--apply``
to write. Conversion is one-way: back up the database first.
"""

from html.parser import HTMLParser

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils.module_loading import import_string
from djpress.conf import settings as djpress_settings
from djpress.models.post import PUBLISHED_POSTS_CACHE_KEY, Post
from djpress.utils import get_content_renderer

from djpress_tiptap.renderers import html_renderer

# Tags the Tiptap editor's schema models (see frontend/src/extensions.js).
# Anything else in a converted post still renders fine on the public page,
# but would be silently dropped or unwrapped the first time the post is
# opened in the editor and saved — so the command reports it.
EDITOR_TAGS = frozenset(
    {
        "p", "h1", "h2", "h3", "h4", "h5", "h6",
        "ul", "ol", "li", "blockquote", "pre", "code", "hr", "br",
        "strong", "b", "em", "i", "s", "del", "strike", "u", "a",
        "img", "video", "source",
        "table", "thead", "tbody", "tr", "th", "td", "colgroup", "col",
    }
)  # fmt: skip


class _TagCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list) -> None:  # noqa: ARG002
        """Record every element name seen in the document."""
        self.tags.add(tag)


def unsupported_tags(html: str) -> list[str]:
    """Return the tags in `html` that the editor's schema doesn't model.

    Args:
        html: The rendered HTML to scan.

    Returns:
        Sorted list of tag names that would not survive an edit-and-save.
    """
    collector = _TagCollector()
    collector.feed(html)
    return sorted(collector.tags - EDITOR_TAGS)


class Command(BaseCommand):
    """Convert stored Markdown post content to HTML, in place."""

    help = (
        "Convert every post's stored Markdown content to HTML using the configured "
        "Markdown renderer, so the site can switch CONTENT_RENDERER to "
        "djpress_tiptap.renderers.html_renderer. Dry run by default; pass --apply to "
        "write. One-way: back up the database first."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Register the command's flags."""
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the converted content to the database (default is a dry run).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Also convert posts whose content already looks like HTML (starts with '<').",
        )
        parser.add_argument(
            "--renderer",
            help=(
                "Dotted path of the Markdown renderer to convert with. Defaults to the "
                "configured CONTENT_RENDERER, so use this when that has already been "
                "switched to the HTML renderer."
            ),
        )

    def handle(self, **options) -> None:  # noqa: ANN003
        """Run the conversion."""
        renderer = self._resolve_renderer(options["renderer"])
        truncate_tag = djpress_settings.TRUNCATE_TAG

        converted = 0
        skipped = 0
        for post in Post.admin_objects.all().order_by("pk"):
            label = f"{post.post_type} {post.pk} ({post.slug})"
            raw = post.content

            if not options["force"] and raw.lstrip().startswith("<"):
                self.stdout.write(f"{label}: skipped — content already looks like HTML (use --force to convert)")
                skipped += 1
                continue

            rendered = renderer(raw)

            if truncate_tag in raw and truncate_tag not in rendered:
                # Never trade the excerpt marker away silently: djpress splits
                # on the raw tag before rendering, so losing it changes what
                # the index pages show.
                self.stderr.write(
                    self.style.ERROR(f"{label}: skipped — rendering would lose the {truncate_tag} marker")
                )
                skipped += 1
                continue

            leftovers = unsupported_tags(rendered)
            note = ""
            if leftovers:
                note = self.style.WARNING(
                    f" — contains tags the editor would drop on the next save: {', '.join(leftovers)}"
                )

            if options["apply"]:
                # queryset.update() rather than post.save(): no auto_now bump
                # of updated_at, no slug regeneration, no save signals.
                Post.admin_objects.filter(pk=post.pk).update(content=rendered)
                self.stdout.write(f"{label}: converted{note}")
            else:
                self.stdout.write(f"{label}: would convert{note}")
            converted += 1

        if options["apply"] and converted:
            # .update() bypasses the post_save signal that normally clears
            # djpress's cached published-posts queryset.
            cache.delete(PUBLISHED_POSTS_CACHE_KEY)

        summary = f"{converted} converted, {skipped} skipped"
        if options["apply"]:
            self.stdout.write(self.style.SUCCESS(summary))
        else:
            self.stdout.write(f"Dry run ({summary}): no changes written. Re-run with --apply to convert.")

    def _resolve_renderer(self, override: str | None):  # noqa: ANN202
        """Import the Markdown renderer to convert with, refusing a pass-through."""
        path = override or str(djpress_settings.CONTENT_RENDERER)
        try:
            renderer = import_string(path) if override else get_content_renderer()
        except ImportError as exc:
            msg = f"Could not import renderer '{path}': {exc}"
            raise CommandError(msg) from exc

        if renderer is html_renderer:
            msg = (
                "CONTENT_RENDERER is already djpress_tiptap.renderers.html_renderer, which "
                "would convert nothing. Pass --renderer with the Markdown renderer that "
                "produced your public pages, e.g. --renderer djpress.markdown_renderer.default_renderer."
            )
            raise CommandError(msg)
        return renderer
