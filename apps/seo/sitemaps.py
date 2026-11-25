from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.seo.models import SEOLandingPage
from apps.labs.models import Branch


class StaticViewSitemap(Sitemap):
    """
    Sitemap for core static/public pages of LabFinder.
    """
    def items(self):
        return [
            {"name": "home", "priority": 1.0, "changefreq": "daily"},
            {"name": "search-lab", "priority": 0.9, "changefreq": "daily"},
            {"name": "search-product", "priority": 0.9, "changefreq": "daily"},
            {"name": "enquiry_now", "priority": 0.8, "changefreq": "weekly"},
        ]

    def location(self, item):
        return reverse(item["name"])

    def priority(self, item):
        return item["priority"]

    def changefreq(self, item):
        return item["changefreq"]


class SEOLandingPageSitemap(Sitemap):
    """
    Sitemap for programmatic Category x City landing pages.
    Excludes 0-lab pages to prevent soft 404/thin-content penalties.
    """
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return (
            SEOLandingPage.objects.filter(is_active=True, lab_count__gt=0)
            .select_related("category")
            .order_by("-lab_count", "-updated_at")
        )

    def location(self, item):
        return item.get_absolute_url()

    def lastmod(self, item):
        return item.updated_at


class LabDetailSitemap(Sitemap):
    """
    Sitemap for public, verified laboratory profile pages.
    """
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return (
            Branch.objects.filter(is_active=True, is_public=True)
            .exclude(lab_name__isnull=True)
            .exclude(lab_name__exact="")
            .order_by("-created_at")
        )

    def location(self, item):
        return item.get_absolute_url()

    def lastmod(self, item):
        return item.updated_at


sitemaps = {
    "static": StaticViewSitemap,
    "seo": SEOLandingPageSitemap,
    "labs": LabDetailSitemap,
}
