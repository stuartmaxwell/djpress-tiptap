"""Tests for the HTML renderer and the djpress_tiptap_convert command.

The command converts a site's stored Markdown to HTML with the same Markdown
renderer that already produced its public pages, so the visible output is
unchanged. The example settings configure the pass-through HTML renderer, so
these tests point the command at djpress's Markdown renderer explicitly —
via the setting or the --renderer flag, both of which are exercised.
"""

import io
import time

import pytest
from django.core.management import CommandError, call_command
from djpress.models import Post

from djpress_tiptap.renderers import html_renderer

pytestmark = pytest.mark.django_db

MARKDOWN_RENDERER = "djpress.markdown_renderer.default_renderer"


def test_html_renderer_returns_content_unchanged():
    content = '<video controls src="/media/clip.mp4"></video>\n<p>Text & "quotes"</p>'
    assert html_renderer(content) == content


@pytest.fixture
def author(django_user_model):
    return django_user_model.objects.create_user(username="author", password="secret")


@pytest.fixture
def markdown_renderer_configured(settings):
    settings.DJPRESS_SETTINGS = {"CONTENT_RENDERER": MARKDOWN_RENDERER}


def make_post(author, content):
    return Post.objects.create(
        title=f"convert test {time.time_ns()}",
        content=content,
        author=author,
        status="published",
    )


def convert(*args):
    out, err = io.StringIO(), io.StringIO()
    call_command("djpress_tiptap_convert", *args, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


@pytest.mark.usefixtures("markdown_renderer_configured")
def test_dry_run_reports_but_writes_nothing(author):
    post = make_post(author, "# Hello\n\nSome *text*.")

    out, _ = convert()
    post.refresh_from_db()

    assert "would convert" in out
    assert "Dry run" in out
    assert post.content == "# Hello\n\nSome *text*."


@pytest.mark.usefixtures("markdown_renderer_configured")
def test_apply_converts_markdown_using_the_configured_renderer(author):
    post = make_post(author, "# Hello\n\nSome *text*.")
    updated_at_before = post.updated_at

    out, _ = convert("--apply")
    post.refresh_from_db()

    assert "converted" in out
    assert post.content == "<h1>Hello</h1>\n<p>Some <em>text</em>.</p>"
    # queryset.update() must not bump the auto_now timestamp: the conversion
    # is a storage-format change, not an edit.
    assert post.updated_at == updated_at_before


@pytest.mark.usefixtures("markdown_renderer_configured")
def test_content_that_already_looks_like_html_is_skipped(author):
    post = make_post(author, "<p>Already HTML</p>")

    out, _ = convert("--apply")
    post.refresh_from_db()

    assert "skipped" in out
    assert post.content == "<p>Already HTML</p>"


@pytest.mark.usefixtures("markdown_renderer_configured")
def test_force_converts_html_looking_content_too(author):
    post = make_post(author, "<p>Already HTML</p>")

    convert("--apply", "--force")
    post.refresh_from_db()

    assert post.content == "<p>Already HTML</p>"  # markdown passes the block through


@pytest.mark.usefixtures("markdown_renderer_configured")
def test_the_more_marker_survives_conversion(author):
    post = make_post(author, "Intro\n\n<!--more-->\n\nRest of the post")

    convert("--apply")
    post.refresh_from_db()

    assert "<!--more-->" in post.content
    assert "<p>Intro</p>" in post.content


@pytest.mark.usefixtures("markdown_renderer_configured")
def test_tags_outside_the_editor_schema_are_reported(author):
    make_post(author, 'Text\n\n<iframe src="https://example.com/embed"></iframe>')

    out, _ = convert()

    assert "iframe" in out
    assert "drop" in out


def test_refuses_to_run_against_the_html_renderer(author):
    # The example settings configure the pass-through renderer, so with no
    # override the command must refuse rather than silently convert nothing.
    make_post(author, "# Hello")

    with pytest.raises(CommandError, match="html_renderer"):
        call_command("djpress_tiptap_convert")


def test_renderer_flag_overrides_the_configured_renderer(author):
    # CONTENT_RENDERER stays the example settings' HTML renderer; the flag
    # supplies the Markdown renderer for sites that already switched.
    post = make_post(author, "# Hello")

    convert("--apply", "--renderer", MARKDOWN_RENDERER)
    post.refresh_from_db()

    assert post.content == "<h1>Hello</h1>"
