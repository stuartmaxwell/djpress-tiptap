"""Tests for djpress_tiptap.conf.

Every setting is optional in the host project: with nothing configured the
functions return the package defaults, and the upload/browse URL functions
resolve to the bundled djpress_tiptap views. Setting an URL to None or ""
returns "" — that empty string is what tells the widget template to hide the
image/browse buttons.

The example project deliberately sets no DJPRESS_TIPTAP_* settings, so the
"default" cases below exercise the real fallback path.
"""

import pytest

from djpress_tiptap import conf

pytestmark = pytest.mark.urls("config.urls")


class TestMaxUploadSizeMb:
    def test_default(self):
        assert conf.max_upload_size_mb() == 10

    def test_configured(self, settings):
        settings.DJPRESS_TIPTAP_MAX_UPLOAD_SIZE_MB = 25
        assert conf.max_upload_size_mb() == 25


class TestAllowedImageTypes:
    def test_default(self):
        assert conf.allowed_image_types() == conf.DEFAULT_ALLOWED_IMAGE_TYPES

    def test_configured(self, settings):
        settings.DJPRESS_TIPTAP_ALLOWED_IMAGE_TYPES = {"PNG": "image/png"}
        assert conf.allowed_image_types() == {"PNG": "image/png"}


class TestMaxVideoUploadSizeMb:
    def test_default(self):
        assert conf.max_video_upload_size_mb() == 100

    def test_configured(self, settings):
        settings.DJPRESS_TIPTAP_MAX_VIDEO_UPLOAD_SIZE_MB = 500
        assert conf.max_video_upload_size_mb() == 500


class TestAllowedVideoTypes:
    def test_default(self):
        assert conf.allowed_video_types() == conf.DEFAULT_ALLOWED_VIDEO_TYPES

    def test_configured(self, settings):
        settings.DJPRESS_TIPTAP_ALLOWED_VIDEO_TYPES = {"video/mp4"}
        assert conf.allowed_video_types() == {"video/mp4"}


class TestUploadUrl:
    def test_default_resolves_to_bundled_view(self):
        assert conf.upload_url() == "/media/upload/"

    def test_url_name_is_resolved(self, settings):
        settings.DJPRESS_TIPTAP_UPLOAD_URL = "djpress_tiptap:media_upload"
        assert conf.upload_url() == "/media/upload/"

    def test_path_is_passed_through(self, settings):
        settings.DJPRESS_TIPTAP_UPLOAD_URL = "/custom/upload/"
        assert conf.upload_url() == "/custom/upload/"

    def test_none_returns_empty(self, settings):
        settings.DJPRESS_TIPTAP_UPLOAD_URL = None
        assert conf.upload_url() == ""

    def test_empty_string_returns_empty(self, settings):
        settings.DJPRESS_TIPTAP_UPLOAD_URL = ""
        assert conf.upload_url() == ""

    def test_override_wins_over_setting(self, settings):
        settings.DJPRESS_TIPTAP_UPLOAD_URL = "/from-settings/"
        assert conf.upload_url("/from-widget/") == "/from-widget/"

    def test_override_works_when_setting_unset(self):
        assert conf.upload_url("djpress_tiptap:media_upload") == "/media/upload/"


class TestBrowseUrl:
    def test_default_resolves_to_bundled_view(self):
        assert conf.browse_url() == "/media/browse/"

    def test_url_name_is_resolved(self, settings):
        settings.DJPRESS_TIPTAP_BROWSE_URL = "djpress_tiptap:media_browse"
        assert conf.browse_url() == "/media/browse/"

    def test_path_is_passed_through(self, settings):
        settings.DJPRESS_TIPTAP_BROWSE_URL = "/custom/browse/"
        assert conf.browse_url() == "/custom/browse/"

    def test_none_returns_empty(self, settings):
        settings.DJPRESS_TIPTAP_BROWSE_URL = None
        assert conf.browse_url() == ""

    def test_empty_string_returns_empty(self, settings):
        settings.DJPRESS_TIPTAP_BROWSE_URL = ""
        assert conf.browse_url() == ""

    def test_override_wins_over_setting(self, settings):
        settings.DJPRESS_TIPTAP_BROWSE_URL = "/from-settings/"
        assert conf.browse_url("/from-widget/") == "/from-widget/"
