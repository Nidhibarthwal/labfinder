import logging
from django.db.models import Q, Count
from django.utils.text import slugify

from apps.samples_configurations.models import Category
from apps.labs.models import Branch
from apps.seo.models import SEOLandingPage, SEOTemplate

logger = logging.getLogger(__name__)

ALLOWED_TOP_TIERS = (3, 5, 10, 20, 50)


def get_top_count_tier(lab_count):
    """
    Returns the highest allowed SEO 'Top N' tier (3, 5, 10, 20, 50)
    that does not exceed lab_count, or None if lab_count < 3.
    """
    if not lab_count or lab_count < ALLOWED_TOP_TIERS[0]:
        return None
    tier = None
    for t in ALLOWED_TOP_TIERS:
        if lab_count >= t:
            tier = t
        else:
            break
    return tier


def get_or_create_default_template(page_type="category_city"):
    """
    Ensures a default SEOTemplate exists for the given page_type.
    """
    template, _ = SEOTemplate.objects.get_or_create(
        page_type=page_type,
        defaults={
            "title_pattern": "Top {count} {category} Labs in {location} (NABL Accredited) | LabFinder",
            "meta_desc_pattern": "Find and compare top {count} {category_phrase} laboratories in {location}. View NABL & BIS accreditations, testing turnaround times, sample parameters, and request instant quotation on LabFinder.",
            "meta_keywords_pattern": "{category} testing labs in {location}, top {category} labs {location}, NABL accredited {category} lab {location}",
            "h1_pattern": "Top {count} {category_phrase} Laboratories in {location}",
            "intro_pattern": "Looking for certified {category_phrase} laboratories in {location}? Browse our verified directory of accredited laboratories equipped with advanced testing instrumentation, experienced scientific personnel, and quick turnaround times. Request direct quotations or compare multiple responses effortlessly.",
        }
    )
    return template


def build_page_metadata(template, category_name, location_name, count_display):
    """
    Interpolates dynamic placeholders into SEO template patterns.
    """
    cat_clean = (category_name or "Testing").strip()
    if cat_clean.lower().endswith("testing") or cat_clean.lower().endswith("labs"):
        category_phrase = cat_clean
    else:
        category_phrase = f"{cat_clean} Testing"

    ctx = {
        "count": count_display,
        "category": cat_clean,
        "category_phrase": category_phrase,
        "location": location_name,
    }

    title = template.title_pattern.format(**ctx)
    desc = template.meta_desc_pattern.format(**ctx)
    keywords = template.meta_keywords_pattern.format(**ctx)
    h1 = template.h1_pattern.format(**ctx)
    intro = template.intro_pattern.format(**ctx)

    raw_faq_patterns = template.get_default_faq_patterns()
    rendered_faqs = []
    for item in raw_faq_patterns:
        rendered_faqs.append({
            "question": item.get("question", "").format(**ctx),
            "answer": item.get("answer", "").format(**ctx),
        })

    return {
        "meta_title": title[:255],
        "meta_description": desc,
        "meta_keywords": keywords[:255],
        "h1_heading": h1[:255],
        "intro_content": intro,
        "faq_schema": rendered_faqs,
    }


def sync_branch_categories_from_group_names():
    """
    Auto-populates Branch.categories M2M field across laboratories based on
    Branch.group_name, Branch.discipline_name, and Branch.lab_category.
    Performs batch through-table inserts.
    """
    rules = [
        ("Food", Q(group_name__icontains="Food")),
        ("Water", Q(group_name__icontains="Water") | Q(group_name__icontains="Pollution") | Q(group_name__icontains="Environment")),
        ("Metal", Q(group_name__icontains="Metal") | Q(group_name__icontains="Building")),
        ("Chemical", Q(discipline_name__icontains="Chemical") | Q(group_name__icontains="Chemical") | Q(group_name__icontains="Petroleum")),
        ("Mechanical", Q(discipline_name__icontains="Mechanical")),
        ("Electrical", Q(discipline_name__icontains="Electrical") | Q(discipline_name__icontains="Electronics")),
        ("Pharma", Q(group_name__icontains="Drug") | Q(group_name__icontains="Pharma")),
        ("Textile", Q(group_name__icontains="Textile")),
        ("Calibration", Q(lab_category__name__icontains="Calibration") | Q(lab_name__icontains="Calibration")),
    ]

    through_model = Branch.categories.through
    total_added = 0

    for keyword, query in rules:
        cat = Category.objects.filter(name__icontains=keyword, active=True).first()
        if not cat:
            continue

        branch_ids = set(Branch.objects.filter(query).values_list("pk", flat=True))
        if not branch_ids:
            continue

        existing_branch_ids = set(
            through_model.objects.filter(category_id=cat.pk).values_list("branch_id", flat=True)
        )
        new_ids = branch_ids - existing_branch_ids

        if new_ids:
            new_relations = [
                through_model(category_id=cat.pk, branch_id=b_id)
                for b_id in new_ids
            ]
            through_model.objects.bulk_create(new_relations, ignore_conflicts=True, batch_size=2000)
            total_added += len(new_relations)

    logger.info(f"Synchronized {total_added} category-branch linkages from group_names.")
    return total_added


