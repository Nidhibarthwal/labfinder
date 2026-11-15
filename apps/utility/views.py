import os
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.shortcuts import redirect
from django.urls import reverse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from allauth.socialaccount.models import SocialAccount

User = get_user_model()

def get_linkedin_profile(user):
    if not user.is_authenticated:
        return {}

    # Mock LinkedIn account for local testing
    if user.email and user.email.lower() == "linkedin.test@example.com":
        return {
            "linkedin_id": "mock_linkedin_123",
            "name": user.get_full_name() or "LinkedIn Tester",
            "first_name": user.first_name or "LinkedIn",
            "last_name": user.last_name or "Tester",
            "email": user.email,
            "profile_picture": "",
            "current_organization": "Test Organization",
            "is_mock": True,
        }

    social_account = SocialAccount.objects.filter(
        user=user,
        provider="openid_connect",
        uid__isnull=False,
    ).first()

    if not social_account:
        return {
            "name": user.get_full_name(),
            "email": user.email,
            "profile_picture": "",
            "current_organization": "",
            "is_mock": False,
        }

    data = social_account.extra_data or {}

    return {
        "linkedin_id": data.get("sub"),
        "name": data.get("name") or user.get_full_name(),
        "first_name": data.get("given_name") or user.first_name,
        "last_name": data.get("family_name") or user.last_name,
        "email": data.get("email") or user.email,
        "profile_picture": data.get("picture", ""),
        "current_organization": "",
        "is_mock": False,
    }


class MockLinkedInLoginAPIView(APIView):
    """
    LinkedIn SSO Handler.
    - If real credentials (LINKEDIN_CLIENT_ID & LINKEDIN_CLIENT_SECRET) are configured
      and MOCK_LINKEDIN_LOGIN is False, redirects to Allauth LinkedIn OpenID Connect login.
    - If credentials are not yet available (or MOCK_LINKEDIN_LOGIN is True), authenticates
      a mock LinkedIn user and redirects to the target page (e.g. enquiry form).
    - Supports both browser GET/POST navigation and AJAX/REST clients.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def _is_mock_enabled(self):
        client_id = getattr(settings, "LINKEDIN_CLIENT_ID", "") or os.environ.get("LINKEDIN_CLIENT_ID", "")
        client_secret = getattr(settings, "LINKEDIN_CLIENT_SECRET", "") or os.environ.get("LINKEDIN_CLIENT_SECRET", "")
        mock_setting = getattr(settings, "MOCK_LINKEDIN_LOGIN", None)
        if mock_setting is not None:
            return bool(mock_setting)
        return not bool(client_id and client_secret)

    def _get_next_url(self, request):
        return (
            request.GET.get("next")
            or request.POST.get("next")
            or getattr(settings, "LOGIN_REDIRECT_URL", "/enquiry/")
        )

    def _redirect_to_real_linkedin(self, request, next_url):
        try:
            oidc_url = reverse("openid_connect_login", kwargs={"provider_id": "linkedin"})
            return redirect(f"{oidc_url}?process=login&next={next_url}")
        except Exception:
            return redirect(f"/accounts/oidc/linkedin/login/?process=login&next={next_url}")

    def _authenticate_mock_user(self, request):
        email = "linkedin.test@example.com"
        user = User.objects.filter(email__iexact=email).first()

        if not user:
            base_username = "linkedin_test_user"
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1

            create_kwargs = {
                User.USERNAME_FIELD: username,
                "email": email,
            }
            user = User(**create_kwargs)
            user.first_name = "LinkedIn"
            user.last_name = "Tester"
            user.set_unusable_password()
            if hasattr(user, "is_active"):
                user.is_active = True
            user.save()

        if not user.is_active:
            user.is_active = True
            user.save()

        login(
            request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )
        return user

    def get(self, request):
        next_url = self._get_next_url(request)

        if not self._is_mock_enabled():
            return self._redirect_to_real_linkedin(request, next_url)

        user = self._authenticate_mock_user(request)
        messages.success(
            request,
            f"Successfully signed in as {user.get_full_name() or user.email} via LinkedIn."
        )
        return redirect(next_url)

    def post(self, request):
        next_url = self._get_next_url(request)

        if not self._is_mock_enabled():
            is_ajax = (
                request.headers.get("x-requested-with") == "XMLHttpRequest"
                or "application/json" in request.headers.get("Accept", "")
            )
            if is_ajax:
                return Response(
                    {
                        "success": True,
                        "provider": "linkedin_openid_connect",
                        "redirect_url": f"/accounts/oidc/linkedin/login/?process=login&next={next_url}",
                    },
                    status=status.HTTP_200_OK,
                )
            return self._redirect_to_real_linkedin(request, next_url)

        user = self._authenticate_mock_user(request)
        linkedin_profile = get_linkedin_profile(user)

        is_ajax = (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            or "application/json" in request.headers.get("Accept", "")
        )
        if is_ajax:
            return Response(
                {
                    "success": True,
                    "message": "Mock LinkedIn login successful.",
                    "provider": (
                        "mock_linkedin"
                        if linkedin_profile.get("is_mock")
                        else "linkedin_openid_connect"
                    ),
                    "redirect_url": next_url,
                    "user": {
                        "id": str(user.pk),
                        "email": linkedin_profile.get("email", ""),
                        "name": linkedin_profile.get("name", ""),
                        "first_name": linkedin_profile.get("first_name", ""),
                        "last_name": linkedin_profile.get("last_name", ""),
                        "profile_picture": linkedin_profile.get("profile_picture", ""),
                        "current_organization": linkedin_profile.get(
                            "current_organization", ""
                        ),
                    },
                },
                status=status.HTTP_200_OK,
            )

        messages.success(
            request,
            f"Successfully signed in as {user.get_full_name() or user.email} via LinkedIn."
        )
        return redirect(next_url)
