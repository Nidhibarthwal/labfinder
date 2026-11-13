from apps.customers.views import render_customer_dashboard
from apps.enquiries.models import Enquiry
from apps.enquiries.views import get_leads_dashboard_context, get_reviews_dashboard_context, get_orders_dashboard_context
from apps.utility.models import Country, Department, Discipline, State, Unit
import json
import secrets
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from apps.accounts.models import OTPVerification
from django.contrib.auth import authenticate, login, logout, get_user_model
User = get_user_model()
from apps.labs.models import (
    Branch, BranchImage, LabCategory, LabSocialLink, ProductService, TestingPackage, TestingPackageItem, User,
    Accreditation, BranchItem, TestingScopeFacility, BranchManpower,
)
from django.contrib.auth.models import User, Group
from django.middleware.csrf import get_token
import re
from apps.samples_configurations.models import TestMethod, Category, SubCategory
from config.settings_local import SERVER_LIVE
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from decimal import Decimal
import requests
import logging
logger = logging.getLogger(__name__)

@require_POST
def account_api_login(request):
    """
    Accepts username OR email (modal posts name=\"email\").
    Users are created with username=email at signup.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request method."})

    raw_id = (
        request.POST.get("email")
        or request.POST.get("username")
        or ""
    ).strip()
    password = (request.POST.get("password") or "").strip()

    if not raw_id or not password:
        return JsonResponse(
            {
                "success": False,
                "message": "Email and password are required.",
            }
        )

    login_username = raw_id
    # If client sent an email, resolve to the account username
    if "@" in raw_id:
        email = raw_id.lower()
        user_obj = (
            User.objects.filter(email__iexact=email).first()
            or User.objects.filter(username__iexact=email).first()
        )
        if user_obj:
            login_username = user_obj.get_username()

    user = authenticate(request, username=login_username, password=password)

    # Fallback: try email-as-username lowercased (signup stores username=email.lower())
    if user is None and "@" in raw_id:
        user = authenticate(request, username=raw_id.lower(), password=password)

    if user is not None:
        if not user.is_active:
            return JsonResponse(
                {
                    "success": False,
                    "message": "This account is inactive. Please contact support.",
                }
            )
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return JsonResponse(
            {
                "success": True,
                "message": "Login successful.",
                "csrf_token": get_token(request),
            }
        )

    return JsonResponse(
        {
            "success": False,
            "message": "Invalid email or password.",
        }
    )


def account_api_signup(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "").strip()
        group_name = request.POST.get("user_group", "Customer").strip()
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()

        if not email or not password:
            return JsonResponse({"success": False, "message": "Email and password are required."})

        if User.objects.filter(username__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
            return JsonResponse({"success": False, "message": "An account with this email already exists. Please log in."})

        try:
            # 1. Create User (username = email for customer login)
            if not first_name and full_name:
                parts = full_name.split()
                first_name = parts[0]
                last_name = " ".join(parts[1:]) if len(parts) > 1 else last_name
            if not first_name:
                first_name = email.split("@")[0]

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            # 2. Assign to Group ('Customer' by default)
            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)

            # 3. Log user in
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            # 4. Return success response with rotated CSRF token
            return JsonResponse({
                "success": True,
                "message": "User registered and logged in successfully.",
                "csrf_token": get_token(request)
            })

        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})

    return JsonResponse({"success": False, "message": "Invalid request method."})


def get_current_branch(request):
    branch_id = request.POST.get("branch_id") or request.GET.get("branch_id")
    if branch_id:
        branch = Branch.objects.filter(id=branch_id).first()
        if branch:
            return branch

    email = request.session.get("registration_email")
    if email:
        email = email.strip().lower()
        branch = Branch.objects.filter(contact_email__iexact=email).first()
        if branch:
            return branch

    if request.user.is_authenticated:
        branch = getattr(request.user, "lab_user", None)
        if branch:
            return branch
        branch = Branch.objects.filter(contact_email__iexact=request.user.email).first()
        if branch:
            return branch

    return None


def parse_excel_or_csv(file_obj):
    """
    Parses an uploaded .xlsx, .xls, or .csv file and returns a list of dicts:
    [{"name": "...", "method": "...", "unit": "..."}, ...]
    """
    import io
    filename = getattr(file_obj, "name", "").lower()
    raw_rows = []

    if hasattr(file_obj, "seek"):
        file_obj.seek(0)
    content = file_obj.read()
    if hasattr(file_obj, "seek"):
        file_obj.seek(0)

    if filename.endswith(".csv"):
        import csv
        if isinstance(content, bytes):
            for enc in ("utf-8-sig", "utf-8", "latin1", "cp1252"):
                try:
                    text = content.decode(enc)
                    break
                except UnicodeDecodeError:
                    text = ""
        else:
            text = content
        reader = csv.reader(text.splitlines())
        raw_rows = [list(r) for r in reader]
    else:
        import openpyxl
        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            ws = wb.active
            raw_rows = [list(r) for r in ws.iter_rows(values_only=True)]
        except Exception as e:
            raise ValueError(f"Unable to read Excel file. Please ensure it is a valid .xlsx or .csv file. Details: {e}")

    if not raw_rows:
        return []

    # Detect header row within the first 10 rows
    param_col = None
    method_col = None
    unit_col = None
    start_idx = 0

    header_keywords = ("param", "test", "name", "property", "standard", "method", "spec", "unit", "limit", "range", "requirement", "protocol", "uom")

    for r_idx in range(min(10, len(raw_rows))):
        row_cells = [str(c or "").strip().lower() for c in raw_rows[r_idx]]
        # Count keyword matches in this row
        matches = [idx for idx, cell in enumerate(row_cells) if any(kw in cell for kw in header_keywords)]
        if len(matches) >= 2 or any("param" in cell or "test name" in cell or "property" in cell for cell in row_cells):
            start_idx = r_idx + 1
            for idx, col_name in enumerate(row_cells):
                # Ignore serial number columns
                if any(sr in col_name for sr in ("sr", "s.no", "sl.", "sl no", "serial")):
                    continue
                if param_col is None and any(k in col_name for k in ("param", "test name", "name of test", "property", "item", "test")):
                    param_col = idx
                elif method_col is None and any(k in col_name for k in ("method", "standard", "is code", "spec", "protocol", "procedure")):
                    method_col = idx
                elif unit_col is None and any(k in col_name for k in ("unit", "limit", "range", "requirement", "uom", "acceptance")):
                    unit_col = idx
            break

    # If no header detected or columns not identified, use positional fallbacks
    if param_col is None:
        param_col = 0
    if method_col is None:
        method_col = 1 if len(raw_rows[0]) > 1 else 0
    if unit_col is None:
        unit_col = 2 if len(raw_rows[0]) > 2 else (1 if len(raw_rows[0]) > 1 else 0)

    rows_data = []
    for row in raw_rows[start_idx:]:
        if not row:
            continue
        p_name = str(row[param_col] if len(row) > param_col and row[param_col] is not None else "").strip()
        p_method = str(row[method_col] if len(row) > method_col and row[method_col] is not None else "").strip()
        p_unit = str(row[unit_col] if len(row) > unit_col and row[unit_col] is not None else "").strip()

        # Ignore empty row or header repeats
        if p_name and p_name.lower() not in ("none", "nan", "null") and not any(kw in p_name.lower() for kw in ("parameter", "test name", "sr no")):
            rows_data.append({
                "name": p_name,
                "method": p_method if p_method.lower() not in ("none", "nan", "null") else "",
                "unit": p_unit if p_unit.lower() not in ("none", "nan", "null") else "",
            })

    return rows_data


def generate_otp():
    return f"{secrets.randbelow(100000):05d}"


def send_otp(email):
    email = email.strip().lower()
    otp = generate_otp()
    
    with transaction.atomic():
        # Invalidate previously active OTPs
        OTPVerification.objects.filter(
            email__iexact=email,
            status=OTPVerification.Status.ACTIVE,
        ).update(
            status=OTPVerification.Status.INVALIDATED
        )

        # Create new OTP
        otp_record = OTPVerification.objects.create(
            email=email,
            otp_code=otp,
            status=OTPVerification.Status.ACTIVE,
        )

        # Send email
        send_mail(
            subject="Your LabFinder Verification Code",
            message=(
                f"Your LabFinder verification code is {otp}.\n\n"
                "This code is valid for 5 minutes.\n"
                "If you did not request this code, please ignore this email."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

    return otp_record


@method_decorator(never_cache, name="dispatch")
class RegisterView(View):

    def get(self, request, *args, **kwargs):
        return render(request, "accounts/register.html")

    def post(self, request, *args, **kwargs):
        try:
            if request.content_type == "application/json":
                data = json.loads(request.body)
                email = data.get("email", "").strip().lower()
            else:
                email = request.POST.get("email", "").strip().lower()

        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid request data."
                },
                status=400,
            )

        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Please enter a valid email address."
                },
                status=400,
            )

        # user = User.objects.filter(username=email).first()
        # if user:
        #     redirect_url = ""
        #     branch = Branch.objects.filter(user=user).first()   
        #     if branch:
        #         request.session["registration_email"] = email
        #         request.session["email_verified"] = True
        #         if branch.status == "approved":
        #             backend = request.session.get(
        #                 "auth_backend",
        #                 "django.contrib.auth.backends.ModelBackend"
        #             )
        #             if user.is_active:
        #                 login(request, user, backend=backend)        
        #             else:
        #                 return JsonResponse(
        #                     {
        #                         "success": False,
        #                         "message": "Unable to process registration. User not active"
        #                     },
        #                     status=500,
        #                 )          
        #             redirect_url = "/dashboard/"
        #         elif branch.status == "claimed":
        #             redirect_url = "/lab-review-detail/"   
        #         elif branch.status == "unclaimed":
        #             redirect_url = "/claim-labs/"       
        #     else:
        #         ''' user not linked with any branch. 
        #         ask user to enter website url'''
        #         redirect_url = "/lab-website-url/"

        #     return JsonResponse(
        #         {
        #             "success": True,
        #             "message": "Email already registered.",
        #             "redirect_to": redirect_url
        #         },
        #         status=200,
        #     )

        try:
            if settings.SERVER_LIVE:
                send_otp(email)

            # Save registration information in session
            request.session["registration_email"] = email
            request.session["pending_registration"] = {"email": email}
            request.session["email_verified"] = False

            return JsonResponse(
                {
                    "success": True,
                    "message": "OTP sent successfully.",
                    "redirect_to": "/verify-email/"
                },
                status=200,
            )

        except Exception as e:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Unable to process registration."
                },
                status=500,
            )


@method_decorator(never_cache, name="dispatch")
class VerifyEmailView(View):
    """
    Display OTP verification page and verify the 5-digit OTP.

    OTP verification is required only when SERVER_LIVE is True.
    When SERVER_LIVE is False, email verification is bypassed.
    """

    def get_redirect_url(self, email):
        """
        Decide where the user should go after email verification.
        """
        matched_branches = Branch.objects.filter(
            contact_email__iexact=email
        )
        print("***************** email *************",email)
        print("***************** matched_branches *************",matched_branches)
        if matched_branches.exists():
            # At least one branch is already claimed
            if matched_branches.filter(status="approved").exists():
                user = User.objects.filter(username=email).first()
                if user:
                    branch = Branch.objects.filter(user=user).first()   
                    if branch:
                        if user.is_active:
                            backend = self.request.session.get(
                                "auth_backend",
                                "django.contrib.auth.backends.ModelBackend"
                            )                            
                            login(self.request, user, backend=backend)        
        #             
                return reverse("dashboard")
            elif matched_branches.filter(status="claimed").exists():
                return reverse("lab-review-detail")
            # Branches found but none claimed
            print("***************** Branches found but none claimed *************")
            return reverse("claim-labs")

        # No branch found for this email
        print("***************** No branch found for this email *************")
        return reverse("lab-website-url")

    def get(self, request, *args, **kwargs):
        email = request.session.get("registration_email")
        if not email:
            return redirect("register")

        email = email.strip().lower()

        # -------------------------------------------------
        # OTP is required ONLY on live server
        # -------------------------------------------------
        if not settings.SERVER_LIVE:
            request.session["email_verified"] = True
            redirect_url = self.get_redirect_url(email)
            return redirect(redirect_url)

        # -------------------------------------------------
        # Live server - check whether already verified
        # -------------------------------------------------
        if request.session.get("email_verified") is True:
            redirect_url = self.get_redirect_url(email)
            return redirect(redirect_url)

        otp_record = (
            OTPVerification.objects
            .filter(
                email__iexact=email,
                status=OTPVerification.Status.ACTIVE,
            )
            .order_by("-created_at")
            .first()
        )

        expiry_secs = 0
        resend_secs = 0

        if otp_record:
            elapsed = int(
                (
                    timezone.now() -
                    otp_record.created_at
                ).total_seconds()
            )
            expiry_secs = max(0, 300 - elapsed)
            resend_secs = max(0, 60 - elapsed)

        expiry_formatted = (
            f"{expiry_secs // 60:02d}:"
            f"{expiry_secs % 60:02d}"
            if expiry_secs > 0
            else "Expired"
        )

        return render(
            request,
            "accounts/verify_email.html",
            {
                "email": email,
                "otp_expiry_seconds": expiry_secs,
                "otp_expiry_formatted": expiry_formatted,
                "resend_cooldown_seconds": resend_secs,
            }
        )

    def post(self, request, *args, **kwargs):
        email = request.session.get("registration_email")
        if not email:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Session expired. Please register again."
                },
                status=400,
            )

        email = email.strip().lower()

        # -------------------------------------------------
        # OTP is required ONLY on live server
        # -------------------------------------------------
        if not settings.SERVER_LIVE:
            request.session["email_verified"] = True
            redirect_url = self.get_redirect_url(email)
            return JsonResponse(
                {
                    "success": True,
                    "message": "Email verified successfully.",
                    "redirect_url": redirect_url,
                }
            )

        # Handle Resend OTP
        action = request.POST.get("action")
        if action == "resend":
            try:
                send_otp(email)
                return JsonResponse(
                    {
                        "success": True,
                        "message": "A new OTP has been sent to your email.",
                    }
                )
            except Exception as e:
                return JsonResponse(
                    {
                        "success": False,
                        "message": f"Unable to send OTP. Please try again. {e}",
                    },
                    status=500,
                )

        # Always reset before actual verification
        request.session["email_verified"] = False

        otp = request.POST.get("otp", "").strip()

        if not otp:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Please enter the OTP.",
                },
                status=400,
            )

        if not otp.isdigit() or len(otp) != 5:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Please enter a valid 5-digit OTP.",
                },
                status=400,
            )

        otp_record = (
            OTPVerification.objects
            .filter(
                email__iexact=email,
                status=OTPVerification.Status.ACTIVE,
            )
            .order_by("-created_at")
            .first()
        )

        if not otp_record:
            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "No active OTP found. "
                        "Please request a new OTP."
                    ),
                },
                status=400,
            )

        if otp_record.is_expired():
            otp_record.status = OTPVerification.Status.EXPIRED
            otp_record.save(update_fields=["status"])
            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "This OTP has expired. "
                        "Please request a new OTP."
                    ),
                },
                status=400,
            )

        if otp_record.attempts >= 3:
            otp_record.status = OTPVerification.Status.INVALIDATED
            otp_record.save(update_fields=["status"])
            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "Too many failed attempts. "
                        "Please request a new OTP."
                    ),
                },
                status=400,
            )

        if otp_record.otp_code == otp:
            otp_record.status = OTPVerification.Status.VERIFIED
            otp_record.verified_at = timezone.now()
            otp_record.save(
                update_fields=[
                    "status",
                    "verified_at",
                ]
            )

            request.session["email_verified"] = True
            redirect_url = self.get_redirect_url(email)

            return JsonResponse(
                {
                    "success": True,
                    "message": "Email verified successfully.",
                    "redirect_url": redirect_url,
                }
            )

        otp_record.attempts += 1

        if otp_record.attempts >= 3:
            otp_record.status = OTPVerification.Status.INVALIDATED
            otp_record.save(
                update_fields=[
                    "attempts",
                    "status",
                ]
            )
            return JsonResponse(
                {
                    "success": False,
                    "message": (
                        "Too many failed attempts. "
                        "Please request a new OTP."
                    ),
                    "attempts_remaining": 0,
                },
                status=400,
            )

        otp_record.save(update_fields=["attempts"])

        remaining = 3 - otp_record.attempts

        return JsonResponse(
            {
                "success": False,
                "message": (
                    f"Invalid OTP. "
                    f"You have {remaining} attempts remaining."
                ),
                "attempts_remaining": remaining,
            },
            status=400,
        )


class LabWebsiteURLView(View):
    """
    Class-based view for rendering the lab website detail page (GET).
    """
    def get(self, request, *args, **kwargs):
        email = request.session.get("registration_email")
        if not email:
            return redirect("register")

        email = email.strip().lower()

        return render(
            request,
            "accounts/lab_website_detail.html",
            {
                "email": email,
            }
        )


# @method_decorator(never_cache, name='dispatch')
# class LabReviewDetailViewOld(View):
#     """
#     Class-based view for displaying lab review details after profile is claimed.
#     """
#     def get(self, request, *args, **kwargs):
#         email = request.session.get("registration_email")
#         if not email or not request.session.get("email_verified"):
#             return redirect("register")

