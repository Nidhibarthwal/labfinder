from django.test import TestCase, Client
from django.urls import reverse
from apps.labs.models import Branch


class LabSlugAndDetailViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.lab1 = Branch.objects.create(
            lab_name="Ghaziabad Testing Lab",
            lab_city="Ghaziabad",
            is_active=True,
            is_public=True,
        )

    def test_slug_auto_generation_on_save(self):
        """Branch automatically generates an SEO slug on save based on lab_name."""
        self.assertEqual(self.lab1.slug, "ghaziabad-testing-lab")
        self.assertEqual(self.lab1.get_absolute_url(), "/lab-detail/ghaziabad-testing-lab/")

    def test_slug_uniqueness_handles_collisions(self):
        """Creating labs with identical names distinguishes them by city or counter."""
        lab2 = Branch.objects.create(
            lab_name="Ghaziabad Testing Lab",
            lab_city="Noida",
            is_active=True,
            is_public=True,
        )
        self.assertEqual(lab2.slug, "ghaziabad-testing-lab-noida")

        lab3 = Branch.objects.create(
            lab_name="Ghaziabad Testing Lab",
            lab_city="Noida",
            is_active=True,
            is_public=True,
        )
        self.assertEqual(lab3.slug, "ghaziabad-testing-lab-noida-2")

    def test_lab_detail_view_resolves_by_slug(self):
        """Accessing /lab-detail/<slug>/ returns 200 OK with the lab page."""
        response = self.client.get(f"/lab-detail/{self.lab1.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ghaziabad Testing Lab")

    def test_lab_detail_view_redirects_uuid_to_slug(self):
        """Accessing /lab-detail/<uuid>/ returns 301 Permanent Redirect to /lab-detail/<slug>/."""
        response = self.client.get(f"/lab-detail/{self.lab1.pk}/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, self.lab1.get_absolute_url())

        # Following redirect leads to 200 OK page
        follow_response = self.client.get(f"/lab-detail/{self.lab1.pk}/", follow=True)
        self.assertEqual(follow_response.status_code, 200)
        self.assertContains(follow_response, "Ghaziabad Testing Lab")

    def test_sitemap_labs_uses_slug_urls(self):
        """The /sitemap-labs.xml sitemap outputs SEO slug URLs."""
        response = self.client.get(reverse("django.contrib.sitemaps.views.sitemap", kwargs={"section": "labs"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"/lab-detail/{self.lab1.slug}/")
