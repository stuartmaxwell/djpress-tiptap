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
from django.core.checks import run_checks
from django.core.exceptions import ImproperlyConfigured

from djpress_tiptap import conf
from djpress_tiptap.checks import (
    LEGACY_HTML_RENDERER,
    LEGACY_HTML_STORAGE_WARNING,
    MARKDOWN_CAPABILITIES_WARNING,
    MARKDOWN_WITH_HTML_RENDERER_ERROR,
)

pytestmark = pytest.mark.urls("config.urls")


class TestStorageFormat:
    def test_default_is_markdown(self):
        assert conf.storage_format() == "markdown"

    def test_legacy_html_can_be_selected_explicitly(self, settings):
        settings.DJPRESS_TIPTAP_STORAGE_FORMAT = "html"
        assert conf.storage_format() == "html"

    def test_unknown_format_is_rejected(self, settings):
        settings.DJPRESS_TIPTAP_STORAGE_FORMAT = "json"
        with pytest.raises(ImproperlyConfigured, match="must be one of"):
            conf.storage_format()

    def test_default_does_not_produce_a_system_check_warning(self):
        assert all(message.id != LEGACY_HTML_STORAGE_WARNING for message in run_checks())

    def test_legacy_html_produces_a_deprecation_warning(self, settings):
        settings.DJPRESS_TIPTAP_STORAGE_FORMAT = "html"
        warning = next(message for message in run_checks() if message.id == LEGACY_HTML_STORAGE_WARNING)
        assert "deprecated HTML storage" in warning.msg
        assert "djpress_tiptap_convert_to_markdown" in warning.hint
        assert "remove DJPRESS_TIPTAP_STORAGE_FORMAT" in warning.hint

    def test_default_markdown_rejects_the_legacy_html_renderer(self, settings):
        settings.DJPRESS_SETTINGS = {"CONTENT_RENDERER": LEGACY_HTML_RENDERER}
        error = next(message for message in run_checks() if message.id == MARKDOWN_WITH_HTML_RENDERER_ERROR)
        assert "cannot render Markdown content" in error.msg
        assert "Remove the CONTENT_RENDERER" in error.hint

    def test_explicit_markdown_rejects_the_legacy_html_renderer(self, settings):
        settings.DJPRESS_TIPTAP_STORAGE_FORMAT = "markdown"
        settings.DJPRESS_SETTINGS = {"CONTENT_RENDERER": LEGACY_HTML_RENDERER}
        assert any(message.id == MARKDOWN_WITH_HTML_RENDERER_ERROR for message in run_checks())

    def test_legacy_renderer_is_allowed_while_html_storage_is_enabled(self, settings):
        settings.DJPRESS_TIPTAP_STORAGE_FORMAT = "html"
        settings.DJPRESS_SETTINGS = {"CONTENT_RENDERER": LEGACY_HTML_RENDERER}
        assert all(message.id != MARKDOWN_WITH_HTML_RENDERER_ERROR for message in run_checks())


class TestMarkdownCapabilities:
    def warning(self):
        return next(message for message in run_checks() if message.id == MARKDOWN_CAPABILITIES_WARNING)

    def test_default_example_configuration_has_required_capabilities(self):
        assert all(message.id != MARKDOWN_CAPABILITIES_WARNING for message in run_checks())

    def test_missing_both_extensions_reports_both_features(self, settings):
        settings.DJPRESS_SETTINGS = {"MARKDOWN_EXTENSIONS": []}
        warning = self.warning()
        assert "fenced code blocks, tables" in warning.msg
        assert "fenced_code" in warning.hint
        assert "tables" in warning.hint

    def test_missing_fenced_code_is_reported(self, settings):
        settings.DJPRESS_SETTINGS = {"MARKDOWN_EXTENSIONS": ["tables"]}
        warning = self.warning()
        assert "fenced code blocks" in warning.msg
        assert "tables" not in warning.msg

    def test_missing_tables_is_reported(self, settings):
        settings.DJPRESS_SETTINGS = {"MARKDOWN_EXTENSIONS": ["fenced_code"]}
        warning = self.warning()
        assert "tables" in warning.msg
        assert "fenced code blocks" not in warning.msg

    def test_extra_satisfies_both_capabilities(self, settings):
        settings.DJPRESS_SETTINGS = {"MARKDOWN_EXTENSIONS": ["extra"]}
        assert all(message.id != MARKDOWN_CAPABILITIES_WARNING for message in run_checks())

    def test_custom_renderer_is_not_probed(self, settings):
        settings.DJPRESS_SETTINGS = {"CONTENT_RENDERER": "example.custom_renderer"}
        assert all(message.id != MARKDOWN_CAPABILITIES_WARNING for message in run_checks())

    def test_html_storage_is_not_probed(self, settings):
        settings.DJPRESS_TIPTAP_STORAGE_FORMAT = "html"
        settings.DJPRESS_SETTINGS = {"MARKDOWN_EXTENSIONS": []}
        assert all(message.id != MARKDOWN_CAPABILITIES_WARNING for message in run_checks())


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