#         email = email.strip().lower()
#         branches = Branch.objects.filter(contact_email__iexact=email)
#         current_branch = branches.first()
#         social_media_links = LabSocialLink.objects.filter(lab=current_branch, is_active=True)
#         # ── 1. Accreditation data for the lab ─────────────────────────────────
#         accreditation = (
#             Accreditation.objects
#             .filter(lab=current_branch, active=True)
#             .select_related("accred")
#             .order_by("id")
#         )

#         # ── 3. Lab photos (all image / base64 fields from Branch) ─────────────
#         lab_photos = {
#             "lab_logo": current_branch.lab_logo if current_branch else None,
#             "logo_base64": current_branch.logo_base64 if current_branch else None,
#             "lab_footer_logo": current_branch.lab_footer_logo if current_branch else None,
#             "logo_footer_base64": current_branch.logo_footer_base64 if current_branch else None,
#             "nabl_logo": current_branch.nabl_logo if current_branch else None,
#             "nabl_logo_calibration": current_branch.nabl_logo_calibration if current_branch else None,
#             "cover_picture": current_branch.cover_picture if current_branch else None,
#             "cover_base64": current_branch.cover_base64 if current_branch else None,
#         }

#         # ── 2. Testing scopes with nested facilities ───────────────────────────
#         scopes_with_facilities = (
#             BranchItem.objects
#             .filter(lab=current_branch, is_deleted=False, is_disable=False)
#             .select_related("service_category", "unit", "gst")
#             .prefetch_related(
#                 "facility_scope",                       # TestingScopeFacility reverse FK
#                 "facility_scope__test_type",            # Department FK on each facility
#                 "facility_scope__range_value",          # FacilityRangeValue M2M
#                 "facility_scope__range_values",         # ParameterRangeValue M2M
#                 "facility_scope__qualitative_values",   # ParameterQualitativeValue M2M
#                 "facility_scope__certificate",          # Accreditation M2M on facility
#                 "certificate",                          # Accreditation M2M on scope
#                 "test_type",                            # Department M2M on scope
#                 "category",                             # Category M2M on scope
#             )
#             .order_by("sort_order", "is_number")
#         )

