"""Tests for the reversible HTML-to-Markdown upgrade path."""

import io
import time

import pytest
from django.core.management import call_command
from djpress.models import Post

from djpress_tiptap.conversion import html_to_markdown

pytestmark = pytest.mark.django_db


@pytest.fixture
def author(django_user_model):
    return django_user_model.objects.create_user(username="markdown-author", password="secret")


def make_post(author, content):
    return Post.objects.create(
        title=f"markdown conversion {time.time_ns()}",
        content=content,
        author=author,
        status="published",
    )


def convert(*args):
    output = io.StringIO()
    call_command("djpress_tiptap_convert_to_markdown", *args, stdout=output)
    return output.getvalue()


def test_converts_the_editor_schema_to_markdown():
    html = (
        "<h2>Hello</h2><p>Some <strong>bold</strong>, <em>italic</em>, <s>deleted</s> and "
        '<a href="/about/" title="About">linked</a> text.</p>'
        '<pre><code class="language-python">print("hello")</code></pre>'
    )
    assert html_to_markdown(html) == (
        '## Hello\n\nSome **bold**, *italic*, <del>deleted</del> and [linked](/about/ "About") text.\n\n'
        '```python\nprint("hello")\n```'
    )


def test_preserves_more_and_lossless_html_escape_hatches():
    html = (
        "<p>Intro</p><!--more--><p>Rest</p>"
        '<img src="/photo.png" alt="Photo" width="640" height="480">'
        '<video src="/clip.mp4" controls="controls"></video>'
        '<table><tbody><tr><td colwidth="240"><p>Wide</p></td></tr></tbody></table>'
    )
    markdown = html_to_markdown(html)
    assert "<!--more-->" in markdown
    assert '<img src="/photo.png" alt="Photo" width="640" height="480">' in markdown
    assert '<video src="/clip.mp4" controls="controls"></video>' in markdown
    assert '<table><tbody><tr><td colwidth="240"><p>Wide</p></td></tr></tbody></table>' in markdown


def test_dry_run_does_not_write(author):
    post = make_post(author, "<h1>Hello</h1><p>Text</p>")
    output = convert()
    post.refresh_from_db()
    assert "would convert" in output
    assert "Dry run" in output
    assert post.content == "<h1>Hello</h1><p>Text</p>"


def test_apply_updates_without_touching_updated_at(author):
    post = make_post(author, "<h1>Hello</h1><p>Text</p>")
    updated_at = post.updated_at
    output = convert("--apply")
    post.refresh_from_db()
    assert "converted" in output
    assert post.content == "# Hello\n\nText"
    assert post.updated_at == updated_at


def test_already_markdown_content_is_skipped(author):
    post = make_post(author, "# Already Markdown")
    output = convert("--apply")
    post.refresh_from_db()
    assert "skipped" in output
    assert post.content == "# Already Markdown"


def test_unsupported_tags_are_preserved_and_reported(author):
    post = make_post(author, '<p>Before</p><iframe src="/embed"></iframe>')
    output = convert("--apply")
    post.refresh_from_db()
    assert "review preserved HTML tags: iframe" in output
    assert '<iframe src="/embed"></iframe>' in post.content
