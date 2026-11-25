from django.test import Client, TestCase
from django.urls import reverse

from apps.samples_configurations.models import Category
from apps.labs.models import Branch
from apps.seo.models import SEOTemplate, SEOLandingPage
from apps.seo.services import generate_bulk_seo_pages, update_bulk_seo_metadata, sync_lab_seo


class SEOPagesAndMetadataTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Create Categories
        self.food_cat = Category.objects.create(name="Food Testing", active=True)
        self.pharma_cat = Category.objects.create(name="Pharmaceutical", active=True)

        # 2. Create Labs with locations
        self.lab1 = Branch.objects.create(
            lab_name="Delhi Food Testing Central",
            lab_city="Delhi",
            lab_address="Plot 45, Okhla Phase 3",
            lab_pincode="110020",
            NABL_code="NABL-1234",
            BIS_code="BIS-5678",
        )
        self.lab1.categories.add(self.food_cat)

        self.lab2 = Branch.objects.create(
            lab_name="Capital Food & Water Diagnostics",
            lab_city="Delhi",
            lab_address="Connaught Place",
            lab_pincode="110001",
        )
        self.lab2.categories.add(self.food_cat)

        self.lab3 = Branch.objects.create(
            lab_name="Noida Pharma Analytics Lab",
            lab_city="Noida",
            lab_address="Sector 62",
            lab_pincode="201301",
        )
        self.lab3.categories.add(self.pharma_cat)

    def test_bulk_generation_creates_database_records(self):
        """Verify that generate_bulk_seo_pages creates records according to Category and Branch city."""
        # Clear any auto-synced pages to test fresh generation
        SEOLandingPage.objects.all().delete()

        res = generate_bulk_seo_pages(min_labs_threshold=1)
        self.assertGreaterEqual(res["created"], 2)

        # Check Delhi food page
        delhi_page = SEOLandingPage.objects.filter(
            category=self.food_cat, city__iexact="Delhi"
        ).first()
        self.assertIsNotNone(delhi_page)
        self.assertEqual(delhi_page.lab_count, 2)
        self.assertEqual(delhi_page.slug, "top-2-food-testing-labs-in-delhi")
        self.assertIn("Delhi", delhi_page.meta_title)
        self.assertIn("Food Testing", delhi_page.meta_title)
        self.assertIn("Delhi", delhi_page.h1_heading)
        self.assertTrue(delhi_page.is_active)
        self.assertGreaterEqual(len(delhi_page.faq_schema), 2)

    def test_seo_landing_page_view_renders_correctly(self):
        """Verify that /labs/<slug>/ returns 200 with meta tags, schema JSON-LD, and matching labs."""
        generate_bulk_seo_pages(min_labs_threshold=1)
        page = SEOLandingPage.objects.filter(category=self.food_cat, city__iexact="Delhi").first()
        self.assertIsNotNone(page)

        response = self.client.get(page.get_absolute_url())
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        # Check SEO meta tags
        self.assertIn(f"<title>{page.meta_title}</title>", content)
        self.assertIn("Find and compare top 2 Food Testing laboratories in Delhi", content)
        self.assertIn(f'<h1>{page.h1_heading}</h1>', content)

        # Check JSON-LD Structured Data
        self.assertIn('"@type": "BreadcrumbList"', content)
        self.assertIn('"@type": "ItemList"', content)
        self.assertIn('"@type": "FAQPage"', content)

        # Check Lab names rendered
        self.assertIn("Delhi Food Testing Central", content)
        self.assertIn("Capital Food & Water Diagnostics", content)

    def test_bulk_metadata_update(self):
        """Verify bulk update re-applies template changes across records."""
        generate_bulk_seo_pages(min_labs_threshold=1)

        template = SEOTemplate.objects.filter(page_type="category_city").first()
        template.title_pattern = "Best {count} {category} Labs in {location} | Verified 2026"
        template.save()

        updated_count = update_bulk_seo_metadata(page_type="category_city", force=True)
        self.assertGreaterEqual(updated_count, 2)

        delhi_page = SEOLandingPage.objects.filter(category=self.food_cat, city__iexact="Delhi").first()
        self.assertIn("Best 2 Food Testing Labs in Delhi | Verified 2026", delhi_page.meta_title)

    def test_sitemap_includes_active_seo_landing_pages(self):
        """Verify sitemap.xml includes generated active landing page URLs."""
        generate_bulk_seo_pages(min_labs_threshold=1)
        delhi_page = SEOLandingPage.objects.filter(category=self.food_cat, city__iexact="Delhi").first()

        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn(delhi_page.get_absolute_url(), response.content.decode("utf-8"))

    def test_signal_syncs_seo_when_lab_registers(self):
        """Verify that creating a new lab in a new city triggers sync_lab_seo automatically."""
        new_lab = Branch.objects.create(
            lab_name="Gurgaon Water Testing Services",
            lab_city="Gurgaon",
            lab_address="Udyog Vihar",
        )
        new_lab.categories.add(self.food_cat)

        gurgaon_page = SEOLandingPage.objects.filter(
            category=self.food_cat, city__iexact="Gurgaon"
        ).first()
        self.assertIsNotNone(gurgaon_page)
        self.assertEqual(gurgaon_page.lab_count, 1)
        self.assertEqual(gurgaon_page.slug, "top-1-food-testing-labs-in-gurgaon")
