"""Convert content stored by djpress-tiptap 0.2 from HTML to Markdown.

Version 0.2 of djpress-tiptap stored content as HTML and also included a converter to conver existing Markdown content
to HTML. This converter undoes that and converts HTML back to Markdown.

This converter will be removed in a future version.
"""

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from djpress.models import Post
from djpress.models.post import PUBLISHED_POSTS_CACHE_KEY

from djpress_tiptap.conversion import html_tags, html_to_markdown, unsupported_tags


class Command(BaseCommand):
    """Convert stored djpress-tiptap HTML content to hybrid Markdown."""

    help = "Convert djpress-tiptap HTML content back to portable Markdown. Dry run by default."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register the write and force-conversion flags."""
        parser.add_argument("--apply", action="store_true", help="Write converted content (default: dry run).")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Also process content containing no HTML elements; normally it is treated as already Markdown.",
        )

    def handle(self, **options) -> None:  # noqa: ANN003
        """Audit or convert posts without changing their timestamps."""
        converted = 0
        skipped = 0

        with transaction.atomic():
            for post in Post.admin_objects.all().iterator():
                label = f"Post {post.pk} ({post.title or 'untitled'})"
                tags = html_tags(post.content)
                if not tags and not options["force"]:
                    self.stdout.write(f"{label}: skipped — no HTML elements found")
                    skipped += 1
                    continue

                markdown = html_to_markdown(post.content)
                warnings = unsupported_tags(post.content)
                note = f"; review preserved HTML tags: {', '.join(sorted(warnings))}" if warnings else ""
                if options["apply"]:
                    Post.admin_objects.filter(pk=post.pk).update(content=markdown)
                    self.stdout.write(f"{label}: converted{note}")
                else:
                    self.stdout.write(f"{label}: would convert{note}")
                converted += 1

            if not options["apply"]:
                transaction.set_rollback(True)

        summary = f"{converted} converted, {skipped} skipped"
        if options["apply"]:
            if converted:
                # QuerySet.update() bypasses DJ Press's post-save cache clear.
                cache.delete(PUBLISHED_POSTS_CACHE_KEY)
            self.stdout.write(self.style.SUCCESS(summary))
            self.stdout.write(
                "Now restore DJ Press's Markdown CONTENT_RENDERER and remove DJPRESS_TIPTAP_STORAGE_FORMAT "
                "(or set it to 'markdown')."
            )
        else:
            self.stdout.write(
                f"Dry run ({summary}): no changes written. Re-run with --apply after backing up the database."
            )
