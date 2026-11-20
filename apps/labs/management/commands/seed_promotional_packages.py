import decimal
from django.core.management.base import BaseCommand
from apps.labs.models import (
    PromotionalPlan,
    PromotionalPlanFeature,
    PlanFeatureValue,
    PromotionalAddon,
)


class Command(BaseCommand):
    help = "Seed standard promotional packages and add-ons from Figma specifications"

    def handle(self, *args, **options):
        self.stdout.write("Seeding Promotional Plans...")

        plans_data = [
            {
                "name": "Basic (Free)",
                "slug": "basic",
                "tagline": "Standard Algorithmic Visibility",
                "base_price": decimal.Decimal("0.00"),
                "billing_period_days": 30,
                "search_ranking_priority": "standard",
                "priority_tier_level": 3,
                "trust_badge_type": "basic",
                "badge_label": "Basic Listed",
                "requires_gst_license": False,
                "requires_nabl_iso": False,
                "banner_type": "none",
                "max_header_banners": 0,
                "allow_video_banner": False,
                "direct_cta_type": "request_quote",
                "allow_direct_phone": False,
                "allow_whatsapp": False,
                "allow_instant_rfq": False,
                "can_hide_reviews": False,
                "hide_competitor_ads": False,
                "monthly_shared_enquiries": 2,
                "is_unlimited_enquiries": False,
                "home_page_listing": "random",
                "is_featured": False,
                "sort_order": 1,
            },
            {
                "name": "Verified Lab (Growth)",
                "slug": "growth",
                "tagline": "Priority Tier 2 & Verified Trust Badge",
                "base_price": decimal.Decimal("4999.00"),
                "billing_period_days": 30,
                "search_ranking_priority": "tier_2",
                "priority_tier_level": 2,
                "trust_badge_type": "verified_lab",
                "badge_label": "Verified Lab Badge",
                "requires_gst_license": True,
                "requires_nabl_iso": False,
                "banner_type": "static_header",
                "max_header_banners": 1,
                "allow_video_banner": False,
                "direct_cta_type": "send_enquiry",
                "allow_direct_phone": False,
                "allow_whatsapp": False,
                "allow_instant_rfq": False,
                "can_hide_reviews": False,
                "hide_competitor_ads": False,
                "monthly_shared_enquiries": 10,
                "is_unlimited_enquiries": False,
                "home_page_listing": "random",
                "is_featured": True,
                "sort_order": 2,
            },
            {
                "name": "Trusted Partner (Pro)",
                "slug": "pro",
                "tagline": "Priority Tier 1 Top Organic Placement & Full Lead Suite",
                "base_price": decimal.Decimal("14999.00"),
                "billing_period_days": 30,
                "search_ranking_priority": "tier_1",
                "priority_tier_level": 1,
                "trust_badge_type": "trusted_partner",
                "badge_label": "NABL / ISO Verified Highlight Badge",
                "requires_gst_license": True,
                "requires_nabl_iso": True,
                "banner_type": "carousel_video",
                "max_header_banners": 3,
                "allow_video_banner": True,
                "direct_cta_type": "all_channels",
                "allow_direct_phone": True,
                "allow_whatsapp": True,
                "allow_instant_rfq": True,
                "can_hide_reviews": True,
                "hide_competitor_ads": True,
                "monthly_shared_enquiries": -1,
                "is_unlimited_enquiries": True,
                "home_page_listing": "high_priority",
                "is_featured": False,
                "sort_order": 3,
            },
        ]

        plans_dict = {}
        for pdata in plans_data:
            slug = pdata.pop("slug")
            plan, created = PromotionalPlan.objects.update_or_create(
                slug=slug, defaults=pdata
            )
            plans_dict[slug] = plan
            action = "Created" if created else "Updated"
            self.stdout.write(f"  {action} plan: {plan.name}")

        self.stdout.write("Seeding Dynamic Features (Figma comparison table)...")

        features_data = [
            ("Base Price (30 Days INR)", "base_price", "Billing cost for 30 days active period", 1),
            ("Search Ranking Priority", "search_ranking", "Search placement algorithm tier", 2),
            ("Trust & Compliance Badge", "trust_badge", "Trust verification badge displayed on lab cards", 3),
            ("Profile Promotional Banner", "promotional_banner", "Custom branding banners on lab profile", 4),
            ("Direct Lead CTA Button", "direct_lead_cta", "Primary customer call-to-action buttons", 5),
            ("Manage Reviews", "manage_reviews", "Capability to control public review visibility", 6),
            ("Competitor Ads on Profile", "competitor_ads", "Display or hide other labs ads on profile", 7),
            ("Enquiries", "enquiries_allowance", "Monthly quota of shared lead inquiries", 8),
            ("Home Page Listing", "home_page_listing", "Home page placement probability", 9),
        ]

        features_dict = {}
        for name, code, desc, order in features_data:
            feat, created = PromotionalPlanFeature.objects.update_or_create(
                code=code, defaults={"name": name, "description": desc, "sort_order": order, "is_active": True}
            )
            features_dict[code] = feat

        # Feature values matrix matching figma-screens/promotional-packages.png
        values_matrix = [
            # feature_code, basic_val, basic_inc, growth_val, growth_inc, pro_val, pro_inc
            ("base_price", "₹0", True, "₹4,999", True, "₹14,999", True),
            ("search_ranking", "Standard (Algorithmic)", True, "Priority Tier 2 (Above Free)", True, "Priority Tier 1 (Top Organic)", True),
            ("trust_badge", "Basic Listed", True, "Verified Lab Badge (GST/License)", True, "NABL / ISO Verified Highlight Badge", True),
            ("promotional_banner", "None", False, "1 Static Header Banner", True, "Carousel Banner (Up to 3) + Video", True),
            ("direct_lead_cta", "Request Quote", True, "Send Enquiry", True, "Send Enquiry, Direct Phone, WhatsApp & Instant RFQ", True),
            ("manage_reviews", "No", False, "No", False, "Can hide reviews", True),
            ("competitor_ads", "Shown", False, "Shown", False, "Hidden (Ad-free profile)", True),
            ("enquiries_allowance", "upto 2 shared enquiries/month", True, "upto 10 shared enquiries/month", True, "Unlimited Shared Enquiries", True),
            ("home_page_listing", "Random", True, "Random", True, "High Priority Listing", True),
        ]

        for code, b_val, b_inc, g_val, g_inc, p_val, p_inc in values_matrix:
            feat = features_dict[code]
            # Basic
            PlanFeatureValue.objects.update_or_create(
                plan=plans_dict["basic"], feature=feat,
                defaults={"value_text": b_val, "is_included": b_inc, "sort_order": feat.sort_order}
            )
            # Growth
            PlanFeatureValue.objects.update_or_create(
                plan=plans_dict["growth"], feature=feat,
                defaults={"value_text": g_val, "is_included": g_inc, "sort_order": feat.sort_order}
            )
            # Pro
            PlanFeatureValue.objects.update_or_create(
                plan=plans_dict["pro"], feature=feat,
                defaults={"value_text": p_val, "is_included": p_inc, "sort_order": feat.sort_order}
            )

        self.stdout.write("Seeding Promotional Add-ons (figma-screens/promotional-addon.png)...")

        addons_data = [
            {
                "name": "Category Featured Lab Pin",
                "code": "category_featured_pin",
                "placement": "Top 3 search results per category/country",
                "tagging": "Sponsored",
                "inventory_cap_text": "Max 3 slots per category/country",
                "max_inventory_slots": 3,
                "base_price": decimal.Decimal("2999.00"),
                "max_price": decimal.Decimal("7999.00"),
                "pricing_factor": "Category & city search demand",
                "duration_days": 30,
                "is_active": True,
                "sort_order": 1,
            },
            {
                "name": "Competitor Targeting",
                "code": "competitor_targeting",
                "placement": "Top banner on other labs profile, belonging to targeted category/country",
                "tagging": "Promoted / Ad",
                "inventory_cap_text": "3 rotating slots per category",
                "max_inventory_slots": 3,
                "base_price": decimal.Decimal("4999.00"),
                "max_price": None,
                "pricing_factor": "Category traffic volume",
                "duration_days": 30,
                "is_active": True,
                "sort_order": 2,
            },
            {
                "name": "Home Page Listing",
                "code": "home_page_listing",
                "placement": "Listing on home page for particular category",
                "tagging": "Sponsored",
                "inventory_cap_text": "1 per category",
                "max_inventory_slots": 1,
                "base_price": decimal.Decimal("1999.00"),
                "max_price": None,
                "pricing_factor": "Category demand",
                "duration_days": 30,
                "is_active": True,
                "sort_order": 3,
            },
        ]

        for adata in addons_data:
            code = adata.pop("code")
            addon, created = PromotionalAddon.objects.update_or_create(
                code=code, defaults=adata
            )
            action = "Created" if created else "Updated"
            self.stdout.write(f"  {action} addon: {addon.name}")

        self.stdout.write(self.style.SUCCESS("Successfully seeded all promotional packages, features, and add-ons!"))