def generate_bulk_seo_pages(min_labs_threshold=3, overwrite_customized=False, include_groups=True):
    """
    Main bulk generator engine using both Branch.categories and Branch.group_name.
    Only generates pages for allowed Top-N tiers: 3, 5, 10, 20, 50 (never top-1, top-2, top-4, etc.).
    """
    # 1. Sync laboratory categories from group names & disciplines
    sync_branch_categories_from_group_names()

    effective_min_labs = max(min_labs_threshold, ALLOWED_TOP_TIERS[0])
    template = get_or_create_default_template("category_city")
    categories = Category.objects.filter(active=True)

    created_count = 0
    updated_count = 0
    deactivated_count = 0
    valid_slugs = set()

    # Pass 1: Generate landing pages for formal Categories (Branch.categories)
    for cat in categories:
        city_names = (
            Branch.objects.filter(
                categories=cat,
                lab_city__isnull=False
            )
            .exclude(lab_city__exact="")
            .values_list("lab_city", flat=True)
            .distinct()
        )

        for raw_city in city_names:
            city_clean = raw_city.strip().title()
            if not city_clean:
                continue

            labs_qs = Branch.objects.filter(
                categories=cat,
                lab_city__iexact=city_clean
            ).distinct()

            lab_count = labs_qs.count()
            if lab_count < effective_min_labs:
                continue

            count_display = get_top_count_tier(lab_count)
            if count_display is None:
                continue

            slug = slugify(f"top-{count_display}-{cat.name}-labs-in-{city_clean}")
            valid_slugs.add(slug)

            meta = build_page_metadata(template, cat.name, city_clean, count_display)

            sample_branch = labs_qs.first()
            state_ref = sample_branch.lab_state if sample_branch else None
            district_ref = sample_branch.lab_district if sample_branch else None
            region_ref = sample_branch.lab_region if sample_branch else ""

            page, created = SEOLandingPage.objects.get_or_create(
                slug=slug,
                defaults={
                    "page_type": "category_city",
                    "category": cat,
                    "city": city_clean,
                    "state": state_ref,
                    "district": district_ref,
                    "region": region_ref,
                    "meta_title": meta["meta_title"],
                    "meta_description": meta["meta_description"],
                    "meta_keywords": meta["meta_keywords"],
                    "h1_heading": meta["h1_heading"],
                    "intro_content": meta["intro_content"],
                    "faq_schema": meta["faq_schema"],
                    "lab_count": lab_count,
                    "is_active": True,
                    "is_customized": False,
                }
            )

            if created:
                created_count += 1
            else:
                page.lab_count = lab_count
                page.is_active = True
                page.category = cat
                if not page.is_customized or overwrite_customized:
                    page.meta_title = meta["meta_title"]
                    page.meta_description = meta["meta_description"]
                    page.h1_heading = meta["h1_heading"]
                    page.intro_content = meta["intro_content"]
                    page.faq_schema = meta["faq_schema"]
                page.save()
                updated_count += 1

    # Pass 2: Generate landing pages for prominent specialties from Branch.group_name
    if include_groups:
        top_groups = [
            "Soil and Rock",
            "Buildings Materials",
            "Solid Fuels",
            "Plastics and Plastic Products",
            "Petroleum and Products",
            "Rubber and Rubber Products",
            "Ores & Minerals",
            "Atmospheric Pollution",
            "Animal Food & Feeds",
        ]

        for g_name in top_groups:
            city_names = (
                Branch.objects.filter(
                    group_name__icontains=g_name,
                    lab_city__isnull=False
                )
                .exclude(lab_city__exact="")
                .values_list("lab_city", flat=True)
                .distinct()
            )

            for raw_city in city_names:
                city_clean = raw_city.strip().title()
                if not city_clean:
                    continue

                labs_qs = Branch.objects.filter(
                    group_name__icontains=g_name,
                    lab_city__iexact=city_clean
                ).distinct()

                lab_count = labs_qs.count()
                if lab_count < effective_min_labs:
                    continue

                count_display = get_top_count_tier(lab_count)
                if count_display is None:
                    continue

                slug = slugify(f"top-{count_display}-{g_name}-labs-in-{city_clean}")
                valid_slugs.add(slug)

                meta = build_page_metadata(template, g_name, city_clean, count_display)

                sample_branch = labs_qs.first()
                state_ref = sample_branch.lab_state if sample_branch else None
                district_ref = sample_branch.lab_district if sample_branch else None
                region_ref = sample_branch.lab_region if sample_branch else ""

                page, created = SEOLandingPage.objects.get_or_create(
                    slug=slug,
                    defaults={
                        "page_type": "group_city",
                        "group_name": g_name,
                        "city": city_clean,
                        "state": state_ref,
                        "district": district_ref,
                        "region": region_ref,
                        "meta_title": meta["meta_title"],
                        "meta_description": meta["meta_description"],
                        "meta_keywords": meta["meta_keywords"],
                        "h1_heading": meta["h1_heading"],
                        "intro_content": meta["intro_content"],
                        "faq_schema": meta["faq_schema"],
                        "lab_count": lab_count,
                        "is_active": True,
                        "is_customized": False,
                    }
                )

                if created:
                    created_count += 1
                else:
                    page.lab_count = lab_count
                    page.is_active = True
                    page.group_name = g_name
                    if not page.is_customized or overwrite_customized:
                        page.meta_title = meta["meta_title"]
                        page.meta_description = meta["meta_description"]
                        page.h1_heading = meta["h1_heading"]
                        page.intro_content = meta["intro_content"]
                        page.faq_schema = meta["faq_schema"]
                    page.save()
                    updated_count += 1

    # Clean up stale/disallowed tier pages (e.g., top-1, top-2, top-4, or outdated tiers)
    stale_qs = SEOLandingPage.objects.exclude(slug__in=valid_slugs)
    if overwrite_customized:
        deactivated_count = stale_qs.count()
        stale_qs.delete()
    else:
        non_custom_stale = stale_qs.filter(is_customized=False)
        deactivated_count += non_custom_stale.count()
        non_custom_stale.delete()
        custom_stale = stale_qs.filter(is_customized=True, is_active=True)
        deactivated_count += custom_stale.update(is_active=False)

    return {
        "created": created_count,
        "updated": updated_count,
        "deactivated": deactivated_count,
    }