#         # Collect unique departments present in the fetched scopes for filter tabs
#         scope_departments = []
#         seen_dept_ids = set()
#         for scope in scopes_with_facilities:
#             for dept in scope.test_type.all():
#                 if dept.id not in seen_dept_ids:
#                     seen_dept_ids.add(dept.id)
#                     scope_departments.append(dept)


#         ALL_SOCIAL_PLATFORMS = [
#             "youtube",
#             "facebook",
#             "instagram",
#             "linkedin",
#             "twitter",
#         ]

#         social_media_links = list(social_media_links)

#         existing_platforms = {
#             social.platform.lower()
#             for social in social_media_links
#         }

#         missing_platforms = [
#             platform
#             for platform in ALL_SOCIAL_PLATFORMS
#             if platform not in existing_platforms
#         ]

#         return render(
#             request,
#             "accounts/review-details.html",
#             {
#                 "email": email,
#                 "branch": current_branch,
#                 "branches": branches,
#                 "social_media_links": social_media_links,
#                 "missing_platforms": missing_platforms,
#                 "accreditation": accreditation,
#                 "lab_photos": lab_photos,
#                 "all_disciplines": Discipline.objects.all().order_by('order'),
#                 "all_departments": Department.objects.all().order_by('order'),
#                 "scopes_with_facilities": scopes_with_facilities,
#                 "scope_departments": scope_departments,
#                 "countries" : Country.objects.all(),
#                 "states": State.objects.all(),
#             }
#         )

#     def post(self, request, *args, **kwargs):
#         email = request.session.get("registration_email")
#         if not email or not request.session.get("email_verified"):
#             return redirect("register")

#         email = email.strip().lower()
#         branches = Branch.objects.filter(contact_email__iexact=email)
#         current_branch = branches.first()
        
#         if not current_branch:
#             return redirect("register")

#         try:
#             # ── 1. Identity & Contact Information ─────────────────────────────
#             current_branch.lab_name = request.POST.get("legal_lab_name", current_branch.lab_name)
#             current_branch.contact_mobile = request.POST.get("phone_number", current_branch.contact_mobile)
#             current_branch.contact_email = request.POST.get("contact_email", current_branch.contact_email)
#             current_branch.lab_address = request.POST.get("facility_address", current_branch.lab_address)
#             current_branch.lab_pincode = request.POST.get("facility_postal_code", current_branch.lab_pincode)

#             country_id = request.POST.get("facility_country")
#             if country_id:
#                 current_branch.lab_country = Country.objects.filter(id=country_id).first()
#             else:
#                 current_branch.lab_country = None

#             state_id = request.POST.get("facility_state")
#             if state_id:
#                 current_branch.lab_state = State.objects.filter(id=state_id).first()
#             else:
#                 current_branch.lab_state = None

#             if "lab_logo" in request.FILES:
#                 current_branch.lab_logo = request.FILES["lab_logo"]

#             # ── 2. Lab Overview (Executive Summary & Tags) ────────────────────
#             exec_summary = request.POST.get("executive_summary")
#             if exec_summary is not None:
#                 current_branch.description = exec_summary

#             # 3. Save selected Test Disciplines (toggled via interface/hidden inputs)
#             discipline_names = request.POST.getlist("disciplines")
#             if discipline_names:
#                 discipline_objs = Discipline.objects.filter(name__in=discipline_names)
#                 current_branch.disciplines.set(discipline_objs)
#             else:
#                 current_branch.disciplines.clear()

#             # 4. Save selected Types of Testing / Departments
#             department_names = request.POST.getlist("departments")
#             if department_names:
#                 dept_objs = Department.objects.filter(name__in=department_names)
#                 current_branch.departments.set(dept_objs)
#             else:
#                 current_branch.departments.clear()

#             # ── 5. Social Media Links ─────────────────────────────────────────
#             submitted_platforms = [p.lower() for p in request.POST.getlist("social_platform") if p.strip()]
#             platforms = request.POST.getlist("social_platform")
#             urls = request.POST.getlist("social_url")
            
#             # Delete platforms that were removed from the UI
#             LabSocialLink.objects.filter(lab=current_branch).exclude(platform__in=submitted_platforms).delete()

#             for platform, url in zip(platforms, urls):
#                 if platform and url.strip():
#                     LabSocialLink.objects.update_or_create(
#                         lab=current_branch,
#                         platform=platform.lower(),
#                         defaults={"url": url.strip(), "is_active": True}
#                     )

#             # ── 6 Detailed Services / Product Services ───────────────────────
#             submitted_service_ids = request.POST.getlist("existing_service_id[]")
#             # Delete services whose IDs are no longer in the DOM
#             ProductService.objects.filter(lab=current_branch).exclude(id__in=submitted_service_ids).delete()

#             service_names = request.POST.getlist("name")
#             service_descs = request.POST.getlist("service_description")            
#             for name, desc in zip(service_names, service_descs):
#                 if name and name.strip():
#                     ProductService.objects.create(
#                         lab=current_branch,
#                         name=name.strip(),
#                         summary=desc.strip() if desc else "",
#                         is_active=True
#                     )

#             # ── 7. Accreditations ─────────────────────────────────────────────
#             submitted_accred_ids = request.POST.getlist("existing_accred_id[]")
#             # Delete accreditations whose IDs were removed from the DOM
#             Accreditation.objects.filter(lab=current_branch).exclude(id__in=submitted_accred_ids).delete()

#             accred_ids = request.POST.getlist("existing_accred_id[]")
#             accred_bodies = request.POST.getlist("accreditation_body")
#             cert_nos = request.POST.getlist("certificate_no")
#             validity_dates = request.POST.getlist("validity_date")

