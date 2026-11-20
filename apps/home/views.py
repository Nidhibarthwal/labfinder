from urllib.parse import unquote
from django.db.models import Q, Count, Prefetch, Case, When, Value, IntegerField
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from apps.labs.models import Branch, BranchItem, ProductService
from apps.samples_configurations.models import Category, SubCategory
# ==============================================================================
# Common Helper Formatters
# ==============================================================================

def _format_lab_card_product(b, tests=None):
    """Format a Branch instance into product-search card data."""
    accred_names = []
    for a in b.branch_accreditation.all():
        if a.active:
            accred_names.append(a.name or (a.accred.name if a.accred else "NABL"))
    if not accred_names:
        accred_names = ["NABL", "ISO/IEC 17025"] if b.NABL_code else ["NABL"]

    loc_parts = [p for p in [b.lab_city, str(b.lab_state) if b.lab_state else "", "IN"] if p]
    location = ", ".join(loc_parts) or "India"

    formatted_tests = tests or []

    return {
        "id": str(b.pk),
        "name": b.lab_name or "Certified Analytical Lab",
        "logo": b.lab_logo.url if b.lab_logo else None,
        "is_vista": (b.source == "vista") or bool(b.VISTA_code),
        "rating": 4.8,
        "reviews_count": 107,
        "accreditations": accred_names[:3],
        "location": location,
        "country": str(b.lab_country.name) if b.lab_country else "India",
        "tests": formatted_tests[:4],
        "lab_type": "connected" if ((b.source == "vista") or bool(b.VISTA_code)) else "partner",
        "url": f"/lab-detail/{b.pk}/",
        "promotional_tier": getattr(b, "promotional_tier", "basic"),
        "priority_tier_level": getattr(b, "priority_tier_level", 3),
        "is_verified_growth": getattr(b, "is_verified_growth", False),
        "is_trusted_partner_pro": getattr(b, "is_trusted_partner_pro", False),
    }


def _format_lab_card_lab(b):
    """Format a Branch instance into lab-search grid card data."""
    accred_names = []
    for a in b.branch_accreditation.all():
        if a.active:
            accred_names.append(a.name or (a.accred.name if a.accred else "NABL"))
    if not accred_names:
        accred_names = ["NABL", "ISO/IEC 17025"] if b.NABL_code else ["NABL"]

    loc_parts = [p for p in [b.lab_city, str(b.lab_state) if b.lab_state else ""] if p]
    location = ", ".join(loc_parts) or "India"

    return {
        "id": str(b.pk),
        "name": b.lab_name or "Certified Laboratory",
        "logo": b.lab_logo.url if b.lab_logo else None,
        "cover": b.cover_picture.url if b.cover_picture else None,
        "is_vista": (b.source == "vista") or bool(b.VISTA_code),
        "rating": 4.9,
        "reviews_count": 214,
        "location": location,
        "accreditations": accred_names[:2],
        "price": "₹1,800+",
        "tat": "Onwards",
        "url": f"/lab-detail/{b.pk}/",
        "country": str(b.lab_country.name) if b.lab_country else "India",
        "lab_type": "connected" if ((b.source == "vista") or bool(b.VISTA_code)) else "partner",
        "promotional_tier": getattr(b, "promotional_tier", "basic"),
        "priority_tier_level": getattr(b, "priority_tier_level", 3),
        "is_verified_growth": getattr(b, "is_verified_growth", False),
        "is_trusted_partner_pro": getattr(b, "is_trusted_partner_pro", False),
    }