def update_bulk_seo_metadata(page_type=None, force=False):
    """
    Bulk re-applies the latest SEOTemplate across all matching SEOLandingPage records.
    Completes in seconds across thousands of pages using batch processing.
    """
    template = get_or_create_default_template("category_city")
    qs = SEOLandingPage.objects.all()
    if page_type:
        qs = qs.filter(page_type=page_type)
    if not force:
        qs = qs.filter(is_customized=False)

    pages_to_update = []
    for page in qs.select_related("category"):
        count_display = get_top_count_tier(page.lab_count)
        if count_display is None:
            continue
        cat_name = page.display_category
        meta = build_page_metadata(template, cat_name, page.city, count_display)

        page.meta_title = meta["meta_title"]
        page.meta_description = meta["meta_description"]
        page.meta_keywords = meta["meta_keywords"]
        page.h1_heading = meta["h1_heading"]
        page.intro_content = meta["intro_content"]
        page.faq_schema = meta["faq_schema"]
        pages_to_update.append(page)

    if pages_to_update:
        SEOLandingPage.objects.bulk_update(
            pages_to_update,
            fields=["meta_title", "meta_description", "meta_keywords", "h1_heading", "intro_content", "faq_schema", "updated_at"],
            batch_size=1000
        )

    return len(pages_to_update)


def sync_lab_seo(branch):
    """
    Triggered when a laboratory registers or updates its location/categories.
    Syncs the corresponding Category x City and Group x City landing page metrics.
    """
    if not branch or not branch.lab_city:
        return

    city_clean = branch.lab_city.strip().title()
    template = get_or_create_default_template("category_city")

    # Categories to sync
    categories = list(branch.categories.filter(active=True))
    for cat in categories:
        labs_qs = Branch.objects.filter(
            categories=cat,
            lab_city__iexact=city_clean
        ).distinct()

        lab_count = labs_qs.count()
        count_display = get_top_count_tier(lab_count)
        if count_display is None:
            SEOLandingPage.objects.filter(
                category=cat, city__iexact=city_clean, is_customized=False
            ).delete()
            continue

        slug = slugify(f"top-{count_display}-{cat.name}-labs-in-{city_clean}")

        # Remove older tier slug for the same category + city if tier changed (e.g., top-3 -> top-5)
        SEOLandingPage.objects.filter(
            category=cat, city__iexact=city_clean, is_customized=False
        ).exclude(slug=slug).delete()

        meta = build_page_metadata(template, cat.name, city_clean, count_display)

        page, created = SEOLandingPage.objects.get_or_create(
            slug=slug,
            defaults={
                "page_type": "category_city",
                "category": cat,
                "city": city_clean,
                "state": branch.lab_state,
                "district": branch.lab_district,
                "region": branch.lab_region,
                "meta_title": meta["meta_title"],
                "meta_description": meta["meta_description"],
                "meta_keywords": meta["meta_keywords"],
                "h1_heading": meta["h1_heading"],
                "intro_content": meta["intro_content"],
                "faq_schema": meta["faq_schema"],
                "lab_count": lab_count,
                "is_active": (lab_count > 0),
            }
        )

        if not created:
            page.lab_count = lab_count
            page.is_active = (lab_count > 0)
            page.category = cat
            if not page.is_customized:
                page.meta_title = meta["meta_title"]
                page.meta_description = meta["meta_description"]
                page.h1_heading = meta["h1_heading"]
            page.save()
