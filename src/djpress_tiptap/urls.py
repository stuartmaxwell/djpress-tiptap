"""Website URLs file."""

from django.urls import path

from djpress_tiptap import views

app_name = "djpress_tiptap"
urlpatterns = [
    path("upload/", views.MediaUploadView.as_view(), name="media_upload"),
    path("browse/", views.MediaBrowseView.as_view(), name="media_browse"),
]