def _compute_filter_counts(labs):
    """Compute facet counts directly from the matching lab cards."""
    india_cnt = sum(1 for l in labs if (l.get("country") or "").lower() == "india")
    usa_cnt = sum(1 for l in labs if (l.get("country") or "").lower() in ["united states", "usa"])
    germany_cnt = sum(1 for l in labs if (l.get("country") or "").lower() == "germany")

    connected_cnt = sum(1 for l in labs if l.get("lab_type") == "connected")
    partner_cnt = sum(1 for l in labs if l.get("lab_type") == "partner")

    return {
        "country_counts": {
            "india": india_cnt,
            "usa": usa_cnt,
            "germany": germany_cnt,
        },
        "category_counts": {
            "water": 0,
            "product": 0,
            "pharma": 0,
            "food": 0,
        },
        "lab_type_counts": {
            "connected": connected_cnt,
            "partner": partner_cnt,
        },
    }


# ==============================================================================
# 1. COMMON PRODUCT SEARCH FUNCTION
#    Used by both HomeProductSearchAPI and ProductSearchView
# ==============================================================================

def search_labs_by_product(query, limit=None):
    """
    Common search function for Product Search.
    Searches BranchItem, ProductService, and SubCategory/Category relationships on Branch.
    """
    q = (query or "").strip()
    if not q:
        branches = (
            Branch.objects.filter(is_active=True, is_public=True)
            .prefetch_related(
                "branch_accreditation__accred",
                "lab_scope__certificate__accred",
                "lab_scope__facility_scope__certificate__accred"
            )
            .order_by("-updated_at")[: (limit or 24)]
        )
        labs = [_format_lab_card_product(b, tests=[]) for b in branches]
        return labs, []

    # 1. Fetch matching BranchItems
    branch_items = (
        BranchItem.objects.filter(is_disable=False, is_deleted=False, is_public=True)
        .filter(
            Q(is_title__icontains=q)
            | Q(is_number__icontains=q)
            | Q(description__icontains=q)
            | Q(name__icontains=q)
        )
        .select_related("lab", "lab__lab_state", "lab__lab_country")
        .prefetch_related("lab__branch_accreditation", "lab__branch_accreditation__accred")
        .order_by("is_title")
    )

    # 2. Fetch matching ProductServices
    services = (
        ProductService.objects.filter(is_active=True)
        .filter(Q(name__icontains=q) | Q(summary__icontains=q))
        .select_related("lab", "lab__lab_state", "lab__lab_country")
        .prefetch_related("lab__branch_accreditation", "lab__branch_accreditation__accred")
        .order_by("name")
    )

    # 3. Fetch Labs matching Category or SubCategory relationships directly
    # Note: Using 'subcategories' and 'categories' because query originates on Branch
    subcat_labs = (
        Branch.objects.filter(is_active=True, is_public=True)
        .filter(
            Q(subcategories__name__icontains=q) | Q(categories__name__icontains=q)
        )
        .prefetch_related("branch_accreditation", "branch_accreditation__accred")
        .distinct()
    )

    lab_map = {}
    distinct_products = {}

    # Process Subcategory/Category linked Labs
    for lab in subcat_labs:
        if lab.pk not in lab_map:
            lab_map[lab.pk] = {"lab": lab, "tests": []}
        
        test_title = q
        std = "Subcategory Testing Scope"
        if not any(t["title"] == test_title for t in lab_map[lab.pk]["tests"]):
            lab_map[lab.pk]["tests"].append({
                "id": f"subcat-{lab.pk}",
                "type": "scope",
                "title": test_title,
                "standard": std,
            })

    # Process BranchItems
    for item in branch_items:
        lab = item.lab
        if not lab or not lab.is_active or not lab.is_public:
            continue

        test_title = (item.is_title or "").strip() or (item.name or "").strip() or (item.is_number or "Scope item")
        std = f"Tested against {item.is_number}" if item.is_number else "Tested against certified standard"

        if lab.pk not in lab_map:
            lab_map[lab.pk] = {"lab": lab, "tests": []}

        if not any(t["title"] == test_title for t in lab_map[lab.pk]["tests"]):
            lab_map[lab.pk]["tests"].append({
                "id": str(item.pk),
                "type": "scope",
                "title": test_title,
                "standard": std,
            })

        norm_key = test_title.strip().lower()
        if norm_key not in distinct_products:
            distinct_products[norm_key] = {
                "id": str(item.pk),
                "type": "scope",
                "title": test_title,
                "standard": item.is_number or "",
                "labs": set(),
            }
        if lab.lab_name:
            distinct_products[norm_key]["labs"].add(lab.lab_name)

    # Process ProductServices
    for svc in services:
        lab = svc.lab
        if not lab or not lab.is_active or not lab.is_public:
            continue

        svc_title = (svc.name or "").strip() or "Service"

        if lab.pk not in lab_map:
            lab_map[lab.pk] = {"lab": lab, "tests": []}

        if not any(t["title"] == svc_title for t in lab_map[lab.pk]["tests"]):
            lab_map[lab.pk]["tests"].append({
                "id": str(svc.pk),
                "type": "service",
                "title": svc_title,
                "standard": svc.summary or "Certified Laboratory Testing",
            })

        norm_key = svc_title.strip().lower()
        if norm_key not in distinct_products:
            distinct_products[norm_key] = {
                "id": str(svc.pk),
                "type": "service",
                "title": svc_title,
                "standard": svc.summary or "",
                "labs": set(),
            }
        if lab.lab_name:
            distinct_products[norm_key]["labs"].add(lab.lab_name)

    # Build unique product items list for dropdown
    autocomplete_items = []
    for prod in distinct_products.values():
        labs_set = prod["labs"]
        lab_count = len(labs_set)
        subtitle = f"Offered by {next(iter(labs_set))}" if lab_count == 1 else f"{lab_count} labs offer this testing scope"

        autocomplete_items.append({
            "id": prod["id"],
            "type": prod["type"],
            "title": prod["title"][:180],
            "subtitle": subtitle[:160],
            "lab_count": lab_count,
        })

    if limit:
        autocomplete_items = autocomplete_items[:limit]

    labs = []
    # Sort lab_map entries by promotional ranking priority (Priority Tier 1 Pro, Priority Tier 2 Growth, Priority Tier 3 Basic)
    sorted_lab_entries = sorted(lab_map.values(), key=lambda d: getattr(d["lab"], "priority_tier_level", 3))
    for data in sorted_lab_entries:
        labs.append(_format_lab_card_product(data["lab"], tests=data["tests"]))

    return labs, autocomplete_items

