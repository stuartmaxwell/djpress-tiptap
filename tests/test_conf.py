"""Tests for djpress_tiptap.conf.

The upload/browse URL functions must resolve configured values (URL name or
path) and return "" when the setting is unset, None, or empty — that empty
string is what tells the widget template to hide the image/browse buttons.
"""

import pytest

from djpress_tiptap import conf

pytestmark = pytest.mark.urls("config.urls")


class TestMaxUploadSizeMb:
    def test_default(self, settings):
        del settings.DJPRESS_TIPTAP_MAX_UPLOAD_SIZE_MB
        assert conf.max_upload_size_mb() == 10

    def test_configured(self, settings):
        settings.DJPRESS_TIPTAP_MAX_UPLOAD_SIZE_MB = 25
        assert conf.max_upload_size_mb() == 25


class TestAllowedImageTypes:
    def test_default(self, settings):
        del settings.DJPRESS_TIPTAP_ALLOWED_IMAGE_TYPES
        assert conf.allowed_image_types() == conf.DEFAULT_ALLOWED_IMAGE_TYPES

    def test_configured(self, settings):
        settings.DJPRESS_TIPTAP_ALLOWED_IMAGE_TYPES = {"PNG": "image/png"}
        assert conf.allowed_image_types() == {"PNG": "image/png"}


class TestMaxVideoUploadSizeMb:
    def test_default(self, settings):
        del settings.DJPRESS_TIPTAP_MAX_VIDEO_UPLOAD_SIZE_MB
        assert conf.max_video_upload_size_mb() == 100

    def test_configured(self, settings):
        settings.DJPRESS_TIPTAP_MAX_VIDEO_UPLOAD_SIZE_MB = 500
        assert conf.max_video_upload_size_mb() == 500


class TestAllowedVideoTypes:
    def test_default(self, settings):
        del settings.DJPRESS_TIPTAP_ALLOWED_VIDEO_TYPES
        assert conf.allowed_video_types() == conf.DEFAULT_ALLOWED_VIDEO_TYPES

    def test_configured(self, settings):
        settings.DJPRESS_TIPTAP_ALLOWED_VIDEO_TYPES = {"video/mp4"}
        assert conf.allowed_video_types() == {"video/mp4"}


class TestUploadUrl:
    def test_url_name_is_resolved(self, settings):
        settings.DJPRESS_TIPTAP_UPLOAD_URL = "website:attachment_upload"
        assert conf.upload_url() == "/attachments/upload/"

    def test_path_is_passed_through(self, settings):
        settings.DJPRESS_TIPTAP_UPLOAD_URL = "/custom/upload/"
        assert conf.upload_url() == "/custom/upload/"

    def test_unset_returns_empty(self, settings):
        del settings.DJPRESS_TIPTAP_UPLOAD_URL
        assert conf.upload_url() == ""

    def test_none_returns_empty(self, settings):
        settings.DJPRESS_TIPTAP_UPLOAD_URL = None
        assert conf.upload_url() == ""

    def test_empty_string_returns_empty(self, settings):
        settings.DJPRESS_TIPTAP_UPLOAD_URL = ""
        assert conf.upload_url() == ""

    def test_override_wins_over_setting(self, settings):
        settings.DJPRESS_TIPTAP_UPLOAD_URL = "/from-settings/"
        assert conf.upload_url("/from-widget/") == "/from-widget/"

    def test_override_works_when_setting_unset(self, settings):
        del settings.DJPRESS_TIPTAP_UPLOAD_URL
        assert conf.upload_url("website:attachment_upload") == "/attachments/upload/"


class TestBrowseUrl:
    def test_url_name_is_resolved(self, settings):
        settings.DJPRESS_TIPTAP_BROWSE_URL = "website:attachment_browse"
        assert conf.browse_url() == "/attachments/browse/"

    def test_path_is_passed_through(self, settings):
        settings.DJPRESS_TIPTAP_BROWSE_URL = "/custom/browse/"
        assert conf.browse_url() == "/custom/browse/"

    def test_unset_returns_empty(self, settings):
        del settings.DJPRESS_TIPTAP_BROWSE_URL
        assert conf.browse_url() == ""

    def test_none_returns_empty(self, settings):
        settings.DJPRESS_TIPTAP_BROWSE_URL = None
        assert conf.browse_url() == ""

    def test_empty_string_returns_empty(self, settings):
        settings.DJPRESS_TIPTAP_BROWSE_URL = ""
        assert conf.browse_url() == ""

    def test_override_wins_over_setting(self, settings):
        settings.DJPRESS_TIPTAP_BROWSE_URL = "/from-settings/"
        assert conf.browse_url("/from-widget/") == "/from-widget/"
