"""Website views."""


from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views.generic import View
from djpress import models

from website import forms


class HomeView(LoginRequiredMixin, View):
    """Home view displaying recent posts."""

    def get(self, request):
        posts = models.Post.admin_objects.all()
        return TemplateResponse(request, "website/home.html", {"posts": posts})


class PostView(LoginRequiredMixin, View):
    """View a single post."""

    def get(self, request, pk):
        post = get_object_or_404(models.Post, pk=pk)
        return TemplateResponse(request, "website/post.html", {"post": post})


class PostCreateView(LoginRequiredMixin, View):
    """Create a new post."""

    def get(self, request):
        form = forms.PostForm()

        return TemplateResponse(request, "website/post_form.html", {"form": form})

    def post(self, request):
        form = forms.PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.status = "published"
            post.save()
            return redirect("website:home")

        return TemplateResponse(request, "website/post_form.html", {"form": form})


class PostUpdateView(LoginRequiredMixin, View):
    """Update an existing post."""

    def get(self, request, pk):
        post = get_object_or_404(models.Post, pk=pk)
        form = forms.PostForm(instance=post)

        return TemplateResponse(request, "website/post_form.html", {"form": form, "post": post})

    def post(self, request, pk):
        post = get_object_or_404(models.Post, pk=pk)
        form = forms.PostForm(request.POST, instance=post)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.status = "published"
            post.save()
            return redirect("website:home")

        return TemplateResponse(request, "website/post_form.html", {"form": form, "post": post})
