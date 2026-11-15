import os
from django.conf import settings
from django.urls import reverse


def linkedin_sso_context(request):
    """
    Exposes LinkedIn login URL and mode to all templates.
    If real LinkedIn credentials (client_id & client_secret) are supplied and
    MOCK_LINKEDIN_LOGIN is False, points to allauth OpenID Connect login endpoint.
    Otherwise, points to mock LinkedIn SSO endpoint.
    """
    client_id = getattr(settings, "LINKEDIN_CLIENT_ID", "") or os.environ.get("LINKEDIN_CLIENT_ID", "")
    client_secret = getattr(settings, "LINKEDIN_CLIENT_SECRET", "") or os.environ.get("LINKEDIN_CLIENT_SECRET", "")
    is_mock = getattr(settings, "MOCK_LINKEDIN_LOGIN", True) or not (client_id and client_secret)

    if not is_mock:
        try:
            login_url = reverse("openid_connect_login", kwargs={"provider_id": "linkedin"})
        except Exception:
            login_url = reverse("mock-linkedin-login")
    else:
        try:
            login_url = reverse("mock-linkedin-login")
        except Exception:
            login_url = "/mock-linkedin-login/"

    return {
        "linkedin_login_url": login_url,
        "is_mock_linkedin": is_mock,
    }

