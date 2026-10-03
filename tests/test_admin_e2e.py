"""End-to-end tests of the Tiptap editor inside the Django admin.

The example project's website/admin.py re-registers djpress's PostAdmin with
DjTiptapWidget on the content field; the widget's Media class is what makes
the admin pull in the editor bundle. Same Playwright setup as
test_editor_e2e.py — see that module's docstring for the bundle-staleness
and e2e-marker notes.
"""

import os
import time

import pytest
from django.test import Client
from djpress.models import Post
from playwright.sync_api import expect

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def browser_context_args(browser_context_args, live_server):
    """Point relative page.goto() URLs at the live Django server."""
    return {**browser_context_args, "base_url": live_server.url}


@pytest.fixture(autouse=True)
def admin_browser(context, live_server, django_user_model):
    """Log the browser in as a superuser: the admin needs staff + model perms."""
    user = django_user_model.objects.create_superuser(username="boss", password="secret")
    client = Client()
    client.force_login(user)
    context.add_cookies([{"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}])
    return user


@pytest.fixture(autouse=True)
def page_errors(page):
    """Collect uncaught page errors in every test — a broken bundle should fail loudly."""
    errors = []
    page.on("pageerror", lambda err: errors.append(err.message))
    yield errors
    assert errors == []


def test_admin_add_post_page_mounts_the_editor_and_toolbar(page):
    page.goto("/admin/djpress/post/add/")

    expect(page.locator("djpress-tiptap-editor .tiptap")).to_be_visible()
    expect(page.locator("[data-djpress-tiptap-toolbar]")).to_be_visible()
    # The upload buttons appear: the superuser context has the endpoints configured
    expect(page.get_by_role("button", name="UploadImage", exact=True)).to_be_visible()


def test_a_post_written_in_the_admin_stores_markdown(page):
    title = f"pw-admin {time.time_ns()}"

    page.goto("/admin/djpress/post/add/")
    page.fill("#id_title", title)
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("Written in the admin")
    page.keyboard.press("ControlOrMeta+a")
    page.get_by_role("button", name="Bold", exact=True).click()

    page.click("input[name=_save]")
    page.wait_for_url("/admin/djpress/post/")

    post = Post.admin_objects.get(title=title)
    assert post.content == "**Written in the admin**"


def test_admin_code_block_language_selector_saves_markdown(page, admin_browser):
    post = Post.objects.create(
        title=f"pw-admin code language {time.time_ns()}",
        content='```js\nconst greeting = "hello";\n```',
        author=admin_browser,
        status="published",
    )
    page.goto(f"/admin/djpress/post/{post.pk}/change/")
    language = page.get_by_role("combobox", name="Code block language")
    expect(language).to_be_visible()
    expect(language).to_have_value("js")
    language.select_option("javascript")
    page.click("input[name=_save]")
    page.wait_for_url("/admin/djpress/post/")
    post.refresh_from_db()
    assert post.content == '```javascript\nconst greeting = "hello";\n```'


def test_admin_change_page_round_trips_a_multi_source_video(page, admin_browser):
    # The multi-source markup from test_editor_e2e must survive the admin's
    # edit form the same way it survives the example site's own form.
    post = Post.objects.create(
        title=f"pw-admin video {time.time_ns()}",
        content='<video controls="controls" preload="metadata">'
        '<source src="/media/2026/07/18/example_video.webm" type="video/webm">'
        '<source src="/media/2026/07/18/example_video.mp4" type="video/mp4">'
        "</video>",
        author=admin_browser,
        status="published",
    )

    page.goto(f"/admin/djpress/post/{post.pk}/change/")

    sources = page.locator(".tiptap video source")
    expect(sources).to_have_count(2)

    page.click("input[name=_save]")
    page.wait_for_url("/admin/djpress/post/")

    post.refresh_from_db()
    assert post.content == (
        '<video controls="controls" preload="metadata">'
        '<source src="/media/2026/07/18/example_video.webm" type="video/webm">'
        '<source src="/media/2026/07/18/example_video.mp4" type="video/mp4">'
        "</video>"
    )
