"""Tests for the media upload and browse endpoints."""

import io

import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from djpress import models
from PIL import Image

pytestmark = pytest.mark.django_db

UPLOAD_URL = "/media/upload/"
BROWSE_URL = "/media/browse/"


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def user(django_user_model):
    user = django_user_model.objects.create_user(username="author", password="secret")
    permission = Permission.objects.get(content_type__app_label="djpress", codename="add_media")
    user.user_permissions.add(permission)
    return user


@pytest.fixture
def client(user):
    """An authenticated client whose user is allowed to upload media."""
    client = Client()
    client.force_login(user)
    return client


def image_upload(name="photo.png", image_format="PNG", size=(300, 200)):
    """Build a small real image as an uploaded file."""
    buffer = io.BytesIO()
    Image.new("RGB", size, "red").save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue())


# Just enough of an MP4/MOV header for puremagic's magic-number check: the
# ftyp box with a major brand. The brand decides the mime type (isom ->
# video/mp4, "qt  " -> video/quicktime).
def video_upload(name="clip.mp4", brand=b"isom"):
    """Build a minimal file with a valid MP4-family signature."""
    data = b"\x00\x00\x00\x18ftyp" + brand + b"\x00\x00\x02\x00" + brand + b"\x00" * 32
    return SimpleUploadedFile(name, data)


class TestMediaUpload:
    """Upload endpoint: validation, metadata capture, and error shapes."""

    def test_upload_png_creates_media(self, client, user):
        upload = image_upload()
        response = client.post(UPLOAD_URL, {"file": upload})

        assert response.status_code == 201
        media = models.Media.objects.get()
        assert response.json() == {
            "url": media.file.url,
            "alt": "photo.png",
            "content_type": "image/png",
        }
        assert media.title == "photo.png"
        assert media.alt_text == "photo.png"
        assert media.media_type == "image"
        assert media.uploaded_by == user
        # Files land in DJ Press's configured upload path (djpress/YYYY/MM/DD/)
        assert media.file.name.startswith("djpress/")
        # The stored file must not be truncated by the Pillow verify() pass
        assert media.file.size == upload.size

    def test_upload_jpeg_accepted(self, client):
        upload = image_upload("photo.jpg", image_format="JPEG")
        response = client.post(UPLOAD_URL, {"file": upload})
        assert response.status_code == 201
        assert models.Media.objects.get().media_type == "image"

    def test_anonymous_upload_requires_login(self):
        response = Client().post(UPLOAD_URL, {"file": image_upload()})
        assert response.status_code == 302
        assert response.url == f"/accounts/login/?next={UPLOAD_URL}"
        assert not models.Media.objects.exists()

    def test_authenticated_user_without_permission_is_forbidden(self, django_user_model):
        user = django_user_model.objects.create_user(username="reader", password="secret")
        client = Client()
        client.force_login(user)

        response = client.post(UPLOAD_URL, {"file": image_upload()})

        assert response.status_code == 403
        assert not models.Media.objects.exists()

    def test_get_not_allowed(self, client):
        assert client.get(UPLOAD_URL).status_code == 405

    def test_missing_file_rejected(self, client):
        response = client.post(UPLOAD_URL)
        assert response.status_code == 400
        assert response.json() == {"error": "No file provided."}

    def test_non_media_rejected(self, client):
        upload = SimpleUploadedFile("notes.txt", b"not an image or video")
        response = client.post(UPLOAD_URL, {"file": upload})
        assert response.status_code == 400
        assert "not a recognisable image or video" in response.json()["error"]

    def test_unsupported_format_rejected(self, client):
        upload = image_upload("scan.bmp", image_format="BMP")
        response = client.post(UPLOAD_URL, {"file": upload})
        assert response.status_code == 400
        assert "Unsupported image format: BMP" in response.json()["error"]

    def test_oversized_file_rejected(self, client, settings):
        # With the limit at 0 MB any real file is too large — no need to
        # build a 10 MB blob (and this proves the view reads the setting
        # at request time rather than at import).
        settings.DJPRESS_TIPTAP_MAX_UPLOAD_SIZE_MB = 0
        response = client.post(UPLOAD_URL, {"file": image_upload()})
        assert response.status_code == 400
        assert response.json()["error"] == "File too large (max 0 MB)."

    def test_csrf_enforced(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(UPLOAD_URL, {"file": image_upload()})
        assert response.status_code == 403
        assert not models.Media.objects.exists()


class TestVideoUpload:
    """Video branch of the upload endpoint: magic-byte validation, metadata."""

    def test_upload_mp4_creates_media(self, client, user):
        upload = video_upload()
        response = client.post(UPLOAD_URL, {"file": upload})

        assert response.status_code == 201
        media = models.Media.objects.get()
        assert response.json() == {
            "url": media.file.url,
            "alt": "clip.mp4",
            "content_type": "video/mp4",
        }
        assert media.title == "clip.mp4"
        assert media.media_type == "video"
        assert media.uploaded_by == user
        # The stored file must not be truncated by the detection reads
        assert media.file.size == upload.size

    def test_unsupported_video_format_rejected(self, client):
        # QuickTime is a real video type but not web-playable, so it's not in
        # the default allow-list
        upload = video_upload("clip.mov", brand=b"qt  ")
        response = client.post(UPLOAD_URL, {"file": upload})
        assert response.status_code == 400
        assert "Unsupported video format: video/quicktime" in response.json()["error"]

    def test_video_types_configurable(self, client, settings):
        settings.DJPRESS_TIPTAP_ALLOWED_VIDEO_TYPES = set()
        response = client.post(UPLOAD_URL, {"file": video_upload()})
        assert response.status_code == 400

    def test_oversized_video_rejected(self, client, settings):
        settings.DJPRESS_TIPTAP_MAX_VIDEO_UPLOAD_SIZE_MB = 0
        response = client.post(UPLOAD_URL, {"file": video_upload()})
        assert response.status_code == 400
        assert response.json()["error"] == "File too large (max 0 MB)."

    def test_video_size_limit_independent_of_image_limit(self, client, settings):
        # A 0 MB *image* limit must not block video uploads
        settings.DJPRESS_TIPTAP_MAX_UPLOAD_SIZE_MB = 0
        response = client.post(UPLOAD_URL, {"file": video_upload()})
        assert response.status_code == 201

    def test_videos_excluded_from_image_browse(self, client):
        client.post(UPLOAD_URL, {"file": video_upload()})
        client.post(UPLOAD_URL, {"file": image_upload()})
        response = client.get(BROWSE_URL)
        assert response.text.count("data-image-url") == 1


class TestMediaBrowse:
    """Browse endpoint: fragment rendering and pagination."""

    def test_empty_library(self, client):
        response = client.get(BROWSE_URL)
        assert response.status_code == 200
        assert "No images yet" in response.text

    def test_grid_and_pagination(self, client):
        for i in range(25):  # one more than a full page
            client.post(UPLOAD_URL, {"file": image_upload(f"img{i}.png")})

        response = client.get(BROWSE_URL)
        assert response.text.count("data-image-url") == 24
        assert 'data-fetch="?page=2"' in response.text

        response = client.get(f"{BROWSE_URL}?page=2")
        assert response.text.count("data-image-url") == 1
        assert 'data-fetch="?page=1"' in response.text

    def test_bad_page_number_clamps(self, client):
        client.post(UPLOAD_URL, {"file": image_upload()})
        response = client.get(f"{BROWSE_URL}?page=999")
        assert response.status_code == 200
        assert "Page 1 of 1" in response.text
