from rest_framework.generics import ListAPIView
from apps.labs.models import LabWebPage, ProductService
from apps.labs.serializers import LabMenuTreeSerializer
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.db.models import Q, Avg, Count
from apps.labs.models import Accreditation, Branch, BranchItem, TestingPackage
from apps.enquiries.models import LabReview, ReviewCategory
from django.shortcuts import render, get_object_or_404
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

        # 5. Approved Reviews for this lab
        approved_reviews = (
            LabReview.objects.filter(lab=branch, is_approved=True)
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
        # Annotate active ReviewCategory records with count of ratings belonging to approved reviews of this lab
        review_categories = (
            ReviewCategory.objects.filter(is_active=True)
            .annotate(
                rating_count=Count(
                    "labreviewcategoryrating",
                    filter=Q(
                        labreviewcategoryrating__review__lab=branch,
                        labreviewcategoryrating__review__is_approved=True,
                    ),
                )
            )
            .order_by("sort_order", "name")
        )

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

        # Packages
        packages = (
            TestingPackage.objects.filter(
                lab=branch, is_active=True
            ).prefetch_related("package_items", "products")
        )

        # Dynamic metric calculations
        # accredited_since = ""
        # if branch.establishment_year:
        #     accredited_since = str(branch.establishment_year)
        # elif branch.establishment_date:
        #     accredited_since = str(branch.establishment_date.year)
        # else:
        #     earliest_accred = accreditations.filter(validity_from__isnull=False).order_by("validity_from").first()
        #     if earliest_accred and earliest_accred.validity_from:
        #         accredited_since = str(earliest_accred.validity_from.year)

        tests_completed_count = "0"
        # cat_data = branch.category_data or {}
        # if isinstance(cat_data, dict) and cat_data.get("tests_completed"):
        #     tests_completed_count = str(cat_data.get("tests_completed"))
        # elif scopes.exists():
        #     tests_completed_count = f"{scopes.count()}+"

        if scopes.exists():
            tests_completed_count = f"{scopes.count()}+"

        avg_turnaround = ""
        # if isinstance(cat_data, dict):
        #     avg_turnaround = cat_data.get("turnaround_time") or cat_data.get("avg_turnaround") or ""

        response_rate = ""
        # if isinstance(cat_data, dict):
        #     response_rate = cat_data.get("response_rate") or ""

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

        context = {
            "branch": branch,
            "accreditations": accreditations,
            "product_services": product_services,
            "packages": packages,
            "scopes": scopes,
            "scope_departments": scope_departments,
            "reviews": approved_reviews[:3],
            "reviews_count": reviews_count,
            "overall_avg": round(overall_avg, 1),
            "review_categories": review_categories,
            "rating_histogram": rating_histogram,
            "other_labs": other_labs,
            # "accredited_since": accredited_since,
            "tests_completed_count": tests_completed_count,
            "avg_turnaround": avg_turnaround,
            "response_rate": response_rate,
        }

        return render(request, "labs/lab-detail.html", context=context)

