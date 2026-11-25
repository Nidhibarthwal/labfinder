"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static



from apps.web.views import dashboard_view
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from apps.seo.sitemaps import sitemaps


def robots_txt_view(request):
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    content = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/
Disallow: /lead/
Disallow: /order/
Disallow: /dashboard/
Disallow: /crawler-dashboard/

Sitemap: {sitemap_url}
"""
    return HttpResponse(content.strip(), content_type="text/plain")


urlpatterns = [
    path("robots.txt", robots_txt_view, name="robots_txt"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap-all"),
    path("sitemap-<section>.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("admin/", admin.site.urls),
    path("", include("apps.utility.urls")),
    path("", include("apps.home.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.labs.urls")),
    path("api/", include("apps.labs.api_urls")),
    path("api/v1/", include("apps.api.urls")),
    path("", include("apps.enquiries.urls")),
    path("", include("apps.customers.urls")),
    path("", include("apps.seo.urls")),
    path("crawler-dashboard/", dashboard_view, name="crawler_dashboard"),
    path("", include("apps.api.health_urls")),
    path("accounts/", include("allauth.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
