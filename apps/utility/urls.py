from django.urls import path
from .views import MockLinkedInLoginAPIView

urlpatterns = [
    path(
        "mock-linkedin-login/",
        MockLinkedInLoginAPIView.as_view(),
        name="mock-linkedin-login",
    ),
    path(
        "linkedin-login/",
        MockLinkedInLoginAPIView.as_view(),
        name="linkedin_login",
    ),
]