#             # Zip lists together to process each row accordingly
#             for accred_id, body, cert_no, validity in zip(accred_ids, accred_bodies, cert_nos, validity_dates):
#                 if body.strip() or cert_no.strip():
#                     if accred_id:
#                         # Update existing accreditation record to avoid duplicates
#                         Accreditation.objects.filter(id=accred_id, lab=current_branch).update(
#                             name=body,
#                             certificate_no=cert_no or None,
#                             validity_to=validity if validity else None,
#                             active=True
#                         )
#                     else:
#                         # Create brand new accreditation if no ID exists (e.g. newly added row)
#                         Accreditation.objects.create(
#                             lab=current_branch,
#                             name=body,
#                             certificate_no=cert_no or None,
#                             validity_to=validity if validity else None,
#                             active=True
#                         )

#             # ── Facility Photos ────────────────────────────────────────────
#             submitted_photo_ids = request.POST.getlist("existing_photo_id[]")
            
#             # Fetch photos to be deleted from DB (calling .delete() triggers our model delete method which clears storage)
#             photos_to_delete = BranchImage.objects.filter(lab=current_branch).exclude(id__in=submitted_photo_ids)
#             for photo in photos_to_delete:
#                 photo.delete() # Triggers the custom delete method above to remove file from disk

#             # Save newly uploaded facility photos
#             facility_files = request.FILES.getlist("facility_photos")
#             if facility_files:
#                 for f in facility_files:
#                     BranchImage.objects.create(lab=current_branch, image=f)
                         
#             # ── 8. Final Approval Status Update ───────────────────────────────
#             current_branch.status = "approved"
#             current_branch.save()

#             if request.headers.get("x-requested-with") == "XMLHttpRequest":
#                 return JsonResponse({"status": "success", "message": "Profile submitted successfully!"})
            
#             return redirect("lab-review-detail") # Change to your dashboard or success URL name

#         except Exception as e:
#             if request.headers.get("x-requested-with") == "XMLHttpRequest":
#                 return JsonResponse({"status": "error", "message": str(e)}, status=400)
#             raise e


class GetDepartmentsByDisciplineView(View):
    """
    Returns departments dynamically based on selected Discipline(s) for tag UI.
    """
    def get(self, request, *args, **kwargs):
        discipline_ids = request.GET.getlist("discipline_ids[]") or request.GET.getlist("discipline_ids")
        if not discipline_ids:
            # Agar koi discipline select nahi hai, toh saare departments dikha do ya blank
            departments = Department.objects.filter(is_active=True).order_by("order", "name").values("id", "name")
        else:
            departments = Department.objects.filter(discipline_id__in=discipline_ids, is_active=True).order_by("order", "name").values("id", "name").distinct()

        return JsonResponse({
            "status": "success",
            "departments": list(departments)
        })


@csrf_protect
@require_POST
def update_branch_coordinates(request, lab_id):
    branch = get_object_or_404(Branch, pk=lab_id)
    lat = request.POST.get("latitude")
    lng = request.POST.get("longitude")

    if lat and lng:
        branch.latitude = float(lat)
        branch.longitude = float(lng)
        branch.save(update_fields=["latitude", "longitude"])
        return JsonResponse({"success": True})

    return JsonResponse(
        {"success": False, "message": "Invalid coordinates provided."},
        status=400,
    )


def geocode_branch_with_osm(branch):
    """Geocodes a branch address using Nominatim structured search parameters
    with fallback degradation for complex industrial addresses.
    """
    if branch.latitude and branch.longitude:
        return branch.latitude, branch.longitude

    street = (branch.lab_address or "").strip()
    city = (branch.lab_city or "").strip()
    state = branch.lab_state.name.strip() if branch.lab_state else ""
    country = branch.lab_country.name.strip() if branch.lab_country else "India"

    if not any([street, city, state]):
        return None, None

    url = "https://nominatim.openstreetmap.org/search"
    headers = {
        "User-Agent": "LabFinder360/1.0 (contact@labfinder360.com)"  # Required by OSM TOS
    }

    # Clean plot numbers/suite codes (e.g. "AO-150") for better OSM matching
    cleaned_street = re.sub(
        r"^[A-Za-z0-9/-]+\s+", "", street
    )  # Removes "AO-150 "

    # Define query fallbacks from most specific to broader areas
    query_attempts = [
        # 1. Structured Query with full street
        {"street": street, "city": city, "state": state, "country": country},
        # 2. Structured Query with cleaned street (without plot/suite numbers)
        {
            "street": cleaned_street,
            "city": city,
            "state": state,
            "country": country,
        },
        # 3. Freeform query without house/plot numbers
        {
            "q": f"{cleaned_street}, {city}, {state}, {country}",
            "format": "json",
            "limit": 1,
        },
        # 4. Fallback to City + State
        {
            "q": f"{city}, {state}, {country}",
            "format": "json",
            "limit": 1,
        },
    ]

    for params in query_attempts:
        # Standardize params
        params.setdefault("format", "json")
        params.setdefault("limit", 1)

        try:
            response = requests.get(
                url, headers=headers, params=params, timeout=5
            )
            if response.status_code == 200:
                results = response.json()
                if results:
                    data = results[0]
                    branch.latitude = Decimal(str(data["lat"]))
                    branch.longitude = Decimal(str(data["lon"]))
                    branch.save(update_fields=["latitude", "longitude"])
                    logger.info(
                        f"Geocoded successfully using params {params}: {branch.latitude}, {branch.longitude}"
                    )
                    return branch.latitude, branch.longitude
        except Exception as e:
            logger.error(f"OSM geocode error with params {params}: {e}")

    return None, None

