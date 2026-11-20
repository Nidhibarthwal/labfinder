from django.http import JsonResponse
from django.utils import timezone
from rest_framework.generics import ListAPIView
from apps.labs.models import (
    LabWebPage, ProductService, Accreditation, Branch, BranchItem, TestingPackage,
    PromotionalPlan, PromotionalAddon, LabPlanSubscription, LabPromotionBanner, LabAddonPurchase
)
from apps.labs.serializers import LabMenuTreeSerializer
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.db.models import Q, Avg, Count
from apps.enquiries.models import LabReview, ReviewCategory
from apps.utility.models import AccreditationMaster


class LabNavigationMenuAPIView(ListAPIView):
    """Endpoint for rendering website navigation menus for a given logged-in lab."""
    serializer_class = LabMenuTreeSerializer

    def get_queryset(self):
        branch_id = self.kwargs.get('branch_id')
        return LabWebPage.objects.filter(
            lab_id=branch_id, 
            parent__isnull=True, 
            is_active=True
        ).prefetch_related('submenus')


class LabDetailView(View):

    def get(self, request, *args, **kwargs):
        branch_id = self.kwargs.get("id") or self.kwargs.get("pk")
        branch = get_object_or_404(Branch, pk=branch_id)

        # 1. Active certificates
        accreditations = Accreditation.objects.filter(
            lab=branch, active=True
        ).select_related("accred")

        # 2. Accreditation masters
        accreditation_masters = (
            AccreditationMaster.objects.filter(
                accreditation__lab=branch, accreditation__active=True
            )
            .distinct()
            .order_by("order", "name")
        )

        # Services
        product_services = (            
            ProductService.objects.filter(
                lab=branch, is_active=True
                )
                .distinct()
        )

        # 3. Scopes
        scopes = (
            BranchItem.objects.filter(
                lab=branch, is_deleted=False, is_disable=False
            )
            .select_related("service_category", "unit")
            .prefetch_related(
                "test_type",
                "certificate__accred",  # direct certificates on scope if any
                "facility_scope__certificate__accred",  # facility-level certificates
            )
            .order_by("sort_order")
        )

        # 4. Scope departments
        scope_departments = []
        seen_dept_ids = set()
        for scope in scopes:
            for dept in scope.test_type.all():
                if dept.id not in seen_dept_ids:
                    seen_dept_ids.add(dept.id)
                    scope_departments.append(dept)

        # 5. Approved Reviews for this lab (excluding reviews hidden by lab)
        approved_reviews = (
            LabReview.objects.filter(
                lab=branch, is_approved=True, is_hidden_by_lab=False
            )
            .select_related("user")
            .prefetch_related("category_ratings__category")
            .order_by("-created_at")
        )

        reviews_count = approved_reviews.count()
        overall_avg = (
            approved_reviews.aggregate(Avg("overall_rating"))[
                "overall_rating__avg"
            ]
            or 0.0
        )

        # 6. Dynamic Review Category Counts from LabReviewCategoryRating
        # Annotate active ReviewCategory records with count of ratings belonging to approved, non-hidden reviews of this lab
        review_categories = (
            ReviewCategory.objects.filter(is_active=True)
            .annotate(
                rating_count=Count(
                    "labreviewcategoryrating",
                    filter=Q(
                        labreviewcategoryrating__review__lab=branch,
                        labreviewcategoryrating__review__is_approved=True,
                        labreviewcategoryrating__review__is_hidden_by_lab=False,
                    ),
                )
            )
            .order_by("sort_order", "name")
        )

        positive_categories = []
        negative_categories = []
        for cat in review_categories:
            display_count = cat.rating_count if cat.rating_count > 0 else 0
            item = {
                "pk": cat.pk,
                "name": cat.name,
                "count": display_count,
                "review_type": cat.review_type,
            }
            if cat.review_type == "positive":
                positive_categories.append(item)
            else:
                negative_categories.append(item)

        positive_categories.sort(key=lambda x: x["count"], reverse=True)
        negative_categories.sort(key=lambda x: x["count"], reverse=True)

        # 7. Dynamic Star Rating Histogram Breakdown (1 to 5 stars)
        rating_histogram = []
        if reviews_count > 0:
            for star in range(5, 0, -1):
                # Count reviews falling into integer score brackets (e.g., 4.5 - 5.0 for 5 star)
                if star == 5:
                    count = approved_reviews.filter(
                        overall_rating__gte=4.5
                    ).count()
                elif star == 1:
                    count = approved_reviews.filter(
                        overall_rating__lt=1.5
                    ).count()
                else:
                    count = approved_reviews.filter(
                        overall_rating__gte=star - 0.5,
                        overall_rating__lt=star + 0.5,
                    ).count()

                percentage = round((count / reviews_count) * 100, 1)
                rating_histogram.append(
                    {"star": star, "count": count, "percentage": percentage}
                )
        else:
            default_dist = [(5, 72.0), (4, 22.0), (3, 15.0), (2, 8.0), (1, 5.0)]
            for star, pct in default_dist:
                rating_histogram.append({"star": star, "count": 0, "percentage": pct})

        # Packages
        packages = (
            TestingPackage.objects.filter(
                lab=branch, is_active=True
            ).prefetch_related("package_items", "products")
        )

        tests_completed_count = "0"
        if scopes.exists():
            tests_completed_count = f"{scopes.count()}+"

        avg_turnaround = ""
        response_rate = ""

        # Ad-free profile check: Hide competitor ads / other labs if active plan has hide_competitor_ads
        if branch.has_ad_free_profile:
            other_labs = Branch.objects.none()
        else:
            # Other labs with dynamic ratings and badges
            other_labs = (
                Branch.objects.filter(is_active=True)
                .exclude(pk=branch.pk)
                .annotate(
                    avg_rating=Avg(
                        "reviews__overall_rating",
                        filter=Q(reviews__is_approved=True),
                    )
                )
                .prefetch_related("branch_accreditation__accred")
                .order_by("-avg_rating", "lab_name")[:4]
            )

        # Active promotional subscription & promotional assets
        active_sub = branch.active_promotional_subscription
        carousel_banners = list(active_sub.carousel_banners.filter(is_active=True).order_by('sort_order')) if active_sub else []

        context = {
            "branch": branch,
            "active_sub": active_sub,
            "carousel_banners": carousel_banners,
            "accreditations": accreditations,
            "product_services": product_services,
            "packages": packages,
            "scopes": scopes,
            "scope_departments": scope_departments,
            "reviews": approved_reviews[:3],
            "all_reviews": approved_reviews,
            "reviews_count": reviews_count,
            "overall_avg": round(overall_avg, 1),
            "review_categories": review_categories,
            "positive_categories": positive_categories,
            "negative_categories": negative_categories,
            "rating_histogram": rating_histogram,
            "other_labs": other_labs,
            "tests_completed_count": tests_completed_count,
            "avg_turnaround": avg_turnaround,
            "response_rate": response_rate,
        }

        return render(request, "labs/lab-detail.html", context=context)