# ==============================================================================
# 2. COMMON LAB SEARCH FUNCTION
#    Used by both HomeLabSearchAPI and LabSearchView
# ==============================================================================

def search_labs_by_name(query, limit=None, subcategory_id=None, category_id=None):
    """
    Common search function for Lab Search.
    Searches the Branch table by lab name, hindi name, org name, city,
    as well as category / subcategory relations and exact name matches.
    """
    q = (query or "").strip()
    branches = Branch.objects.filter(is_active=True, is_public=True)

    filter_q = Q()

    # 1. Search directly by subcategory or category ID if explicitly provided
    if subcategory_id:
        filter_q |= Q(subcategories__id=subcategory_id)
    if category_id:
        filter_q |= Q(categories__id=category_id)

    # 2. Text Search logic
    if q:
        # Check if query matches Category or SubCategory names directly
        matching_subcats = SubCategory.objects.filter(name__iexact=q, active=True)
        matching_cats = Category.objects.filter(name__iexact=q, active=True)

        text_q = (
            Q(lab_name__icontains=q)
            | Q(lab_name_hindi__icontains=q)
            | Q(org_name__icontains=q)
            | Q(lab_city__icontains=q)
        )

        if matching_subcats.exists():
            # Correct field on Branch is 'subcategories'
            text_q |= Q(subcategories__in=matching_subcats)
        else:
            text_q |= Q(subcategories__name__icontains=q)

        if matching_cats.exists():
            # Correct field on Branch is 'categories'
            text_q |= Q(categories__in=matching_cats)
        else:
            text_q |= Q(categories__name__icontains=q)

        filter_q |= text_q

    if filter_q:
        branches = branches.filter(filter_q).distinct()

    branches = branches.prefetch_related(
        "branch_accreditation__accred",
        "lab_scope__certificate__accred",
        "lab_scope__facility_scope__certificate__accred"
    )

    if q:
        branches = branches.annotate(
            search_priority=Case(
                When(lab_city__iexact=q, then=Value(1)),
                When(lab_city__istartswith=q, then=Value(2)),
                When(lab_city__icontains=q, then=Value(3)),
                When(lab_name__iexact=q, then=Value(4)),
                When(lab_name__istartswith=q, then=Value(5)),
                When(lab_name__icontains=q, then=Value(6)),
                When(org_name__icontains=q, then=Value(7)),
                default=Value(8),
                output_field=IntegerField(),
            )
        ).order_by("search_priority", "lab_name")
    else:
        branches = branches.order_by("lab_name")
    if limit:
        branches = branches[:limit]
    else:
        branches = branches[:24]

    # Prioritize results by Promotional Priority Tier (Tier 1 Pro Top Organic, Tier 2 Growth, Tier 3 Basic)
    sorted_branches = sorted(
        list(branches),
        key=lambda b: (getattr(b, "priority_tier_level", 3), getattr(b, "search_priority", 8))
    )

    labs = []
    autocomplete_items = []
    for b in sorted_branches:
        card = _format_lab_card_lab(b)
        labs.append(card)
        autocomplete_items.append({
            "id": str(b.pk),
            "type": "lab",
            "title": b.lab_name or "Laboratory",
            "subtitle": card["location"] or (b.org_name or ""),
            "lab_id": str(b.pk),
            "lab_name": b.lab_name or "",
            "logo": b.lab_logo.url if b.lab_logo else "",
            "url": f"/lab-detail/{b.pk}/",
        })

    return labs, autocomplete_items