@method_decorator(never_cache, name='dispatch')
class LabReviewDetailView(View):
    """
    Class-based view for displaying lab review details after profile is claimed.
    """
    def get(self, request, *args, **kwargs):
        user = request.user if request.user.is_authenticated else None
        email = user.email if user else None
        if not user:
            email = request.session.get("registration_email")
            if not email or not request.session.get("email_verified"):
                return redirect("register")

        email = email.strip().lower()
        branches = Branch.objects.filter(contact_email__iexact=email)
        current_branch = branches.first()

        # Automatically resolve and save missing OpenStreetMap Lat/Long
        if not current_branch.latitude or not current_branch.longitude:
            geocode_branch_with_osm(current_branch)

        social_media_links = LabSocialLink.objects.filter(lab=current_branch, is_active=True)
        # ── 1. Accreditation data for the lab ─────────────────────────────────
        accreditation = (
            Accreditation.objects
            .filter(lab=current_branch, active=True)
            .select_related("accred")
            .order_by("id")
        )

        # ── 3. Lab photos (all image / base64 fields from Branch) ─────────────
        lab_photos = {
            "lab_logo": current_branch.lab_logo if current_branch else None,
            "logo_base64": current_branch.logo_base64 if current_branch else None,
            "lab_footer_logo": current_branch.lab_footer_logo if current_branch else None,
            "logo_footer_base64": current_branch.logo_footer_base64 if current_branch else None,
            "nabl_logo": current_branch.nabl_logo if current_branch else None,
            "nabl_logo_calibration": current_branch.nabl_logo_calibration if current_branch else None,
            "cover_picture": current_branch.cover_picture if current_branch else None,
            "cover_base64": current_branch.cover_base64 if current_branch else None,
        }

        # ── 2. Testing scopes with nested facilities ───────────────────────────
        scopes_with_facilities = (
            BranchItem.objects
            .filter(lab=current_branch, is_deleted=False, is_disable=False)
            .select_related("service_category", "unit", "gst")
            .prefetch_related(
                "facility_scope",                       # TestingScopeFacility reverse FK
                "facility_scope__test_type",            # Department FK on each facility
                "facility_scope__range_value",          # FacilityRangeValue M2M
                "facility_scope__range_values",         # ParameterRangeValue M2M
                "facility_scope__qualitative_values",   # ParameterQualitativeValue M2M
                "facility_scope__certificate",          # Accreditation M2M on facility
                "certificate",                          # Accreditation M2M on scope
                "test_type",                            # Department M2M on scope
                "category",                             # Category M2M on scope
            )
            .order_by("sort_order", "is_number")
        )

        # Collect unique departments present in the fetched scopes for filter tabs
        scope_departments = []
        seen_dept_ids = set()
        for scope in scopes_with_facilities:
            for dept in scope.test_type.all():
                if dept.id not in seen_dept_ids:
                    seen_dept_ids.add(dept.id)
                    scope_departments.append(dept)

        # testing_packages_with_products = (
        #     TestingPackage.objects.filter(lab=current_branch, is_active=True)
        # ).select_related("lab").prefetch_related("products").order_by("name")
        testing_packages_with_products = TestingPackage.objects.filter(lab=current_branch, is_active=True).order_by("name")

        ALL_SOCIAL_PLATFORMS = [
            "youtube",
            "facebook",
            "instagram",
            "linkedin",
            "twitter",
        ]

        social_media_links = list(social_media_links)

        # existing_platforms = {
        #     social.platform.lower()
        #     for social in social_media_links
        # }

        # missing_platforms = [
        #     platform
        #     for platform in ALL_SOCIAL_PLATFORMS
        #     if platform not in existing_platforms
        # ]

        # ── Test Disciplines Display Logic (Minimum 4 visible) ────────────────
        all_disciplines = list(Discipline.objects.filter(is_active=True).order_by('order'))
        selected_disciplines = list(current_branch.disciplines.all())
        unselected_disciplines = [d for d in all_disciplines if d not in selected_disciplines]

        # Combine selected first, then pad with unselected until there are at least 4
        display_disciplines = list(selected_disciplines)
        if len(display_disciplines) < 4:
            needed = 4 - len(display_disciplines)
            display_disciplines.extend(unselected_disciplines[:needed])

        # ── Testing Types / Departments Display Logic (Minimum 4 visible) ─────
        all_departments = list(Department.objects.filter(is_active=True).order_by('order'))
        selected_departments = list(current_branch.departments.all())
        unselected_departments = [d for d in all_departments if d not in selected_departments]
        
        display_departments = list(selected_departments)
        if len(display_departments) < 4:
            needed = 4 - len(display_departments)
            display_departments.extend(unselected_departments[:needed])

        # ── Categories Display Logic (Minimum 4 visible) ─────────────────────
        all_categories = list(Category.objects.filter(active=True).order_by('order', 'name'))
        selected_categories = list(current_branch.categories.all())
        unselected_categories = [c for c in all_categories if c not in selected_categories]

        display_categories = list(selected_categories)
        if len(display_categories) < 4:
            needed = 4 - len(display_categories)
            display_categories.extend(unselected_categories[:needed])

        # ── Subcategories Display Logic (Minimum 4 visible) ──────────────────
        all_subcategories = list(SubCategory.objects.filter(active=True).order_by('order', 'name'))
        if not selected_categories:
            display_subcategories = []
        else:
            selected_subcategories = list(current_branch.subcategories.filter(category__in=selected_categories))
            matching_subcategories = [s for s in all_subcategories if s.category_id in [c.id for c in selected_categories]]
            unselected_subcategories = [s for s in matching_subcategories if s not in selected_subcategories]

            display_subcategories = list(selected_subcategories)
            if len(display_subcategories) < 4:
                needed = 4 - len(display_subcategories)
                display_subcategories.extend(unselected_subcategories[:needed])

        ############# Lab category wise fields ################
        category_fields = []
        if current_branch.lab_category and current_branch.lab_category.dynamic_schema:
            category_fields = current_branch.lab_category.dynamic_schema.get("fields", [])



        return render(
            request,
            "accounts/review-details.html",
            {
                "email": email,
                "branch": current_branch,
                "branches": branches,
                "category_fields": category_fields,
                "category_data": current_branch.category_data or {},
                "All_social_platforms": ALL_SOCIAL_PLATFORMS,
                "social_media_links": social_media_links,
                # "missing_platforms": missing_platforms,
                "accreditation": accreditation,
                "lab_photos": lab_photos,
                "all_disciplines": all_disciplines,
                "all_departments": all_departments,
                "display_disciplines": display_disciplines,
                "display_departments": display_departments,
                "all_categories": all_categories,
                "all_subcategories": all_subcategories,
                "display_categories": display_categories,
                "display_subcategories": display_subcategories,
                "scopes_with_facilities": scopes_with_facilities,
                "testing_packages_with_products": testing_packages_with_products,
                "scope_departments": scope_departments,
                "countries" : Country.objects.all(),
                "states": State.objects.all(),
                "lab_categories": LabCategory.objects.filter(is_active=True)
            }
        )

    def post(self, request, *args, **kwargs):
        user = request.user if request.user.is_authenticated else None        
        if not user:
            email = request.session.get("registration_email")
            if not email or not request.session.get("email_verified"):
                return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

        current_branch = get_current_branch(request)
        if not current_branch:
            return JsonResponse({"status": "error", "message": "Branch not found"}, status=404)

        try:
            action = request.POST.get("action", "save_general")

            # ── 1. General Info / Identity Auto-Save ──────────────────────────
            if action == "save_general":
                current_branch.lab_name = request.POST.get("legal_lab_name", current_branch.lab_name)
                current_branch.contact_mobile = request.POST.get("phone_number", current_branch.contact_mobile)
                current_branch.contact_email = request.POST.get("contact_email", current_branch.contact_email)
                current_branch.lab_address = request.POST.get("facility_address", current_branch.lab_address)
                current_branch.lab_pincode = request.POST.get("facility_postal_code", current_branch.lab_pincode)
                current_branch.establishment_year = request.POST.get("establishment_year", current_branch.establishment_year)

                country_id = request.POST.get("facility_country")
                current_branch.lab_country = Country.objects.filter(id=country_id).first() if country_id else None

                state_id = request.POST.get("facility_state")
                current_branch.lab_state = State.objects.filter(id=state_id).first() if state_id else None

                exec_summary = request.POST.get("executive_summary")
                if exec_summary is not None:
                    current_branch.description = exec_summary

                if "lab_logo" in request.FILES:
                    current_branch.lab_logo = request.FILES["lab_logo"]

                # ── Handle Lab Category & Dynamic Schema Setup ─────────────────
                cat_id = request.POST.get("facility_lab_category")
                fields = []
                if cat_id:
                    category = LabCategory.objects.filter(id=int(cat_id)).first()
                    if category:
                        category_changed = current_branch.lab_category and str(current_branch.lab_category.id) != str(cat_id)
                        current_branch.lab_category = category

                        if category.dynamic_schema:
                            fields = category.dynamic_schema.get("fields", [])

                        # Case 1 & Case 2: Reset category_data if category changed or if category_data is empty
                        if category_changed or not current_branch.category_data:
                            new_category_data = {}
                            for field in fields:
                                key = field.get("key")
                                if key:
                                    if field.get("type") == "boolean":
                                        new_category_data[key] = False
                                    else:
                                        new_category_data[key] = ""
                            current_branch.category_data = new_category_data

                current_branch.save()
                return JsonResponse({
                    "status": "success",
                    "category_id": str(current_branch.lab_category.id) if current_branch.lab_category else "",
                    "category_name": current_branch.lab_category.name if current_branch.lab_category else "",
                    "fields": fields,
                    "category_data": current_branch.category_data or {},
                    "message": "Saved successfully"
                })

            # ── 1b. Live Dynamic Category Field Updates ────────────────────────
            elif action == "save_category_data":
                if current_branch.category_data is None:
                    current_branch.category_data = {}

                cat_data = dict(current_branch.category_data)
                for key, value in request.POST.items():
                    if key.startswith("category_data[") and key.endswith("]"):
                        clean_key = key[14:-1]
                        if value.lower() == "true":
                            cat_data[clean_key] = True
                        elif value.lower() == "false":
                            cat_data[clean_key] = False
                        else:
                            cat_data[clean_key] = value

                current_branch.category_data = cat_data
                current_branch.save()

                return JsonResponse({
                    "status": "success",
                    "category_data": current_branch.category_data,
                    "message": "Category data saved successfully"
                })
            
            # # ── 2. Disciplines Auto-Save ──────────────────────────────────────
            elif action == "save_disciplines":
                discipline_names = request.POST.getlist("disciplines[]") or request.POST.getlist("disciplines")
                disciplines = Discipline.objects.filter(name__in=discipline_names)
                current_branch.disciplines.set(disciplines)
                return JsonResponse({"status": "success", "message": "Disciplines saved successfully."})

            # # ── 3. Testing Types / Departments Auto-Save ──────────────────────
            elif action == "save_departments":
                department_names = request.POST.getlist("departments[]") or request.POST.getlist("departments")
                departments = Department.objects.filter(name__in=department_names).distinct()
                current_branch.departments.set(departments)
                return JsonResponse({"status": "success", "message": "Departments saved successfully."})

            # ── 3b. Categories Auto-Save ─────────────────────────────────────
            elif action == "save_categories":
                category_names = request.POST.getlist("categories[]") or request.POST.getlist("categories")
                categories = Category.objects.filter(name__in=category_names)
                current_branch.categories.set(categories)
                # Subcategory will be according to category:
                # Remove subcategories that no longer belong to selected categories
                valid_subcategories = SubCategory.objects.filter(category__in=categories)
                current_branch.subcategories.set(
                    current_branch.subcategories.filter(pk__in=valid_subcategories.values("pk"))
                )
                return JsonResponse({"status": "success", "message": "Categories saved successfully."})

            # ── 3c. Subcategories Auto-Save ──────────────────────────────────
            elif action == "save_subcategories":
                category_ids = current_branch.categories.values_list("pk", flat=True)
                subcategory_names = request.POST.getlist("subcategories[]") or request.POST.getlist("subcategories")
                subcategories = SubCategory.objects.filter(name__in=subcategory_names, category_id__in=category_ids).distinct()
                current_branch.subcategories.set(subcategories)
                return JsonResponse({"status": "success", "message": "Subcategories saved successfully."})

            # ── 4. Social Media Links Auto-Save ──────────────────────────────────
            elif action == "save_socials":
                platforms = request.POST.getlist("social_platform")
                urls = request.POST.getlist("social_url")
                LabSocialLink.objects.filter(lab=current_branch).delete()
                for platform, url in zip(platforms, urls):
                    if platform and url.strip() and url.strip() != "https://":
                        LabSocialLink.objects.create(
                            lab=current_branch,
                            platform=platform.strip().lower(),
                            url=url.strip(),
                            is_active=True
                        )
                return JsonResponse({"status": "success", "message": "Social links updated"})

            # ── 5. Product Services (Add / Update / Delete) ───────────────────
            elif action == "save_services":
                service_id = request.POST.get("service_id")
                name = request.POST.get("name", "").strip()
                summary = request.POST.get("service_description", "").strip()

                if service_id:
                    service = ProductService.objects.filter(id=service_id, lab=current_branch).first()
                    if service:
                        if name:
                            service.name = name
                            service.summary = summary
                            service.save()
                        else:
                            service.delete()
                elif name:
                    new_service = ProductService.objects.create(lab=current_branch, name=name, summary=summary, is_active=True)
                    return JsonResponse({"status": "success", "service_id": str(new_service.id)})

                return JsonResponse({"status": "success"})

            elif action == "delete_service":
                service_id = request.POST.get("service_id")
                ProductService.objects.filter(id=service_id, lab=current_branch).delete()
                return JsonResponse({"status": "success"})

            # ── 6. Accreditations (Add / Update / Delete) ─────────────────────
            elif action == "save_accreditation":
                accred_id = request.POST.get("accred_id")
                body = request.POST.get("accreditation_body", "").strip()
                cert_no = request.POST.get("certificate_no", "").strip()
                validity = request.POST.get("validity_date")
                logo_file = request.FILES.get("accreditation_logo")
                cert_file = request.FILES.get("certificate_img")  # If uploading certificate image as well

                # Get existing instance or instantiate a new one
                if accred_id:
                    try:
                        accred_obj = Accreditation.objects.get(id=accred_id, lab=current_branch)
                    except Accreditation.DoesNotExist:
                        return JsonResponse({"status": "error", "message": "Record not found"}, status=404)
                else:
                    accred_obj = Accreditation(lab=current_branch)

                # Assign fields
                accred_obj.name = body
                accred_obj.certificate_no = cert_no or None
                accred_obj.validity_to = validity if validity else None
                accred_obj.active = True

                # Assign image files if uploaded
                if logo_file:
                    accred_obj.logo = logo_file
                if cert_file:
                    accred_obj.certificate_img = cert_file

                # .save() triggers file handling & calls get_accreditation_logo_path()
                accred_obj.save()
                return JsonResponse({"status": "success", "accred_id": str(accred_obj.id)})
            elif action == "delete_accreditation":
                accred_id = request.POST.get("accred_id")
                Accreditation.objects.filter(id=accred_id, lab=current_branch).delete()
                return JsonResponse({"status": "success"})

            # ── 7. Facility Photos (Upload / Delete) ──────────────────────────
            elif action == "upload_photo":
                facility_files = request.FILES.getlist("facility_photos")
                created_photos = []
                for f in facility_files:
                    p = BranchImage.objects.create(lab=current_branch, image=f)
                    created_photos.append({"id": str(p.id), "url": p.image.url})
                return JsonResponse({"status": "success", "photos": created_photos})

            elif action == "delete_photo":
                photo_id = request.POST.get("photo_id")
                photo = BranchImage.objects.filter(id=photo_id, lab=current_branch).first()
                if photo:
                    photo.delete() # Triggers model delete method for physical file cleanup
                return JsonResponse({"status": "success"})

            # ── 8. Delete Product Scope / BranchItem (Hard Delete) ────────────
            elif action == "delete_scope":
                scope_id = request.POST.get("scope_id")
                if scope_id:
                    branch_item = BranchItem.objects.filter(id=scope_id, lab=current_branch).first()
                    if branch_item:
                        branch_item.facility_scope.all().delete()
                        branch_item.delete()                        
                return JsonResponse({"status": "success", "message": "Product scope and parameters permanently deleted."})({"status": "success", "message": "Product scope and parameters deleted successfully."})

            # ── 9. Delete Package (Hard Delete) ────────────
            elif action == "delete_package":
                package_id = request.POST.get("package_id")
                if package_id:
                    package = get_object_or_404(TestingPackage, id=package_id, lab=current_branch)
                    package.delete()
                return JsonResponse({"status": "success", "message": "Package deleted successfully."})  
                       
            # ── Final Approval Submission Action ──────────────────────────────
            elif action == "submit_for_approval":
                current_branch.status = "reviewed" # or "pending approval" depending on your choices
                current_branch.save()
                return JsonResponse({
                    "status": "success", 
                    "message": "Your profile has been successfully submitted for approval!"
                })
            
            return JsonResponse({"status": "error", "message": "Invalid action"}, status=400)

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)