class PurchasePromotionalPlanView(View):
    """
    Handles purchase and verification application for Promotional Plans:
    - Verified Lab (Growth): ₹4,999 / 30 Days, Priority Tier 2, GST/License verification, 1 Static Header Banner
    - Trusted Partner (Pro): ₹14,999 / 30 Days, Priority Tier 1, NABL/ISO verification, Carousel Banners + Video, Direct CTAs, Hide Reviews, Ad-free
    """
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"status": "error", "message": "Please log in to upgrade plan."}, status=401)

        from apps.accounts.views import get_current_branch
        lab = get_current_branch(request)
        if not lab:
            # Fallback to direct user ownership or email match
            lab = Branch.objects.filter(user=request.user).first()
            if not lab and request.user.email:
                lab = Branch.objects.filter(contact_email__iexact=request.user.email).first()

        if not lab:
            return JsonResponse({"status": "error", "message": "Laboratory profile not found for this account."}, status=404)

        plan_slug = request.POST.get("plan_slug", "").strip()
        if not plan_slug:
            return JsonResponse({"status": "error", "message": "Promotional plan slug is required."}, status=400)

        plan = get_object_or_404(PromotionalPlan, slug=plan_slug, is_active=True)

        # Create or update subscription
        subscription = LabPlanSubscription(
            lab=lab,
            plan=plan,
            amount=plan.base_price,
            status='submitted',
            payment_status='paid',
        )

        # 1. Growth Plan fields
        if plan.slug in ('growth', 'pro'):
            gst_no = request.POST.get('gst_number', '').strip()
            lic_no = request.POST.get('license_number', '').strip()
            if gst_no:
                subscription.gst_number = gst_no
            if lic_no:
                subscription.license_number = lic_no
            if 'gst_license_document' in request.FILES:
                subscription.gst_license_document = request.FILES['gst_license_document']

            if 'static_header_banner' in request.FILES:
                subscription.static_header_banner = request.FILES['static_header_banner']
            static_link = request.POST.get('static_banner_link', '').strip()
            if static_link:
                subscription.static_banner_link = static_link

        # 2. Pro Plan fields
        if plan.slug == 'pro':
            nabl_no = request.POST.get('nabl_accreditation_number', '').strip()
            if nabl_no:
                subscription.nabl_accreditation_number = nabl_no
            if 'nabl_document' in request.FILES:
                subscription.nabl_document = request.FILES['nabl_document']

            iso_no = request.POST.get('iso_certification_number', '').strip()
            if iso_no:
                subscription.iso_certification_number = iso_no
            if 'iso_document' in request.FILES:
                subscription.iso_document = request.FILES['iso_document']

            video_url = request.POST.get('promotional_video_url', '').strip()
            if video_url:
                subscription.promotional_video_url = video_url

            direct_phone = request.POST.get('direct_phone', '').strip()
            if direct_phone:
                subscription.direct_phone = direct_phone

            whatsapp = request.POST.get('whatsapp_number', '').strip()
            if whatsapp:
                subscription.whatsapp_number = whatsapp

            instant_rfq_val = request.POST.get('enable_instant_rfq', 'true').lower()
            subscription.enable_instant_rfq = instant_rfq_val in ('true', '1', 'on')

            hide_reviews_val = request.POST.get('hide_reviews', 'false').lower()
            subscription.hide_reviews = hide_reviews_val in ('true', '1', 'on')

        # Set verification status
        if plan.slug == 'basic':
            subscription.verification_status = 'not_required'
        else:
            subscription.verification_status = 'approved'  # Auto-verify on purchase for immediate benefits

        # Activate the subscription
        subscription.save()
        subscription.activate_subscription()

        # Save Carousel Banners for Pro Plan (up to 3)
        if plan.slug == 'pro':
            # Remove previous carousel banners for this subscription if updating
            subscription.carousel_banners.all().delete()
            for idx in range(1, 4):
                file_key = f'carousel_banner_{idx}'
                if file_key in request.FILES:
                    LabPromotionBanner.objects.create(
                        subscription=subscription,
                        image=request.FILES[file_key],
                        sort_order=idx,
                        is_active=True
                    )

        return JsonResponse({
            "status": "success",
            "message": f"Successfully activated {plan.name}! Your promotional features and badges are now live.",
            "plan_name": plan.name,
            "plan_slug": plan.slug,
            "amount": float(plan.base_price),
            "priority_tier": plan.get_priority_tier_level_display() if hasattr(plan, 'get_priority_tier_level_display') else f"Tier {plan.priority_tier_level}",
            "expires_at": subscription.expires_at.strftime("%d %b %Y") if subscription.expires_at else "Ongoing",
        })


