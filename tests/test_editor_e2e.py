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
from django.test import Client
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
    """Log the browser in before each test: the example site's views all require login.

    force_login() writes a session row into the test database the live server
    reads from; handing its cookie to Playwright's context authenticates every
    page the test opens.
    """
    user = django_user_model.objects.create_user(username="author", password="secret")
    client = Client()
    client.force_login(user)
    context.add_cookies(
        [{"name": "sessionid", "value": client.cookies["sessionid"].value, "url": live_server.url}]
    )


@pytest.fixture(autouse=True)
def page_errors(page):
    """Collect uncaught page errors in every test — a broken bundle should fail loudly."""
    errors = []
    page.on("pageerror", lambda err: errors.append(err.message))
    yield errors
    assert errors == []


def editor_html(page):
    """The editor's stored HTML (what the form field will submit)."""
    return page.evaluate("document.querySelector('djpress-tiptap-editor').editor.getHTML()")


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
    page.click(f"text={title}")

    # highlight.js on the public page tokenises the stored language-js block
    code = page.locator(".post-content pre code.language-js")
    expect(code).to_have_class(re.compile("hljs"))
    expect(code.locator(".hljs-keyword").first).to_have_text("const")
    expect(code.locator(".hljs-string").first).to_have_text('"hello"')


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


def test_tables_survive_the_round_trip_to_the_public_post_page(page):
    title = f"pw-test table {time.time_ns()}"

    page.goto("/add/")
    page.fill("input[name=title]", title)
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.get_by_role("button", name="InsertTable", exact=True).click()
    page.keyboard.type("Header cell")  # cursor is in the first header cell

    page.click("input[type=submit]")
    page.wait_for_url("/")
    page.click(f"text={title}")

    table = page.locator(".post-content table")
    expect(table).to_be_visible()
    expect(table.locator("tr")).to_have_count(3)
    expect(table.locator("th").first).to_have_text("Header cell")


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


def test_form_submits_the_editors_html_and_round_trips_it(page):
    title = f"pw-test {time.time_ns()}"

    page.goto("/add/")
    page.fill("input[name=title]", title)
    page.locator("djpress-tiptap-editor .tiptap").click()
    page.keyboard.type("Round trip works")

    page.click("input[type=submit]")
    page.wait_for_url("/")

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
    assert editor_html(page) == (
        '<p>Intro</p><div data-type="more">Read more</div><p>Rest of the post</p>'
    )


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

    # The example page's raw echo (unescaped Django auto-escaping, so this
    # renders as literal visible text) proves the *stored* value is the real
    # `<!--more-->` comment DJ Press looks for, not the editor's sentinel node.
    expect(page.locator("div[style*='monospace']")).to_contain_text("<!--more-->")

    # Reopening the form restores the marker as an editable node again
    page.click("text=edit")
    expect(page.locator('.tiptap div[data-type="more"]')).to_have_text("Read more")
    assert "<!--more-->" not in editor_html(page)
