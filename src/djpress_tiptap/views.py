"""Website views."""

from typing import TYPE_CHECKING

import puremagic
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.views.generic import View
from djpress import models
from PIL import Image, UnidentifiedImageError

from djpress_tiptap import conf

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile


class MediaUploadView(PermissionRequiredMixin, View):
    """Upload media view.

    This view implements the following pipeline on post:

        - identify() identifies the mime type from the file using puremagic
        - a handler is called based on the mime type
        - there are currently two handlers: handle_image() and handle_video()
        - both verify the file and check it against the allowed types and maximum sizes
        - then store() is called to save the media

    Errors are always {"error": "<message>"} with status 400.

    To upload files, users must have the "djpress.add_media" permission.
    """

    permission_required = "djpress.add_media"

    def post(self, request) -> JsonResponse:
        upload = request.FILES.get("file")
        if upload is None:
            return JsonResponse({"error": "No file provided."}, status=400)

        content_type = self.identify(upload)
        handler = getattr(self, f"handle_{content_type.partition('/')[0]}", None)
        if handler is None:
            return JsonResponse({"error": "File is not a recognisable image or video."}, status=400)

        return handler(upload, content_type)

    @staticmethod
    def identify(upload: UploadedFile) -> str:
        """Identify the file type using puremagic.

        Args:
            upload: The uploaded file to identify.

        Returns:
            The identified content type, or an empty string if unrecognised.
        """
        try:
            # All matches ordered by confidence; an unrecognised file yields an empty list (or PureError on some inputs)
            matches = puremagic.magic_stream(upload, filename=upload.name)

        except puremagic.PureError:
            matches = []

        upload.seek(0)  # rewind the header read; handlers expect a fresh stream

        # Some low-confidence matches carry no mime type; skip those.
        return next((m.mime_type for m in matches if m.mime_type), "")

    @staticmethod
    def size_error(upload: UploadedFile, max_upload_mb: int) -> JsonResponse | None:
        """The error response for an oversized upload.

        Args:
            upload: The uploaded file to check.
            max_upload_mb: The maximum allowed size in MB.

        Returns:
            A JsonResponse with an error message if the upload is too large, or None if within the limit.
        """
        if upload.size > max_upload_mb * 1024 * 1024:
            return JsonResponse(
                {"error": f"File too large (max {max_upload_mb} MB)."},
                status=400,
            )

        return None

    def handle_image(self, upload: UploadedFile, _content_type: str) -> JsonResponse:
        """Image handlre.

        Validates an image with Pillow.

        Args:
            upload: The uploaded file to handle.
            _content_type: The content type of the upload (unused).

        Returns:
            A JsonResponse with an error message if the image is invalid, or None if the image is valid.
        """
        try:
            image = Image.open(upload)
            # Read format and dimensions from the header before verify(), which consumes the stream and invalidates the
            # Image object.
            image_format = image.format
            image.verify()

        except UnidentifiedImageError:
            return JsonResponse({"error": "File is not a recognisable image or video."}, status=400)

        allowed_types = conf.allowed_image_types()
        if image_format not in allowed_types:
            return JsonResponse({"error": f"Unsupported image format: {image_format}."}, status=400)

        if error := self.size_error(upload, conf.max_upload_size_mb()):
            return error

        return self.store(upload, allowed_types[image_format])

    def handle_video(self, upload: UploadedFile, content_type: str) -> JsonResponse:
        """Video handler.

        Validate a video: the magic-number identification is the whole check.

        Args:
            upload: The uploaded file to handle.
            content_type: The content type of the upload.

        Returns:
            A JsonResponse with an error message if the video is invalid, or None if the video is valid.
        """
        if content_type not in conf.allowed_video_types():
            # e.g. video/quicktime: a real video, just not a web-playable one
            return JsonResponse({"error": f"Unsupported video format: {content_type}."}, status=400)

        if error := self.size_error(upload, conf.max_video_upload_size_mb()):
            return error

        return self.store(upload, content_type)

    def store(
        self,
        upload: UploadedFile,
        content_type: str,
    ) -> JsonResponse:
        """Create the Attachment.

        Args:
            upload: The uploaded file to store.
            content_type: The content type of the upload.

        Returns:
            A JsonResponse with the attachment's URL, alt text, and content type.
        """
        upload.seek(0)  # rewind after detection, or the stored file is truncated

        media_type = next((mt for mt, _ in models.Media.MEDIA_TYPE_CHOICES if mt in content_type.lower()), "other")

        user = self.request.user
        attachment = models.Media.objects.create(
            title=upload.name,
            file=upload,
            media_type=media_type,
            alt_text=upload.name,
            uploaded_by=user if user.is_authenticated else None,
        )

        return JsonResponse(
            {
                "url": attachment.file.url,
                "alt": attachment.alt_text,
                "content_type": content_type,
            },
            status=201,
        )


class MediaBrowseView(LoginRequiredMixin, View):
    """Simple media browser.

    Shows thumbnails of images in a dialog box with simple pagination.
    """

    def get(self, request):
        paginator = Paginator(models.Media.objects.get_by_type("image"), 24)
        page = paginator.get_page(request.GET.get("page"))
        return TemplateResponse(request, "djpress_tiptap/attachment_browse.html", {"page": page})
