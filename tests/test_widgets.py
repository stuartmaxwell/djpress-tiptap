"""Tests for DjTiptapWidget rendering.

With nothing configured the widget now points at the bundled djpress_tiptap
upload/browse views, so the toolbar buttons render out of the box. Setting
DJPRESS_TIPTAP_UPLOAD_URL / DJPRESS_TIPTAP_BROWSE_URL to None or "" disables
the corresponding buttons, and the widget must still render in every
configuration state (the old NoReverseMatch regression).
"""

import pytest

from djpress_tiptap.widgets import DjTiptapWidget

pytestmark = pytest.mark.urls("config.urls")

UPLOAD_BUTTON = 'data-command="uploadImage"'
BROWSE_BUTTON = 'data-command="browseImages"'
VIDEO_UPLOAD_BUTTON = 'data-command="uploadVideo"'


def test_default_configuration_renders_buttons_for_the_bundled_views():
    html = DjTiptapWidget().render("body", "")
    assert UPLOAD_BUTTON in html
    assert BROWSE_BUTTON in html
    assert VIDEO_UPLOAD_BUTTON in html
    assert 'data-upload-url="/media/upload/"' in html
    assert 'data-browse-url="/media/browse/"' in html
    assert 'data-storage-format="markdown"' in html


def test_configured_url_names_are_resolved(settings):
    settings.DJPRESS_TIPTAP_UPLOAD_URL = "djpress_tiptap:media_upload"
    settings.DJPRESS_TIPTAP_BROWSE_URL = "djpress_tiptap:media_browse"
    html = DjTiptapWidget().render("body", "")
    assert UPLOAD_BUTTON in html
    assert BROWSE_BUTTON in html
    assert VIDEO_UPLOAD_BUTTON in html
    assert 'data-upload-url="/media/upload/"' in html
    assert 'data-browse-url="/media/browse/"' in html


@pytest.mark.parametrize("value", [None, ""])
def test_falsy_urls_disable_buttons(settings, value):
    settings.DJPRESS_TIPTAP_UPLOAD_URL = value
    settings.DJPRESS_TIPTAP_BROWSE_URL = value
    html = DjTiptapWidget().render("body", "")
    assert UPLOAD_BUTTON not in html
    assert BROWSE_BUTTON not in html
    assert VIDEO_UPLOAD_BUTTON not in html
    assert 'data-upload-url=""' in html
    assert 'data-browse-url=""' in html


def test_accept_attributes_rendered():
    html = DjTiptapWidget().render("body", "")
    assert 'data-accept-image="image/jpeg,image/png,image/gif,image/webp"' in html
    assert 'data-accept-video="video/mp4,video/webm"' in html


def test_empty_video_types_hide_video_upload_button(settings):
    settings.DJPRESS_TIPTAP_ALLOWED_VIDEO_TYPES = set()
    html = DjTiptapWidget().render("body", "")
    assert UPLOAD_BUTTON in html
    assert VIDEO_UPLOAD_BUTTON not in html
    assert 'data-accept-video=""' in html


def test_widget_arguments_override_settings(settings):
    settings.DJPRESS_TIPTAP_UPLOAD_URL = "/from-settings/upload/"
    settings.DJPRESS_TIPTAP_BROWSE_URL = "/from-settings/browse/"
    widget = DjTiptapWidget(upload_url="/widget/upload/", browse_url="/widget/browse/")
    html = widget.render("body", "")
    assert UPLOAD_BUTTON in html
    assert BROWSE_BUTTON in html
    assert 'data-upload-url="/widget/upload/"' in html
    assert 'data-browse-url="/widget/browse/"' in html


def test_legacy_html_storage_format_is_forwarded(settings):
    settings.DJPRESS_TIPTAP_STORAGE_FORMAT = "html"
    html = DjTiptapWidget().render("body", "<p>Legacy</p>")
    assert 'data-storage-format="html"' in html


def test_markdown_submission_normalizes_form_line_endings():
    widget = DjTiptapWidget()
    value = widget.value_from_datadict({"body": "first\r\nsecond\rthird"}, {}, "body")
    assert value == "first\nsecond\nthird"


def test_legacy_html_submission_preserves_line_endings(settings):
    settings.DJPRESS_TIPTAP_STORAGE_FORMAT = "html"
    widget = DjTiptapWidget()
    value = widget.value_from_datadict({"body": "<p>first\r\nsecond</p>"}, {}, "body")
    assert value == "<p>first\r\nsecond</p>"