class PurchasePromotionalAddonView(View):
    """
    Handles purchasing Promotional Add-ons:
    - Category Featured Lab Pin
    - Competitor Targeting
    - Home Page Listing
    """
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"status": "error", "message": "Please log in to purchase add-ons."}, status=401)

        from apps.accounts.views import get_current_branch
        from apps.utility.models import Category
        lab = get_current_branch(request) or Branch.objects.filter(user=request.user).first()
        if not lab:
            return JsonResponse({"status": "error", "message": "Laboratory profile not found."}, status=404)

        addon_code = request.POST.get("addon_code", "").strip()
        addon = get_object_or_404(PromotionalAddon, code=addon_code, is_active=True)

        target_cat_id = request.POST.get("target_category_id")
        target_category = Category.objects.filter(pk=target_cat_id).first() if target_cat_id else None

        target_comp_id = request.POST.get("target_competitor_lab_id")
        target_competitor = Branch.objects.filter(pk=target_comp_id).first() if target_comp_id else None

        now = timezone.now()
        purchase = LabAddonPurchase.objects.create(
            lab=lab,
            addon=addon,
            target_category=target_category,
            target_competitor_lab=target_competitor,
            banner_headline=request.POST.get("banner_headline", ""),
            banner_link=request.POST.get("banner_link", ""),
            price_paid=addon.base_price,
            status='active',
            starts_at=now,
            expires_at=now + timezone.timedelta(days=addon.duration_days)
        )
        if 'banner_image' in request.FILES:
            purchase.banner_image = request.FILES['banner_image']
            purchase.save()

        return JsonResponse({
            "status": "success",
            "message": f"Successfully activated {addon.name} for {addon.duration_days} days!",
            "addon_name": addon.name,
            "price_paid": float(addon.base_price),
            "expires_at": purchase.expires_at.strftime("%d %b %Y")
        })