# ==============================================================================
# Views
# ==============================================================================

class HomeView(View):
    """
    Public homepage
    """

    def get(self, request, *args, **kwargs):
        # 1. Fetch & decode location parameters
        raw_city = request.GET.get("city") or request.COOKIES.get("user_city", "")
        raw_state = request.GET.get("state") or request.COOKIES.get("user_state", "")

        user_city = unquote(raw_city).strip()
        user_state = unquote(raw_state).strip()

        # 2. Base Queryset for public active branches
        base_qs = (
            Branch.objects.filter(is_active=True, is_public=True)
            .prefetch_related(
                "branch_accreditation__accred",
                "lab_scope__certificate__accred",
                "lab_scope__facility_scope__certificate__accred",
            )
            .exclude(Q(lab_name__isnull=True) | Q(lab_name=""))
        )

        # 3. Location-based branch filtering
        labs_qs = None
        if user_city:
            city_labs = base_qs.filter(lab_city__icontains=user_city)
            if city_labs.exists():
                labs_qs = city_labs

        if labs_qs is None and user_state:
            state_labs = base_qs.filter(lab_state__name__icontains=user_state)
            if state_labs.exists():
                labs_qs = state_labs

        if labs_qs is None:
            labs_qs = base_qs

        labs = labs_qs.order_by("-updated_at")[:24]
        labs_with_logo = [b for b in labs if b.lab_logo]
        labs_ordered = (labs_with_logo + [b for b in labs if not b.lab_logo])[:12]

        # 4. Fetch dynamic Categories and Subcategories with lab count annotations
        # Querying SubCategory -> Branch, so reverse related_name 'labs_subcategories' is used here
        categories = (
            Category.objects.filter(active=True, category_type='Lims')
            .prefetch_related(
                Prefetch(
                    'subcategories',
                    queryset=SubCategory.objects.filter(active=True)
                    .annotate(
                        lab_count=Count(
                            'labs_subcategories',
                            filter=Q(labs_subcategories__is_active=True, labs_subcategories__is_public=True)
                        )
                    )
                    .order_by('order', 'name')
                )
            )
            .order_by('order', 'name')
        )

        context = {
            "labs": labs_ordered,
            "categories": categories,
            "selected_location": user_city or user_state or "",
            "product_search_url": "/api/home/search/products/",
            "lab_search_url": "/api/home/search/labs/",
        }
        return render(request, "home/home.html", context=context)


