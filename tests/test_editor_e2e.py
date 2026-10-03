"""End-to-end tests of the editor in a real browser.

Playwright (via pytest-playwright) drives Chromium against pytest-django's
live_server, exercising the built JS bundle through the example project's
pages: run `just build` (vite) after changing frontend/src or these tests
will exercise the stale bundle.

Marked e2e: deselect with `pytest -m "not e2e"` for a fast Python-only run.
"""

import base64
import os
import re
import time
from pathlib import Path

import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from djpress.models import Post
from playwright.sync_api import expect

# Playwright's sync API drives an asyncio loop in this thread; Django's ORM
# refuses to run next to one unless told otherwise. Safe here: the tests are
# fully synchronous, the loop belongs to Playwright.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.e2e

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def browser_context_args(browser_context_args, live_server):
    """Point relative page.goto() URLs at the live Django server."""
    return {**browser_context_args, "base_url": live_server.url}


@pytest.fixture(autouse=True)
def authenticated_browser(context, live_server, django_user_model):
    """Log in an author who can use the site's views and upload media.

    force_login() writes a session row into the test database the live server
    reads from; handing its cookie to Playwright's context authenticates every
    page the test opens.
    """
    user = django_user_model.objects.create_user(username="author", password="secret")
    permission = Permission.objects.get(content_type__app_label="djpress", codename="add_media")
    user.user_permissions.add(permission)
    client = Client()
    client.force_login(user)
    context.add_cookies([{"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}])


@pytest.fixture(autouse=True)
def page_errors(page):
    """Collect uncaught page errors in every test — a broken bundle should fail loudly."""
    errors = []
    page.on("pageerror", lambda err: errors.append(err.message))
    yield errors
    assert errors == []


def editor_html(page):
    """The editor's internal HTML, useful for asserting its visible schema."""
    return page.evaluate("document.querySelector('djpress-tiptap-editor').editor.getHTML()")


def editor_markdown(page):
    """The canonical value the form control submits in the default mode."""
    return page.evaluate("document.querySelector('djpress-tiptap-editor').editor.getMarkdown()")


def upload_fixture(page, filename):
    """Insert an image through the toolbar upload button's file chooser.

    The dynamically created <input type=file> still fires filechooser.
    """
    with page.expect_file_chooser() as chooser_info:
        page.get_by_role("button", name="UploadImage", exact=True).click()
    chooser_info.value.set_files(FIXTURES / filename)


def test_editor_and_toolbar_mount_on_the_add_post_page(page):
    page.goto("/add/")

    expect(page.locator("djpress-tiptap-editor .tiptap")).to_be_visible()
    expect(page.locator("[data-djpress-tiptap-toolbar]")).to_be_visible()

    # Undo is disabled until something has been typed
    expect(page.get_by_role("button", name="Undo")).to_be_disabled()


# Marks (inline formatting) need a text selection, so these cases type,
# select all, then click the toolbar button.
@pytest.mark.parametrize(
    ("button", "html"),
    [
        ("Bold", "<p><strong>Hello world</strong></p>"),
        ("Italic", "<p><em>Hello world</em></p>"),
        ("Strike", "<p><s>Hello world</s></p>"),
        ("Underline", "<p><u>Hello world</u></p>"),
        ("Code", "<p><code>Hello world</code></p>"),
    ],
)
def test_toolbar_mark_formats_the_selected_text(page, button, html):
    page.goto("/add/")

    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("Hello world")
    page.keyboard.press("ControlOrMeta+a")

    btn = page.get_by_role("button", name=button, exact=True)
    btn.click()
    expect(btn).to_have_class(re.compile("is-active"))

    assert editor_html(page) == html


def test_underline_uses_portable_html_inside_markdown(page):
    page.goto("/add/")
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("Underlined")
    page.keyboard.press("ControlOrMeta+a")
    page.get_by_role("button", name="Underline", exact=True).click()

    assert editor_markdown(page) == "<u>Underlined</u>"


def test_strikethrough_uses_portable_del_html_and_renders_publicly(page):
    title = f"pw-test strike {time.time_ns()}"

    page.goto("/add/")
    page.fill("input[name=title]", title)
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("Deleted")
    page.keyboard.press("ControlOrMeta+a")
    page.get_by_role("button", name="Strike", exact=True).click()

    assert editor_markdown(page) == "<del>Deleted</del>"

    page.click("input[type=submit]")
    page.wait_for_url("/")
    assert Post.objects.get(title=title).content == "<del>Deleted</del>"

    page.click(f"text={title}")
    expect(page.locator(".post-content del")).to_have_text("Deleted")


def test_existing_tilde_strikethrough_loads_and_resaves_as_del(page, django_user_model):
    author = django_user_model.objects.get(username="author")
    post = Post.objects.create(
        title=f"pw-test legacy strike {time.time_ns()}",
        content="Before ~~deleted~~ after",
        author=author,
        status="published",
    )

    page.goto(f"/{post.pk}/edit/")
    expect(page.locator(".tiptap s")).to_have_text("deleted")
    assert editor_markdown(page) == "Before <del>deleted</del> after"


def test_hard_break_toolbar_stores_markdown_hard_break(page):
    title = f"pw-test hard break {time.time_ns()}"

    page.goto("/add/")
    page.fill("input[name=title]", title)
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("First line")
    page.get_by_role("button", name="HardBreak", exact=True).click()
    page.keyboard.type("Second line")

    assert editor_html(page) == "<p>First line<br>Second line</p>"
    assert editor_markdown(page) == "First line  \nSecond line"

    page.click("input[type=submit]")
    page.wait_for_url("/")
    assert Post.objects.get(title=title).content == "First line  \nSecond line"

    page.click(f"text={title}")
    expect(page.locator(".post-content br")).to_have_count(1)
    expect(page.locator(".post-content p")).to_have_text("First line\nSecond line")


# Node-level commands restructure the block that contains the cursor — no
# selection needed (and select-all would break the active check: StarterKit's
# TrailingNode keeps an empty trailing <p> after a non-paragraph last block,
# and a node only reports active if it covers the whole selection).
@pytest.mark.parametrize(
    ("button", "html"),
    [
        ("H1", "<h1>Hello world</h1><p></p>"),
        ("H2", "<h2>Hello world</h2><p></p>"),
        ("H3", "<h3>Hello world</h3><p></p>"),
        ("Blockquote", "<blockquote><p>Hello world</p></blockquote><p></p>"),
        ("BulletList", "<ul><li><p>Hello world</p></li></ul><p></p>"),
        ("OrderedList", "<ol><li><p>Hello world</p></li></ol><p></p>"),
        ("CodeBlock", "<pre><code>Hello world</code></pre><p></p>"),
    ],
)
def test_toolbar_node_formats_the_current_block(page, button, html):
    page.goto("/add/")

    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("Hello world")

    btn = page.get_by_role("button", name=button, exact=True)
    btn.click()
    expect(btn).to_have_class(re.compile("is-active"))

    assert editor_html(page) == html


def test_code_blocks_get_lowlight_syntax_highlighting(page):
    page.goto("/add/")

    page.locator("djpress-tiptap-editor .tiptap").click()
    # The ``` input rule converts the paragraph into a code block with language js
    page.keyboard.type("```js ")
    page.keyboard.type('const greeting = "hello";')

    # lowlight decorates tokens with hljs-* spans inside the editor view
    expect(page.locator(".tiptap pre .hljs-keyword").first).to_have_text("const")
    expect(page.locator(".tiptap pre .hljs-string").first).to_have_text('"hello"')

    # The stored HTML keeps the language but not the decoration spans
    assert editor_html(page) == '<pre><code class="language-js">const greeting = "hello";</code></pre><p></p>'


def test_published_code_blocks_are_highlighted_on_the_public_post_page(page):
    title = f"pw-test hljs {time.time_ns()}"

    page.goto("/add/")
    page.fill("input[name=title]", title)
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("```js ")
    page.keyboard.type('const greeting = "hello";')

    page.click("input[type=submit]")
    page.wait_for_url("/")
    assert Post.objects.get(title=title).content == '```js\nconst greeting = "hello";\n```'
    page.click(f"text={title}")

    # highlight.js on the public page tokenises the stored language-js block
    code = page.locator(".post-content pre code.language-js")
    expect(code).to_have_class(re.compile("hljs"))
    expect(code.locator(".hljs-keyword").first).to_have_text("const")
    expect(code.locator(".hljs-string").first).to_have_text('"hello"')


def test_code_block_language_can_be_set_changed_and_cleared(page):
    title = f"pw-test code language {time.time_ns()}"
    page.goto("/add/")
    page.fill("input[name=title]", title)
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("``` ")
    page.keyboard.type('print("Hello, world")')

    language = page.get_by_role("combobox", name="Code block language")
    expect(language).to_have_value("")
    language.select_option("python")
    assert editor_markdown(page).strip() == '```python\nprint("Hello, world")\n```'
    expect(page.locator(".tiptap pre .hljs-built_in").first).to_have_text("print")

    # Undo/redo must update the visible selector as well as the document.
    page.get_by_role("button", name="Undo", exact=True).click()
    expect(language).to_have_value("")
    page.get_by_role("button", name="Redo", exact=True).click()
    expect(language).to_have_value("python")

    language.select_option("javascript")
    assert editor_markdown(page).startswith("```javascript\n")
    language.select_option("")
    assert editor_markdown(page).strip() == '```\nprint("Hello, world")\n```'
    language.select_option("python")
    # The code remains editable after interacting with the dropdown.
    page.locator(".tiptap pre code").click()
    page.keyboard.press("End")
    page.keyboard.type(" # edited")
    page.click("input[type=submit]")
    page.wait_for_url("/")
    post = Post.objects.get(title=title)
    assert post.content == '```python\nprint("Hello, world") # edited\n```'
    page.goto(f"/{post.pk}/edit/")
    expect(page.get_by_role("combobox", name="Code block language")).to_have_value("python")
    assert "select" not in editor_html(page)


def test_code_block_dropdown_targets_its_own_block_and_preserves_fence_labels(page):
    page.goto("/add/")
    page.evaluate("""() => document.querySelector('djpress-tiptap-editor').editor.commands.setContent(
        '```js\\nconst first = 1;\\n```\\n\\n```custom-language\\nsecond\\n```',
        { contentType: 'markdown' }
    )""")
    languages = page.get_by_role("combobox", name="Code block language")
    expect(languages).to_have_count(2)
    expect(languages.nth(0)).to_have_value("js")
    expect(languages.nth(1)).to_have_value("custom-language")
    # Leave the caret in the first block, then change the second block.
    page.locator(".tiptap pre code").first.click()
    languages.nth(1).select_option("python")
    assert editor_markdown(page).strip() == "```js\nconst first = 1;\n```\n\n```python\nsecond\n```"
    expect(languages.nth(0)).to_have_value("js")


def test_image_command_inserts_an_image_from_the_prompted_url(page):
    # 1x1 transparent gif: keeps the test off the network entirely
    src = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"

    page.goto("/add/")
    page.locator("djpress-tiptap-editor .tiptap").click()

    # window.prompt() blocks the page; answer it before triggering it
    page.on("dialog", lambda dialog: dialog.accept(src))
    page.get_by_role("button", name="Image", exact=True).click()

    expect(page.locator(".tiptap img")).to_have_attribute("src", src)

    assert editor_html(page) == f'<img src="{src}"><p></p>'


def test_upload_button_uploads_the_chosen_file_and_inserts_the_served_image(page):
    page.goto("/add/")
    page.locator("djpress-tiptap-editor .tiptap").click()

    upload_fixture(page, "pixel.png")

    # src points at the Django-served attachment; the server sets alt to the filename
    img = page.locator(".tiptap img")
    expect(img).to_have_attribute("src", re.compile(r"/media/djpress/\d{4}/\d{2}/\d{2}/pixel.*\.png"))
    expect(img).to_have_attribute("alt", "pixel.png")


# Real drag-and-drop needs OS-level input, so the drop/paste tests dispatch
# synthetic events whose DataTransfer carries a File built from the fixture.
def test_dropping_an_image_file_uploads_it_and_inserts_it(page):
    page.goto("/add/")

    surface = page.locator("djpress-tiptap-editor .tiptap")
    box = surface.bounding_box()
    surface.evaluate(
        """(el, { b64, x, y }) => {
            const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(new File([bytes], "dropped.png", { type: "image/png" }));
            el.dispatchEvent(
                new DragEvent("drop", { clientX: x, clientY: y, dataTransfer, bubbles: true, cancelable: true }),
            );
        }""",
        {
            "b64": base64.b64encode((FIXTURES / "pixel.png").read_bytes()).decode(),
            "x": box["x"] + 20,
            "y": box["y"] + 20,
        },
    )

    img = page.locator(".tiptap img")
    expect(img).to_have_attribute("src", re.compile(r"/media/djpress/\d{4}/\d{2}/\d{2}/dropped.*\.png"))
    expect(img).to_have_attribute("alt", "dropped.png")


def test_pasting_an_image_file_uploads_it_and_inserts_it(page):
    page.goto("/add/")
    page.locator("djpress-tiptap-editor .tiptap").click()

    page.locator("djpress-tiptap-editor .tiptap").evaluate(
        """(el, b64) => {
            const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
            const clipboardData = new DataTransfer();
            clipboardData.items.add(new File([bytes], "pasted.png", { type: "image/png" }));
            el.dispatchEvent(
                new ClipboardEvent("paste", { clipboardData, bubbles: true, cancelable: true }),
            );
        }""",
        base64.b64encode((FIXTURES / "pixel.png").read_bytes()).decode(),
    )

    img = page.locator(".tiptap img")
    expect(img).to_have_attribute("src", re.compile(r"/media/djpress/\d{4}/\d{2}/\d{2}/pasted.*\.png"))
    expect(img).to_have_attribute("alt", "pasted.png")


def test_video_command_inserts_a_video_from_the_prompted_url(page):
    src = "/media/somewhere/clip.mp4"

    page.goto("/add/")
    page.locator("djpress-tiptap-editor .tiptap").click()

    # window.prompt() blocks the page; answer it before triggering it
    page.on("dialog", lambda dialog: dialog.accept(src))
    page.get_by_role("button", name="Video", exact=True).click()

    video = page.locator(".tiptap video")
    expect(video).to_have_attribute("src", src)
    # The stored element must be playable on the public page without JS
    expect(video).to_have_attribute("controls", "controls")

    assert editor_html(page) == f'<video src="{src}" controls="controls" preload="metadata"></video><p></p>'
    assert editor_markdown(page).strip() == f'<video src="{src}" controls="controls" preload="metadata"></video>'


def test_video_upload_button_uploads_the_chosen_file_and_inserts_a_video_element(page):
    page.goto("/add/")
    page.locator("djpress-tiptap-editor .tiptap").click()

    # clip.mp4 is a bare ftyp header — enough for the server's magic-byte
    # check, and the <video> element renders without needing playable media
    with page.expect_file_chooser() as chooser_info:
        page.get_by_role("button", name="UploadVideo", exact=True).click()
    chooser_info.value.set_files(FIXTURES / "clip.mp4")

    video = page.locator(".tiptap video")
    expect(video).to_have_attribute("src", re.compile(r"/media/djpress/\d{4}/\d{2}/\d{2}/clip.*\.mp4"))
    # The server-side alt text (the filename) lands on title: <video> has no alt
    expect(video).to_have_attribute("title", "clip.mp4")


def test_dropping_a_video_file_uploads_it_and_inserts_a_video_element(page):
    page.goto("/add/")

    surface = page.locator("djpress-tiptap-editor .tiptap")
    box = surface.bounding_box()
    surface.evaluate(
        """(el, { b64, x, y }) => {
            const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(new File([bytes], "dropped.mp4", { type: "video/mp4" }));
            el.dispatchEvent(
                new DragEvent("drop", { clientX: x, clientY: y, dataTransfer, bubbles: true, cancelable: true }),
            );
        }""",
        {
            "b64": base64.b64encode((FIXTURES / "clip.mp4").read_bytes()).decode(),
            "x": box["x"] + 20,
            "y": box["y"] + 20,
        },
    )

    video = page.locator(".tiptap video")
    expect(video).to_have_attribute("src", re.compile(r"/media/djpress/\d{4}/\d{2}/\d{2}/dropped.*\.mp4"))


def test_videos_survive_the_round_trip_to_the_public_post_page(page):
    title = f"pw-test video {time.time_ns()}"

    page.goto("/add/")
    page.fill("input[name=title]", title)
    page.locator("djpress-tiptap-editor .tiptap").click()
    with page.expect_file_chooser() as chooser_info:
        page.get_by_role("button", name="UploadVideo", exact=True).click()
    chooser_info.value.set_files(FIXTURES / "clip.mp4")
    expect(page.locator(".tiptap video")).to_be_visible()
    # The freshly inserted node is selected (same as images); typing now
    # would replace it, so step off it first
    page.keyboard.press("ArrowRight")
    page.keyboard.type("Watch this:")

    page.click("input[type=submit]")
    page.wait_for_url("/")
    page.click(f"text={title}")

    video = page.locator(".post-content video")
    expect(video).to_be_visible()
    expect(video).to_have_attribute("controls", "controls")
    expect(video).to_have_attribute("src", re.compile(r"/media/djpress/\d{4}/\d{2}/\d{2}/clip.*\.mp4"))


# Existing sites have hand-written <video> markup using <source> children
# (webm + mp4 fallback) rather than a src attribute. editor.getHTML() is the
# form value, so whatever the editor drops is destroyed on the next save even
# if the user never touches the video block. The contract: a lone <source>
# collapses into the canonical src-attribute form (same shape as uploaded
# videos; presentational attributes like width are theme CSS's job), but
# multiple <source> children are the browser's format-fallback mechanism and
# must survive verbatim, in order.
def open_existing_post_in_editor(page, django_user_model, content):
    """Store `content` as a post's body and open it in the edit form's editor."""
    author = django_user_model.objects.get(username="author")
    post = Post.objects.create(
        title=f"pw-test video sources {time.time_ns()}",
        content=content,
        author=author,
        status="published",
    )
    page.goto(f"/{post.pk}/edit/")
    # Waits on the custom element, not .tiptap or to_be_visible: a broken-src
    # <video> can have a zero-size box, and a bundle crash during mount leaves
    # the ProseMirror div without its tiptap class — both would mask the real
    # assertion failures below with a timeout here.
    expect(page.locator("djpress-tiptap-editor video")).to_have_count(1)
    return post


def test_existing_video_with_a_single_source_child_collapses_to_the_src_attribute_form(page, django_user_model):
    post = open_existing_post_in_editor(
        page,
        django_user_model,
        """<video controls width="100%">
  <source src="/media/2026/07/18/example_video.webm" type="video/webm" />
</video>""",
    )

    expect(page.locator(".tiptap video")).to_have_attribute("src", "/media/2026/07/18/example_video.webm")

    # Initial content no longer gets a trailing paragraph before the first
    # editor transaction. Assert the video contract rather than that side effect.
    expected = '<video src="/media/2026/07/18/example_video.webm" controls="controls" preload="metadata"></video>'
    assert editor_html(page) == expected
    page.click("input[type=submit]")
    page.wait_for_url("/")
    post.refresh_from_db()
    assert post.content == expected

    # The trailing paragraph is still available once editing begins, so an
    # existing post ending in video can be extended normally.
    page.goto(f"/{post.pk}/edit/")
    page.evaluate("""() => document.querySelector('djpress-tiptap-editor').editor
        .chain().focus().setNodeSelection(0).run()""")
    page.locator(".tiptap p").click()
    page.keyboard.type("After the video")
    expect(page.locator(".tiptap p")).to_have_text("After the video")


def test_existing_video_with_multiple_source_children_keeps_every_source(page, django_user_model):
    post = open_existing_post_in_editor(
        page,
        django_user_model,
        """<video controls width="100%">
  <source src="/media/2026/07/18/example_video.webm" type="video/webm" />
  <source src="/media/2026/07/18/example_video.mp4" type="video/mp4" />
</video>""",
    )

    # Both sources survive in order: browsers pick the first playable one, so
    # dropping the mp4 breaks playback wherever webm isn't supported
    sources = page.locator(".tiptap video source")
    expect(sources).to_have_count(2)
    expect(sources.nth(0)).to_have_attribute("src", "/media/2026/07/18/example_video.webm")
    expect(sources.nth(0)).to_have_attribute("type", "video/webm")
    expect(sources.nth(1)).to_have_attribute("src", "/media/2026/07/18/example_video.mp4")
    expect(sources.nth(1)).to_have_attribute("type", "video/mp4")

    expected = (
        '<video controls="controls" preload="metadata">'
        '<source src="/media/2026/07/18/example_video.webm" type="video/webm">'
        '<source src="/media/2026/07/18/example_video.mp4" type="video/mp4">'
        "</video>"
    )
    assert editor_html(page) == expected
    page.click("input[type=submit]")
    page.wait_for_url("/")
    post.refresh_from_db()
    assert post.content == expected


def test_dragging_a_corner_handle_resizes_the_image_and_stores_width_height(page):
    page.goto("/add/")
    page.locator("djpress-tiptap-editor .tiptap").click()

    # Insert a 300x200 image via the upload button
    upload_fixture(page, "photo.png")
    img = page.locator(".tiptap img")
    expect(img).to_have_attribute("src", re.compile(r"photo.*\.png"))

    # Select the image so the corner handles appear, then drag bottom-right
    img.click()
    handle = page.locator('.tiptap [data-resize-handle="bottom-right"]')
    box = handle.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + 60, box["y"] + 40, steps=5)
    page.mouse.up()

    # The new size is committed as width/height attributes in the stored HTML,
    # with the 300:200 aspect ratio preserved (alwaysPreserveAspectRatio).
    match = re.search(r'width="(\d+)" height="(\d+)"', editor_html(page))
    width, height = int(match.group(1)), int(match.group(2))
    assert width > 300
    assert height == round(width * (200 / 300))
    assert re.search(r'<img [^>]*width="\d+" height="\d+">', editor_markdown(page))


def test_media_library_dialog_inserts_a_previously_uploaded_image(page):
    page.goto("/add/")
    page.locator("djpress-tiptap-editor .tiptap").click()

    # Seed the library through the upload button
    upload_fixture(page, "pixel.png")
    expect(page.locator(".tiptap img")).to_have_count(1)

    # On a fresh form, insert the same image from the library instead
    page.goto("/add/")
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.get_by_role("button", name="BrowseImages", exact=True).click()

    dialog = page.locator("dialog.djpress-tiptap-browser")
    expect(dialog.locator("h2")).to_have_text("Media library")
    dialog.locator("[data-image-url]").first.click()

    expect(page.locator(".tiptap img")).to_have_attribute(
        "src",
        re.compile(r"/media/djpress/\d{4}/\d{2}/\d{2}/pixel.*\.png"),
    )
    expect(page.locator(".tiptap img")).to_have_attribute("alt", "pixel.png")
    # Closing removes the dialog element entirely (fresh one per open)
    expect(page.locator("dialog.djpress-tiptap-browser")).to_have_count(0)


def test_media_library_dialog_closes_without_inserting_anything(page):
    page.goto("/add/")
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.get_by_role("button", name="BrowseImages", exact=True).click()

    dialog = page.locator("dialog.djpress-tiptap-browser")
    expect(dialog).to_be_visible()
    dialog.get_by_role("button", name="Close").click()

    expect(page.locator("dialog.djpress-tiptap-browser")).to_have_count(0)
    expect(page.locator(".tiptap img")).to_have_count(0)


def test_insert_table_creates_a_3x3_grid_and_enables_the_table_commands(page):
    page.goto("/add/")

    # The table group is contextual: hidden until the cursor is inside a table
    table_group = page.locator("[data-context-group]")
    expect(table_group).to_be_hidden()

    page.locator("djpress-tiptap-editor .tiptap").click()
    page.get_by_role("button", name="InsertTable", exact=True).click()

    expect(page.locator(".tiptap table")).to_be_visible()
    expect(page.locator(".tiptap tr")).to_have_count(3)
    expect(page.locator(".tiptap th")).to_have_count(3)  # header row
    expect(page.locator(".tiptap td")).to_have_count(6)  # 2 body rows

    # The cursor landed inside the new table, so the group appears ready to use
    expect(table_group).to_be_visible()
    expect(page.get_by_role("button", name="DeleteRow", exact=True)).to_be_enabled()


def test_table_rows_and_columns_can_be_added_and_removed(page):
    page.goto("/add/")
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.get_by_role("button", name="InsertTable", exact=True).click()

    page.get_by_role("button", name="AddRowAfter", exact=True).click()
    expect(page.locator(".tiptap tr")).to_have_count(4)

    page.get_by_role("button", name="AddColAfter", exact=True).click()
    expect(page.locator(".tiptap th")).to_have_count(4)
    expect(page.locator(".tiptap td")).to_have_count(12)

    page.get_by_role("button", name="DeleteRow", exact=True).click()
    expect(page.locator(".tiptap tr")).to_have_count(3)

    page.get_by_role("button", name="DeleteTable", exact=True).click()
    expect(page.locator(".tiptap table")).to_have_count(0)


def test_table_columns_can_be_resized_by_dragging_and_the_width_persists(page):
    page.goto("/add/")
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.get_by_role("button", name="InsertTable", exact=True).click()

    # Drag the right border of the first header cell 60px to the right
    cell = page.locator(".tiptap th").first
    box = cell.bounding_box()
    border_x = box["x"] + box["width"]
    border_y = box["y"] + box["height"] / 2

    page.mouse.move(border_x, border_y)
    page.mouse.down()
    page.mouse.move(border_x + 60, border_y, steps=5)
    page.mouse.up()

    # The dragged width is stored on the column's cells and survives serialization
    assert re.search(r'colwidth="\d+"', editor_html(page))
    # GFM has no column-width syntax, so a resized table intentionally uses
    # Markdown's raw-HTML escape hatch rather than losing the dimensions.
    assert "<table" in editor_markdown(page)


def test_tables_survive_the_round_trip_to_the_public_post_page(page):
    title = f"pw-test table {time.time_ns()}"

    page.goto("/add/")
    page.fill("input[name=title]", title)
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.get_by_role("button", name="InsertTable", exact=True).click()
    page.keyboard.type("Header cell")  # cursor is in the first header cell

    page.click("input[type=submit]")
    page.wait_for_url("/")
    stored = Post.objects.get(title=title).content
    assert "| Header cell" in stored
    assert "<table" not in stored
    page.click(f"text={title}")

    table = page.locator(".post-content table")
    expect(table).to_be_visible()
    expect(table.locator("tr")).to_have_count(3)
    expect(table.locator("th").first).to_have_text("Header cell")


def test_resized_table_widths_survive_a_saved_markdown_round_trip(page, django_user_model):
    author = django_user_model.objects.get(username="author")
    post = Post.objects.create(
        title=f"pw-test table widths {time.time_ns()}",
        content=(
            '<table><tbody><tr><th colspan="1" rowspan="1" colwidth="240">'
            "<p>Wide</p></th></tr></tbody></table>"
        ),
        author=author,
        status="published",
    )

    page.goto(f"/{post.pk}/edit/")
    expect(page.locator(".tiptap th")).to_have_attribute("colwidth", "240")
    page.locator(".tiptap th").click()
    page.keyboard.press("End")
    page.keyboard.type(" cell")
    page.click("input[type=submit]")
    page.wait_for_url("/")

    post.refresh_from_db()
    assert "<table" in post.content
    assert 'colwidth="240"' in post.content

    page.goto(f"/{post.pk}/edit/")
    expect(page.locator(".tiptap th")).to_have_attribute("colwidth", "240")
    expect(page.locator(".tiptap th")).to_contain_text("Wide cell")


def test_empty_editor_shows_a_placeholder_that_never_reaches_the_stored_html(page):
    page.goto("/add/")

    placeholder = page.locator(".tiptap p.is-editor-empty")
    expect(placeholder).to_have_attribute("data-placeholder", "Write something…")

    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("Hello")
    expect(placeholder).to_have_count(0)

    assert editor_html(page) == "<p>Hello</p>"


def test_editor_and_public_page_compute_identical_content_typography(page):
    title = f"pw-test parity {time.time_ns()}"

    def style(locator, prop):
        return locator.evaluate("(el, p) => getComputedStyle(el)[p]", prop)

    page.goto("/add/")
    page.fill("input[name=title]", title)
    page.evaluate(
        """() => {
            document
                .querySelector("djpress-tiptap-editor")
                .editor.commands.setContent("<blockquote><p>Wisdom</p></blockquote><p>Inline <code>chip</code> text</p>");
        }"""  # noqa: E501
    )
    # setContent doesn't count as an update; one real keystroke syncs the form value
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.press("End")
    page.keyboard.type(".")

    editor_styles = {
        "quote_border": style(page.locator(".tiptap blockquote"), "borderLeftWidth"),
        "quote_color": style(page.locator(".tiptap blockquote"), "borderLeftColor"),
        "code_background": style(page.locator(".tiptap code"), "backgroundColor"),
    }
    assert editor_styles["quote_border"] == "3px"  # guard against comparing default-vs-default

    page.click("input[type=submit]")
    page.wait_for_url("/")
    page.click(f"text={title}")

    assert style(page.locator(".post-content blockquote"), "borderLeftWidth") == editor_styles["quote_border"]
    assert style(page.locator(".post-content blockquote"), "borderLeftColor") == editor_styles["quote_color"]
    assert style(page.locator(".post-content code"), "backgroundColor") == editor_styles["code_background"]


def test_typography_extension_smartens_punctuation_as_you_type(page):
    page.goto("/add/")

    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type('"Smart" -- yes... 1/2 (c) ->')

    assert editor_html(page) == "<p>“Smart” — yes… ½ © →</p>"


def test_undo_becomes_available_once_something_is_typed(page):
    page.goto("/add/")

    undo = page.get_by_role("button", name="Undo")
    expect(undo).to_be_disabled()

    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("Hello")
    expect(undo).to_be_enabled()

    undo.click()
    assert editor_html(page) == "<p></p>"


def test_form_submits_markdown_and_round_trips_it(page):
    title = f"pw-test {time.time_ns()}"

    page.goto("/add/")
    page.fill("input[name=title]", title)
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("Round trip works")

    page.click("input[type=submit]")
    page.wait_for_url("/")

    post = Post.objects.get(title=title)
    assert post.content == "Round trip works"

    # Reopen the saved post in the edit form: the widget must restore the value
    page.click(f"text={title}")
    expect(page.locator("h1")).to_have_text(title)
    expect(page.get_by_text("Round trip works").first).to_be_visible()


def test_read_more_button_inserts_a_marker_node(page):
    page.goto("/add/")

    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("Intro")
    page.get_by_role("button", name="ReadMore", exact=True).click()
    page.keyboard.type("Rest of the post")

    # In-editor it's a real (non-editable) node, not a raw HTML comment —
    # ProseMirror's DOM parser drops comment nodes, so a literal <!--more-->
    # couldn't survive being loaded back in. See more.js for the full story.
    expect(page.locator('.tiptap div[data-type="more"]')).to_have_text("Read more")
    assert editor_html(page) == ('<p>Intro</p><div data-type="more">Read more</div><p>Rest of the post</p>')
    assert editor_markdown(page) == "Intro\n\n<!--more-->\n\nRest of the post"


def test_read_more_marker_round_trips_as_a_real_html_comment(page):
    title = f"pw-test more {time.time_ns()}"

    page.goto("/add/")
    page.fill("input[name=title]", title)
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("Intro")
    page.get_by_role("button", name="ReadMore", exact=True).click()
    page.keyboard.type("Rest of the post")

    page.click("input[type=submit]")
    page.wait_for_url("/")
    page.click(f"text={title}")

    # The example page's raw echo (Django auto-escaping makes the comment
    # visible as literal text) proves the *stored* value is the real
    # `<!--more-->` comment DJ Press looks for, not the editor's sentinel node.
    expect(page.locator("pre[style*='monospace']")).to_contain_text("<!--more-->")

    # Reopening the form restores the marker as an editable node again
    page.click("text=edit")
    expect(page.locator('.tiptap div[data-type="more"]')).to_have_text("Read more")
    assert "<!--more-->" not in editor_html(page)


def test_more_text_inside_code_does_not_become_a_marker_node(page, django_user_model):
    author = django_user_model.objects.get(username="author")
    post = Post.objects.create(
        title=f"pw-test literal more {time.time_ns()}",
        content="Inline `<!--more-->`\n\n```html\n<!--more-->\n```",
        author=author,
        status="published",
    )

    page.goto(f"/{post.pk}/edit/")
    expect(page.locator('.tiptap div[data-type="more"]')).to_have_count(0)
    expect(page.locator(".tiptap code").first).to_contain_text("<!--more-->")
    expect(page.locator(".tiptap pre code")).to_contain_text("<!--more-->")


def test_legacy_html_mode_still_submits_html(page, settings):
    settings.DJPRESS_TIPTAP_STORAGE_FORMAT = "html"
    title = f"pw-test legacy html {time.time_ns()}"

    page.goto("/add/")
    page.fill("input[name=title]", title)
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("Legacy content")
    page.click("input[type=submit]")
    page.wait_for_url("/")

    assert Post.objects.get(title=title).content == "<p>Legacy content</p>"


def test_resized_image_dimensions_survive_a_saved_markdown_round_trip(page):
    title = f"pw-test image dimensions {time.time_ns()}"
    page.goto("/add/")
    page.fill("input[name=title]", title)
    page.locator("djpress-tiptap-editor .tiptap").click()
    upload_fixture(page, "photo.png")
    page.locator(".tiptap img").click()
    page.evaluate(
        """() => document.querySelector("djpress-tiptap-editor").editor.commands.updateAttributes(
            "image", { width: 640, height: 480 },
        )"""
    )
    page.click("input[type=submit]")
    page.wait_for_url("/")

    stored = Post.objects.get(title=title).content
    assert re.search(r'<img src="/media/.+photo[^\"]*\.png" alt="photo.png" width="640" height="480">', stored)

    page.click(f"text={title}")
    page.click("text=edit")
    # The resizable node view keeps dimensions in document attributes rather
    # than placing them directly on its live <img>; getHTML reflects the state.
    assert 'width="640" height="480"' in editor_html(page)
