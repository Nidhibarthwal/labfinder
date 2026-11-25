from django.urls import path
from . import views

urlpatterns = [
    path("labs/<slug:slug>/", views.seo_landing_page_view, name="seo_landing_page"),
]