class ProductSearchView(View):
    """
    Search Result screen when user searches by Product / Material.
    Uses common search_labs_by_product function to query BranchItem, ProductService, and Category/SubCategory.
    Corresponds to figma-screens/Search Result_Product.png.
    """

    def get(self, request, *args, **kwargs):
        q = (request.GET.get("q") or "").strip()

        # Call common search function
        labs, _ac_items = search_labs_by_product(q)

        # Dynamic filter facet counts
        filter_counts = _compute_filter_counts(labs)

        context = {
            "query": q,
            "raw_query": q,
            "results": labs,
            "count": len(labs),
            "country_counts": filter_counts["country_counts"],
            "category_counts": filter_counts["category_counts"],
            "lab_type_counts": filter_counts["lab_type_counts"],
            "product_search_url": "/api/home/search/products/",
            "lab_search_url": "/api/home/search/labs/",
        }
        return render(request, "home/search_product.html", context=context)


class HomeProductSearchAPI(View):
    """
    Autocomplete API for homepage "Search by Product".
    Uses common search_labs_by_product function to query BranchItem and ProductService.
    GET /api/home/search/products/?q=
    """

    def get(self, request, *args, **kwargs):
        q = (request.GET.get("q") or "").strip()
        if len(q) < 2:
            return JsonResponse({"success": True, "results": []})

        # Call common search function
        _labs, autocomplete_items = search_labs_by_product(q, limit=15)
        return JsonResponse(
            {"success": True, "count": len(autocomplete_items), "results": autocomplete_items}
        )


class LabSearchView(View):
    """
    Search Result screen when user searches by Lab Name, Category, or Subcategory.
    Uses common search_labs_by_name function to query Branch table.
    Corresponds to figma-screens/Search Result_by Lab.png.
    """

    def get(self, request, *args, **kwargs):
        q = (request.GET.get("q") or "").strip()
        subcat_id = request.GET.get("subcategory") or request.GET.get("subcat_id")
        cat_id = request.GET.get("category") or request.GET.get("cat_id")

        # Call common search function with subcategory/category filters
        labs, _ac_items = search_labs_by_name(
            q, limit=24, subcategory_id=subcat_id, category_id=cat_id
        )

        # Dynamic filter facet counts
        filter_counts = _compute_filter_counts(labs)

        context = {
            "query": q,
            "raw_query": q,
            "results": labs,
            "count": len(labs),
            "country_counts": filter_counts["country_counts"],
            "category_counts": filter_counts["category_counts"],
            "lab_type_counts": filter_counts["lab_type_counts"],
            "product_search_url": "/api/home/search/products/",
            "lab_search_url": "/api/home/search/labs/",
        }
        return render(request, "home/search_lab.html", context=context)


class HomeLabSearchAPI(View):
    """
    Autocomplete API for homepage "Search by Lab".
    Uses common search_labs_by_name function to query Branch table.
    GET /api/home/search/labs/?q=
    """

    def get(self, request, *args, **kwargs):
        q = (request.GET.get("q") or "").strip()
        if len(q) < 2:
            return JsonResponse({"success": True, "results": []})

        # Call common search function
        _labs, autocomplete_items = search_labs_by_name(q, limit=15)
        return JsonResponse(
            {"success": True, "count": len(autocomplete_items), "results": autocomplete_items}
        )
