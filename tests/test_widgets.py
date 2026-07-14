"""Tests for DjTiptapWidget rendering.

Covers the regression where unset/None/empty DJPRESS_TIPTAP_UPLOAD_URL or
DJPRESS_TIPTAP_BROWSE_URL crashed rendering with NoReverseMatch: the widget must
render in every configuration state, showing the upload/browse toolbar
buttons only when the corresponding URL is configured.
"""

import pytest

from djpress_tiptap.widgets import DjTiptapWidget

pytestmark = pytest.mark.urls("config.urls")

UPLOAD_BUTTON = 'data-command="uploadImage"'
BROWSE_BUTTON = 'data-command="browseImages"'
VIDEO_UPLOAD_BUTTON = 'data-command="uploadVideo"'


def test_configured_urls_render_buttons(settings):
    settings.DJPRESS_TIPTAP_UPLOAD_URL = "website:attachment_upload"
    settings.DJPRESS_TIPTAP_BROWSE_URL = "website:attachment_browse"
    html = DjTiptapWidget().render("body", "")
    assert UPLOAD_BUTTON in html
    assert BROWSE_BUTTON in html
    assert VIDEO_UPLOAD_BUTTON in html
    assert 'data-upload-url="/attachments/upload/"' in html
    assert 'data-browse-url="/attachments/browse/"' in html


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


def test_unset_urls_disable_buttons(settings):
    del settings.DJPRESS_TIPTAP_UPLOAD_URL
    del settings.DJPRESS_TIPTAP_BROWSE_URL
    html = DjTiptapWidget().render("body", "")
    assert UPLOAD_BUTTON not in html
    assert BROWSE_BUTTON not in html
    assert VIDEO_UPLOAD_BUTTON not in html


def test_accept_attributes_rendered():
    html = DjTiptapWidget().render("body", "")
    assert 'data-accept-image="image/jpeg,image/png,image/gif,image/webp"' in html
    assert 'data-accept-video="video/mp4,video/webm"' in html


def test_empty_video_types_hide_video_upload_button(settings):
    settings.DJPRESS_TIPTAP_UPLOAD_URL = "website:attachment_upload"
    settings.DJPRESS_TIPTAP_ALLOWED_VIDEO_TYPES = set()
    html = DjTiptapWidget().render("body", "")
    assert UPLOAD_BUTTON in html
    assert VIDEO_UPLOAD_BUTTON not in html
    assert 'data-accept-video=""' in html


def test_widget_arguments_override_settings(settings):
    del settings.DJPRESS_TIPTAP_UPLOAD_URL
    del settings.DJPRESS_TIPTAP_BROWSE_URL
    widget = DjTiptapWidget(upload_url="/widget/upload/", browse_url="/widget/browse/")
    html = widget.render("body", "")
    assert UPLOAD_BUTTON in html
    assert BROWSE_BUTTON in html
    assert 'data-upload-url="/widget/upload/"' in html
    assert 'data-browse-url="/widget/browse/"' in html
