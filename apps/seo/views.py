import json
from django.shortcuts import render, get_object_or_404
from django.db.models import Q

from apps.seo.models import SEOLandingPage
from apps.seo.services import get_top_count_tier
from apps.labs.models import Branch


def seo_landing_page_view(request, slug):
    """
    Renders the programmatic SEO landing page for top laboratories in a category and city.
    Features:
      - Curated list of verified matching laboratories
      - Breadcrumbs navigation
      - Rich Schema: BreadcrumbList, ItemList (top labs), FAQPage
      - Internal linking grid (other categories in this city, same category in other cities)
    """
    page = get_object_or_404(SEOLandingPage, slug=slug, is_active=True)

    # 1. Fetch matching laboratories in this category and city
    cat = page.category
    city = page.city

    labs_qs = Branch.objects.filter(lab_city__iexact=city)
    category_q = Q()
    if cat:
        category_q |= Q(categories=cat)
    if page.group_name:
        category_q |= Q(group_name__icontains=page.group_name)

    if category_q:
        labs_qs = labs_qs.filter(category_q)

    labs_qs = labs_qs.distinct().order_by("-is_active", "-created_at")

    tier_limit = get_top_count_tier(page.lab_count) or 10
    top_labs = list(labs_qs[:tier_limit])

    # 2. Build Structured Data (JSON-LD)
    # A. BreadcrumbList Schema
    breadcrumbs_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": request.build_absolute_uri("/"),
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": f"Labs in {city}",
                "item": request.build_absolute_uri(f"/search-lab/?q={city}"),
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": page.h1_heading,
                "item": request.build_absolute_uri(page.get_absolute_url()),
            },
        ],
    }

    # B. ItemList Schema (Top Laboratories)
    item_list_schema = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": page.h1_heading,
        "description": page.meta_description,
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": idx + 1,
                "name": getattr(lab, "lab_name", "") or str(lab.pk),
                "url": request.build_absolute_uri(lab.get_absolute_url()),
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": lab.lab_address or "",
                    "addressLocality": lab.lab_city or city,
                    "postalCode": lab.lab_pincode or "",
                    "addressCountry": "IN",
                },
            }
            for idx, lab in enumerate(top_labs)
        ],
    }

    # C. FAQPage Schema
    faq_items = []
    for faq in page.faq_schema or []:
        q = faq.get("question")
        a = faq.get("answer")
        if q and a:
            faq_items.append({
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": a,
                },
            })

    faq_schema_ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": faq_items,
    } if faq_items else None

    # 3. Internal Linking Grid
    other_pages_in_city = (
        SEOLandingPage.objects.filter(city__iexact=city, is_active=True)
        .exclude(pk=page.pk)
        .select_related("category")[:8]
    )

    if page.category:
        same_category_other_cities = (
            SEOLandingPage.objects.filter(category=page.category, is_active=True)
            .exclude(pk=page.pk)
            .order_by("-lab_count")[:8]
        )
    elif page.group_name:
        same_category_other_cities = (
            SEOLandingPage.objects.filter(group_name=page.group_name, is_active=True)
            .exclude(pk=page.pk)
            .order_by("-lab_count")[:8]
        )
    else:
        same_category_other_cities = []

    context = {
        "page": page,
        "display_category": page.display_category,
        "top_labs": top_labs,
        "breadcrumbs_schema_json": json.dumps(breadcrumbs_schema),
        "item_list_schema_json": json.dumps(item_list_schema),
        "faq_schema_json": json.dumps(faq_schema_ld) if faq_schema_ld else None,
        "other_pages_in_city": other_pages_in_city,
        "same_category_other_cities": same_category_other_cities,
        "city": city,
        "category": cat,
    }
    return render(request, "seo/landing_page.html", context)
