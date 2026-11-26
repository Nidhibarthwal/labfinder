from django.test import Client, TestCase

from apps.samples_configurations.models import Category
from apps.labs.models import Branch
from apps.seo.models import SEOTemplate, SEOLandingPage
from apps.seo.services import (
    generate_bulk_seo_pages,
    update_bulk_seo_metadata,
    get_top_count_tier,
)


class SEOPagesAndMetadataTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Create Categories
        self.food_cat = Category.objects.create(name="Food Testing", active=True)
        self.pharma_cat = Category.objects.create(name="Pharmaceutical", active=True)

        # 2. Create 3 Food Testing labs in Delhi (meets top-3 tier)
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
            lab_name="North India Food Analytics",
            lab_city="Delhi",
            lab_address="Mayapuri Phase 2",
            lab_pincode="110064",
        )
        self.lab3.categories.add(self.food_cat)

        # 3. Only 1 Pharma lab in Noida (below minimum tier 3 -> should NOT create top-1 page)
        self.lab4 = Branch.objects.create(
            lab_name="Noida Pharma Analytics Lab",
            lab_city="Noida",
            lab_address="Sector 62",
            lab_pincode="201301",
        )
        self.lab4.categories.add(self.pharma_cat)

    def test_get_top_count_tier_mapping(self):
        """Verify only tiers 3, 5, 10, 20, 50 are allowed (never 1, 2, 4, etc.)."""
        self.assertIsNone(get_top_count_tier(0))
        self.assertIsNone(get_top_count_tier(1))
        self.assertIsNone(get_top_count_tier(2))
        self.assertEqual(get_top_count_tier(3), 3)
        self.assertEqual(get_top_count_tier(4), 3)
        self.assertEqual(get_top_count_tier(5), 5)
        self.assertEqual(get_top_count_tier(9), 5)
        self.assertEqual(get_top_count_tier(10), 10)
        self.assertEqual(get_top_count_tier(19), 10)
        self.assertEqual(get_top_count_tier(20), 20)
        self.assertEqual(get_top_count_tier(49), 20)
        self.assertEqual(get_top_count_tier(50), 50)
        self.assertEqual(get_top_count_tier(120), 50)

    def test_bulk_generation_creates_only_allowed_tiers(self):
        """Verify generate_bulk_seo_pages creates top-3 for 3 labs and skips cities with < 3 labs."""
        SEOLandingPage.objects.all().delete()

        res = generate_bulk_seo_pages(min_labs_threshold=1)
        self.assertGreaterEqual(res["created"], 1)

        # Delhi has 3 Food Testing labs -> top-3 page created
        delhi_page = SEOLandingPage.objects.filter(
            category=self.food_cat, city__iexact="Delhi"
        ).first()
        self.assertIsNotNone(delhi_page)
        self.assertEqual(delhi_page.lab_count, 3)
        self.assertEqual(delhi_page.slug, "top-3-food-testing-labs-in-delhi")
        self.assertIn("Delhi", delhi_page.meta_title)
        self.assertIn("Food Testing", delhi_page.meta_title)
        self.assertIn("Delhi", delhi_page.h1_heading)
        self.assertTrue(delhi_page.is_active)
        self.assertGreaterEqual(len(delhi_page.faq_schema), 2)

        # Noida has only 1 Pharma lab -> NO top-1 page created
        noida_page = SEOLandingPage.objects.filter(
            category=self.pharma_cat, city__iexact="Noida"
        ).first()
        self.assertIsNone(noida_page)

    def test_seo_landing_page_view_renders_correctly(self):
        """Verify that /labs/<slug>/ returns 200 with meta tags, schema JSON-LD, and matching labs."""
        generate_bulk_seo_pages()
        page = SEOLandingPage.objects.filter(category=self.food_cat, city__iexact="Delhi").first()
        self.assertIsNotNone(page)

        response = self.client.get(page.get_absolute_url())
        self.assertEqual(response.status_code, 200)

        content = response.content.decode("utf-8")
        self.assertIn(f"<title>{page.meta_title}</title>", content)
        self.assertIn("Find and compare top 3 Food Testing laboratories in Delhi", content)
        self.assertIn(f"<h1>{page.h1_heading}</h1>", content)

        # Check JSON-LD Structured Data
        self.assertIn('"@type": "BreadcrumbList"', content)
        self.assertIn('"@type": "ItemList"', content)
        self.assertIn('"@type": "FAQPage"', content)

        # Check Lab names rendered
        self.assertIn("Delhi Food Testing Central", content)
        self.assertIn("Capital Food & Water Diagnostics", content)

    def test_bulk_metadata_update(self):
        """Verify bulk update re-applies template changes across records."""
        generate_bulk_seo_pages()

        template = SEOTemplate.objects.filter(page_type="category_city").first()
        template.title_pattern = "Best {count} {category} Labs in {location} | Verified 2026"
        template.save()

        updated_count = update_bulk_seo_metadata(page_type="category_city", force=True)
        self.assertGreaterEqual(updated_count, 1)

        delhi_page = SEOLandingPage.objects.filter(category=self.food_cat, city__iexact="Delhi").first()
        self.assertIn("Best 3 Food Testing Labs in Delhi | Verified 2026", delhi_page.meta_title)

    def test_sitemap_includes_active_seo_landing_pages(self):
        """Verify sitemap.xml includes generated active landing page URLs."""
        generate_bulk_seo_pages()
        delhi_page = SEOLandingPage.objects.filter(category=self.food_cat, city__iexact="Delhi").first()

        response = self.client.get("/sitemap-seo.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn(delhi_page.get_absolute_url(), response.content.decode("utf-8"))

    def test_signal_syncs_seo_only_when_reaching_min_tier(self):
        """Verify signal does NOT create top-1/top-2, and creates top-3 once 3rd lab registers."""
        for i in range(1, 3):
            lab = Branch.objects.create(
                lab_name=f"Gurgaon Food Lab {i}",
                lab_city="Gurgaon",
                lab_address="Udyog Vihar",
            )
            lab.categories.add(self.food_cat)

        # Still only 2 labs -> no page yet
        self.assertFalse(
            SEOLandingPage.objects.filter(category=self.food_cat, city__iexact="Gurgaon").exists()
        )

        # Add 3rd lab -> top-3 page is automatically created
        lab3 = Branch.objects.create(
            lab_name="Gurgaon Food Lab 3",
            lab_city="Gurgaon",
            lab_address="Cyber City",
        )
        lab3.categories.add(self.food_cat)

        gurgaon_page = SEOLandingPage.objects.filter(
            category=self.food_cat, city__iexact="Gurgaon"
        ).first()
        self.assertIsNotNone(gurgaon_page)
        self.assertEqual(gurgaon_page.lab_count, 3)
        self.assertEqual(gurgaon_page.slug, "top-3-food-testing-labs-in-gurgaon")