class SaveProductScopeView(View):
    """
    Saves product/scope details from Step 1 into BranchItem model,
    and parameter rows / uploaded Excel files from Step 2 into TestingScopeFacility for that BranchItem.
    """
    def post(self, request, *args, **kwargs):
        current_branch = get_current_branch(request)
        if not current_branch:
            return JsonResponse({"status": "error", "message": "Unauthorized"}, status=403)

        product_name = request.POST.get("product_name", "").strip()
        scope_notes = request.POST.get("scope_notes", "").strip()
        scope_id = request.POST.get("scope_id", "").strip()
        testing_types = request.POST.getlist("testing_types[]") or request.POST.getlist("testing_types")

        param_names = request.POST.getlist("param_name[]")
        param_methods = request.POST.getlist("param_method[]")
        param_units = request.POST.getlist("param_unit[]")

        excel_rows = []
        if "excel_file" in request.FILES:
            try:
                excel_rows = parse_excel_or_csv(request.FILES["excel_file"])
            except Exception as e:
                return JsonResponse({"status": "error", "message": f"Failed to parse Excel file: {str(e)}"}, status=400)

        parameters_to_create = []
        # Add form-submitted parameter rows
        for name, method, unit in zip(param_names, param_methods, param_units):
            if name and name.strip():
                parameters_to_create.append({
                    "name": name.strip(),
                    "method": method.strip() if method else "",
                    "unit": unit.strip() if unit else "",
                })

        # Add Excel-parsed parameter rows
        for r in excel_rows:
            p_name = r.get("name") or r.get("parameter_name") or ""
            p_method = r.get("method") or r.get("test_method") or ""
            p_unit = r.get("unit") or ""
            if p_name.strip():
                parameters_to_create.append({
                    "name": p_name.strip(),
                    "method": p_method.strip(),
                    "unit": p_unit.strip()
                })

        # Validation: If creating a new scope, product name is required
        if not scope_id and not product_name:
            return JsonResponse({"status": "error", "message": "Product / Material name is required."}, status=400)

        try:
            with transaction.atomic():
                branch_item = None
                created_scope = False
                if scope_id:
                    branch_item = BranchItem.objects.filter(id=scope_id, lab=current_branch).first()

                if not branch_item:
                    # Create new BranchItem scope
                    branch_item = BranchItem.objects.create(
                        lab=current_branch,
                        is_number=product_name[:550],
                        is_title=product_name,
                        description=scope_notes if scope_notes else None,
                        form_type="lims",
                        is_standard=True,
                        is_public=True,
                    )
                    created_scope = True
                else:
                    # Update existing BranchItem scope
                    if product_name:
                        branch_item.is_title = product_name
                        branch_item.is_number = product_name[:550]
                    if scope_notes:
                        branch_item.description = scope_notes
                    branch_item.save()
                    # Clear existing parameters to prevent duplicates upon updating
                    branch_item.facility_scope.all().delete()

                # Save Testing Types / Departments
                if testing_types:
                    for type_name in testing_types:
                        clean_type = type_name.strip()
                        if clean_type:
                            dept, _ = Department.objects.get_or_create(
                                name__iexact=clean_type,
                                defaults={"name": clean_type}
                            )
                            branch_item.test_type.add(dept)

                # Save TestingScopeFacility parameters
                for p in parameters_to_create:
                    p_name = p.get("name", "").strip()
                    if not p_name:
                        continue
                    p_method = p.get("method", "").strip()
                    p_unit = p.get("unit", "").strip()

                    facility = TestingScopeFacility.objects.create(
                        scope=branch_item,
                        lab=current_branch,
                        clause_no=p_name[:255],
                        parameter=p_name,
                        title=p_name,
                        quantity=1,
                        charges=1.0,
                        is_active=True,
                    )

                    if p_method:
                        method_obj, _ = TestMethod.objects.get_or_create(
                            lab=current_branch,
                            name=p_method[:500]
                        )
                        facility.method_test.add(method_obj)

                    if p_unit:
                        unit_obj, _ = Unit.objects.get_or_create(name=p_unit[:200])
                        facility.range_unit = unit_obj
                        facility.save(update_fields=["range_unit"])

                total_param_count = branch_item.facility_scope.count()
                departments_data = [
                    {"name": d.name, "slug": slugify(d.name)}
                    for d in branch_item.test_type.all()
                ]

                # Format parameters array for real-time frontend update
                saved_parameters = [
                    {
                        "name": f.parameter,
                        "method": " ".join([m.name for m in f.method_test.all()]),
                        "unit": f.range_unit.name if f.range_unit else ""
                    }
                    for f in branch_item.facility_scope.all()
                ]

                return JsonResponse({
                    "status": "success",
                    "message": "Saved successfully!",
                    "created": created_scope,
                    "scope": {
                        "id": str(branch_item.id),
                        "is_number": branch_item.is_number,
                        "is_title": branch_item.is_title,
                        "description": branch_item.description or "",
                        "param_count": total_param_count,
                        "departments": departments_data,
                        "parameters": saved_parameters
                    }
                })
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)


