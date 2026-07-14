"""Forms for the DJ Press Admin interface."""

from django import forms
from djpress import models

from djpress_tiptap.widgets import DjTiptapWidget


class PostForm(forms.ModelForm):
    """Form for creating a post - uses the DjTiptapWidget for the content field."""


    class Meta:
        """Meta class for PostForm."""

        model = models.Post
        fields = ["title", "content"]
        widgets = {"content": DjTiptapWidget()}
