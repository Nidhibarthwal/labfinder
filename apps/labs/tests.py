from django.test import TestCase, Client
from django.urls import reverse
from apps.labs.models import Branch
from apps.utility.models import Country, State


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

    def test_other_labs_prefers_same_city_then_falls_back_to_same_state(self):
        """Other Labs shows same-city labs first, and falls back to same-state labs if none match city."""
        country_in = Country.objects.create(name="India")
        state_up = State.objects.create(name="Uttar Pradesh", country=country_in)
        state_mh = State.objects.create(name="Maharashtra", country=country_in)

        self.lab1.lab_state = state_up
        self.lab1.save()

        same_city_lab = Branch.objects.create(
            lab_name="Apex Ghaziabad Lab",
            lab_city="ghaziabad",
            lab_state=state_up,
            is_active=True,
            is_public=True,
        )
        same_state_lab = Branch.objects.create(
            lab_name="Noida Quality Lab",
            lab_city="Noida",
            lab_state=state_up,
            is_active=True,
            is_public=True,
        )
        other_state_lab = Branch.objects.create(
            lab_name="Mumbai Testing Lab",
            lab_city="Mumbai",
            lab_state=state_mh,
            is_active=True,
            is_public=True,
        )

        # 1. When another lab exists in the same city, only same-city labs are returned
        response = self.client.get(self.lab1.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        other_labs = list(response.context["other_labs"])
        self.assertEqual(other_labs, [same_city_lab])

        # 2. When no other lab exists in the same city, fall back to same-state labs
        response_fallback = self.client.get(same_state_lab.get_absolute_url())
        self.assertEqual(response_fallback.status_code, 200)
        fallback_labs = list(response_fallback.context["other_labs"])
        self.assertIn(self.lab1, fallback_labs)
        self.assertIn(same_city_lab, fallback_labs)
        self.assertNotIn(other_state_lab, fallback_labs)