class SaveTestingPackageView(View):
    """
    Class-based view to create or update TestingPackage using Smart Sync (Diffing).
    """
    def post(self, request, *args, **kwargs):
        current_branch = get_current_branch(request)
        if not current_branch:
            return JsonResponse({"status": "error", "message": "Unauthorized"}, status=403)

        package_id = request.POST.get("package_id", "").strip()
        package_name = request.POST.get("package_name", "").strip()
        package_price = request.POST.get("package_price") or 0.00
        package_discount = request.POST.get("package_discount") or 0.00
        description = request.POST.get("description", "").strip()

        incoming_product_ids = request.POST.getlist("product_ids[]") or request.POST.getlist("product_ids")
        incoming_product_ids = set(str(pid) for pid in incoming_product_ids)

        if not package_name:
            return JsonResponse({"status": "error", "message": "Package name is required."}, status=400)

        try:
            with transaction.atomic():
                if package_id:
                    package = get_object_or_404(TestingPackage, id=package_id, lab=current_branch)
                    package.name = package_name
                    package.price = package_price
                    package.discount = package_discount
                    package.description = description
                    package.save()
                else:
                    package = TestingPackage.objects.create(
                        lab=current_branch,
                        name=package_name,
                        price=package_price,
                        discount=package_discount,
                        description=description,
                        is_active=True
                    )

                # Smart Sync for Package Items (Through Model)
                existing_items = TestingPackageItem.objects.filter(package=package)
                existing_product_ids = set(str(item.product.id) for item in existing_items)

                # A. Remove unselected products
                products_to_remove = existing_product_ids - incoming_product_ids
                if products_to_remove:
                    TestingPackageItem.objects.filter(
                        package=package, product_id__in=products_to_remove
                    ).delete()

                # B. Add newly selected products
                products_to_add = incoming_product_ids - existing_product_ids
                for p_id in products_to_add:
                    product_item = get_object_or_404(BranchItem, id=p_id, lab=current_branch)
                    TestingPackageItem.objects.create(package=package, product=product_item)

                saved_products = [
                    {"id": str(prod.id), "name": prod.name}
                    for prod in package.products.all()
                ]

                return JsonResponse({
                    "status": "success",
                    "message": "Package saved successfully!",
                    "package": {
                        "id": str(package.id),
                        "name": package.name,
                        "price": str(package.price),
                        "discount": str(package.discount),
                        "product_count": package.products.count(),
                        "products": saved_products
                    }
                })
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)


@method_decorator(never_cache, name='dispatch')
class ParseScopeExcelView(View):
    """
    Parses an uploaded Excel or CSV file and returns the rows as JSON
    to immediately preview in the Step 2 parameters table.
    """
    def post(self, request, *args, **kwargs):
        if "excel_file" not in request.FILES:
            return JsonResponse({"status": "error", "message": "No file uploaded."}, status=400)

        try:
            rows = parse_excel_or_csv(request.FILES["excel_file"])
            return JsonResponse({
                "status": "success",
                "rows": rows,
                "count": len(rows),
            })
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)


@method_decorator(never_cache, name='dispatch')
class ClaimLabs(View):
    """
    Class-based view for displaying matching branches for user email (GET)
    and claiming or unlinking branches (POST).
    """
    def get(self, request, *args, **kwargs):
        email = request.session.get("registration_email")
        if not email or not request.session.get("email_verified"):
            return redirect("register")

        email = email.strip().lower()
        matched_branches = Branch.objects.filter(contact_email__iexact=email)
        if matched_branches.exists():
            if matched_branches.filter(status='claimed').exists():
                '''
                If any of the branch status is claimed then
                go to lab-review-detail with all lab data. list there other unclaimed labs also
                '''
                return redirect("lab-review-detail")
            else:
                '''
                If not claimed then list of matched labs to claim or unlink
                '''
                return render(
                    request,
                    "accounts/claim_labs.html",
                    {
                        "email": email,
                        "branches": matched_branches,
                    }
                )
        else:
            ''' 
            No record found in branch database. 
            Ask lab to enter website url to fetch th details
            '''
            return redirect("lab-website-url")
        

    def post(self, request, *args, **kwargs):
        email = request.session.get("registration_email")
        if not email or not request.session.get("email_verified"):
            if request.content_type == "application/json" or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"success": False, "message": "Session expired."}, status=400)
            return redirect("register")

        email = email.strip().lower()
        # Create or get User for this email
        user, ucreated = User.objects.get_or_create(
            username=email
        )
        user.email=email
                   
        # if ucreated:
        #     user.is_active=False 
        #     user.set_unusable_password()
        if ucreated:
            ''' create a lab user and send password on email with reset password link '''
            user.is_active=True
            lab_group, _ = Group.objects.get_or_create(name="Lab")
            user.groups.add(lab_group)
            # user.set_unusable_password()
            user.set_password("admin@123")
        user.save()

        # Extract post data (JSON or Form POST)
        data = {}
        if request.content_type == "application/json" or request.body:
            try:
                data = json.loads(request.body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                data = request.POST.dict()
        else:
            data = request.POST.dict()

        branches = Branch.objects.filter(contact_email__iexact=email)

        for branch in branches:
            action = data.get(f"action_{branch.id}") or data.get(str(branch.id))

            if action == "claim":
                branch.status = 'claimed'
                if not branch.user and not Branch.objects.filter(user=user).exclude(id=branch.id).exists():
                    branch.user = user
                branch.save()
            elif action == "unlink":
                branch.status = 'unclaimed'
                branch.contact_email = None
                if not branch.user and not Branch.objects.filter(user=user).exclude(id=branch.id).exists():
                    branch.user = user
                branch.save()
            else:
                if not branch.user and not Branch.objects.filter(user=user).exclude(id=branch.id).exists():
                    branch.user = user
                branch.save()

        has_approved = None
        has_claimed = None
        has_approved = Branch.objects.filter(user=user, status='approved').exists() or Branch.objects.filter(contact_email__iexact=email, status='approved').exists()
        has_claimed = Branch.objects.filter(user=user, status='claimed').exists() or Branch.objects.filter(contact_email__iexact=email, status='claimed').exists()
        if has_approved:
            redirect_target = "dashboard"
        elif has_claimed:
            redirect_target = "lab-review-detail"
        else:
            redirect_target = "lab-website-url"

        if request.content_type == "application/json" or request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                "success": True,
                "message": "Branches updated successfully.",
                "redirect_url": reverse(redirect_target)
            })

        return redirect(redirect_target)



