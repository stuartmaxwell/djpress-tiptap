"""Website URLs file."""

from django.urls import path

from website import views

app_name = "website"
urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("<int:pk>/", views.PostView.as_view(), name="post_view"),
    path("add/", views.PostCreateView.as_view(), name="post_create"),
    path("<int:pk>/edit/", views.PostUpdateView.as_view(), name="post_edit"),
]