# @method_decorator(never_cache, name='dispatch')
# class LabDashboardView(View):
    
#     def get(self, request, *args, **kwargs):
#         email = request.session.get("registration_email")
#         if not email or not request.session.get("email_verified"):
#             return redirect("register")

#         email = email.strip().lower()
#         branches = Branch.objects.filter(contact_email__iexact=email)
#         current_branch = branches.first()
        
#         if not current_branch:
#             return redirect("register")

#         # ── 1. Fetch Leads via Modular Function ──────────────────────────────
#         leads_res = get_leads_dashboard_context(request, current_branch)
#         leads_data = leads_res["context"]
#         leads_tab_html = leads_res["rendered_html"]

#         # ── 2. Existing Dashboard Data ───────────────────────────────────────
#         social_media_links = LabSocialLink.objects.filter(lab=current_branch, is_active=True)

#         accreditation = (
#             Accreditation.objects
#             .filter(lab=current_branch, active=True)
#             .select_related("accred")
#             .order_by("id")
#         )

#         scopes_with_facilities = (
#             BranchItem.objects
#             .filter(lab=current_branch, is_deleted=False, is_disable=False)
#             .select_related("service_category", "unit", "gst")
#             .prefetch_related(
#                 "facility_scope",
#                 "facility_scope__test_type",
#                 "facility_scope__range_value",
#                 "facility_scope__range_values",
#                 "facility_scope__qualitative_values",
#                 "facility_scope__certificate",
#                 "certificate",
#                 "test_type",
#                 "category",
#             )
#             .order_by("sort_order", "is_number")
#         )

#         lab_photos = {
#             "lab_logo": current_branch.lab_logo if current_branch else None,
#             "logo_base64": current_branch.logo_base64 if current_branch else None,
#             "lab_footer_logo": current_branch.lab_footer_logo if current_branch else None,
#             "logo_footer_base64": current_branch.logo_footer_base64 if current_branch else None,
#             "nabl_logo": current_branch.nabl_logo if current_branch else None,
#             "nabl_logo_calibration": current_branch.nabl_logo_calibration if current_branch else None,
#             "cover_picture": current_branch.cover_picture if current_branch else None,
#             "cover_base64": current_branch.cover_base64 if current_branch else None,
#         }

#         team_members = (
#             BranchManpower.objects
#             .filter(lab=current_branch, is_deleted=False)
#             .select_related("user", "group_assigned")
#             .prefetch_related(
#                 "roles",
#                 "roles__group",
#                 "roles__active_department",
#                 "roles__departments",
#             )
#             .order_by("status", "user__first_name")
#         )

#         return render(
#             request,
#             "accounts/dashboard.html",
#             {
#                 "email": email,
#                 "branch": current_branch,
#                 "branches": branches,
#                 "social_media_links": social_media_links,
#                 "accreditation": accreditation,
#                 "scopes_with_facilities": scopes_with_facilities,
#                 "lab_photos": lab_photos,
#                 "team_members": team_members,
#                 "leads_data": leads_data,
#                 "leads_tab_html": leads_tab_html,  # Pre-rendered HTML string option
#             }
#         )



@method_decorator(never_cache, name="dispatch")
class DashboardView(View):
    """
    Unified Dashboard Router:
    - Customer group -> Renders Customer Dashboard
    - Lab group / Verified Branch -> Renders Lab Dashboard
    - Otherwise -> Redirects to Register
    """

    def get(self, request, *args, **kwargs):
        # Ensure user is logged in
        if not request.user.is_authenticated:
            return redirect("register")

        lab_login = False
        user_groups = request.user.groups.values_list('name', flat=True)
        if 'customer' in user_groups or 'Customer' in user_groups:
            return render_customer_dashboard(request)
        elif 'lab' in user_groups or 'Lab' in user_groups or Branch.objects.filter(user=request.user):
            lab_login = True
            email = request.user.email
            current_branch = Branch.objects.get(user=request.user) 

        else:
            # check session
            email = request.session.get("registration_email", "").strip().lower()
            is_verified = request.session.get("email_verified", False)
            current_branch = Branch.objects.filter(contact_email__iexact=email).first() if (email and is_verified) else None

            # Fallback if lab session or branch profile is missing
            if current_branch:
                lab_login = True
            else:
                return redirect("register")

        
        if lab_login:
            leads_res = get_leads_dashboard_context(request, current_branch)
            reviews_res = get_reviews_dashboard_context(request, current_branch)
            try:
                orders_res = get_orders_dashboard_context(request, current_branch)
                orders_ctx = orders_res["context"]
                orders = orders_ctx.get("orders")
            except Exception:
                orders = []
                orders_ctx = {}

            leads_ctx = leads_res["context"]
            reviews_ctx = reviews_res["context"]
            lead_rows = leads_ctx.get("lead_rows") or []
            scope_count = (
                BranchItem.objects.filter(lab=current_branch, is_deleted=False, is_disable=False).count()
            )
            photos = list(current_branch.facility_images.filter(is_active=True)[:8])
            has_basic = bool(current_branch.lab_name and (current_branch.lab_address or current_branch.contact_email))
            has_accred = Accreditation.objects.filter(lab=current_branch, active=True).exists()
            has_photos = bool(photos or current_branch.cover_picture)
            has_tests = scope_count >= 3
            checks = {
                "basic": has_basic,
                "accreditation": has_accred,
                "photos": has_photos,
                "tests": has_tests,
            }
            profile_pct = int(sum(1 for v in checks.values() if v) / 4 * 100)
            counts = leads_ctx.get("counts") or {}
            tab = request.GET.get("tab") or "dashboard"
            if tab not in ("dashboard", "leads", "orders", "scope", "profile", "reviews", "analytics", "settings"):
                tab = "dashboard"

            context = {
                "email": email,
                "branch": current_branch,
                "active_tab": tab,
                "edit_mode": request.GET.get("edit") == "1" and tab == "profile",
                "active_status": leads_ctx.get("active_status", "all"),
                "counts": counts,
                "lead_rows": lead_rows,
                "recent_leads": lead_rows[:5],
                "orders": orders,
                "order_rows": orders_ctx.get("order_rows") or [],
                "order_counts": orders_ctx.get("order_counts") or {},
                "active_order_status": orders_ctx.get("active_order_status", "all"),
                "order_stats": orders_ctx.get("order_stats") or {},
                "reviews": reviews_ctx.get("reviews"),
                "overall_avg": reviews_ctx.get("overall_avg"),
                "total_count": reviews_ctx.get("total_count"),
                "category_averages": reviews_ctx.get("category_averages"),
                "accreditation": (
                    Accreditation.objects.filter(lab=current_branch, active=True)
                    .select_related("accred")
                    .order_by("id")
                ),
                "scopes_with_facilities": (
                    BranchItem.objects.filter(lab=current_branch, is_deleted=False, is_disable=False)
                    .order_by("sort_order", "is_number")[:30]
                ),
                "scope_count": scope_count,
                "facility_images": photos,
                "profile_pct": profile_pct,
                "checks": checks,
                "metrics": {
                    "views": 0,
                    "leads": counts.get("all", 0),
                    "pending": counts.get("new", 0),
                    "appearances": 0,
                },
            }
            return render(request, "accounts/lab_portal.html", context)

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("register")
        branch = Branch.objects.filter(user=request.user).first()
        if not branch:
            return redirect("dashboard")
        if request.POST.get("action") == "update_profile":
            branch.lab_name = request.POST.get("lab_name", branch.lab_name) or branch.lab_name
            branch.contact_mobile = request.POST.get("contact_mobile", "") or branch.contact_mobile
            branch.contact_email = request.POST.get("contact_email", "") or branch.contact_email
            branch.lab_address = request.POST.get("lab_address", "") or branch.lab_address
            branch.lab_city = request.POST.get("lab_city", "") or branch.lab_city
            branch.lab_pincode = request.POST.get("lab_pincode", "") or branch.lab_pincode
            branch.description = request.POST.get("description", branch.description)
            photo = request.FILES.get("facility_photo")
            if photo:
                from apps.labs.models import BranchImage
                BranchImage.objects.create(lab=branch, image=photo, is_active=True)
            branch.save()
            messages.success(request, "Profile updated.")
            return redirect(f"{reverse('dashboard')}?tab=profile")
        return redirect("dashboard")


# Backward compatibility aliases
send_otp_view = RegisterView.as_view()
register = RegisterView.as_view()
verify_email = VerifyEmailView.as_view()
lab_website_detail = LabWebsiteURLView.as_view()
