from datetime import timedelta
import uuid
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.db.models import Avg, Prefetch, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.decorators.http import require_http_methods

from apps.labs.models import Branch, BranchItem
from apps.utility.views import get_linkedin_profile

try:
    from config.settings_local import MOCK_LINKEDIN_LOGIN
except Exception:
    MOCK_LINKEDIN_LOGIN = False

from .forms import (
    AcceptQuotationForm,
    DisputeForm,
    EnquiryDiscussionForm,
    EnquiryForm,
    GuestEnquiryForm,
    LabReviewForm,
    LeadStatusForm,
    OrderDocumentForm,
    OrderInvoiceForm,
    OrderMessageForm,
    QuotationForm,
    RejectQuotationForm,
)
from .models import (
    Dispute,
    Enquiry,
    EnquiryDiscussion,
    LabLead,
    LabReview,
    LabReviewCategoryRating,
    LIMSJobOrder,
    OrderDocument,
    OrderMessage,
    Quotation,
    ReviewCategory,
)

User = get_user_model()


def _branch_for_user(user):
    if not user or not user.is_authenticated:
        return None
    return getattr(user, "lab_user", None)


def _resolve_sender_type(user, lab_lead: LabLead) -> str:
    if lab_lead.is_lab_staff(user):
        return "lab"
    return "customer"


def _lead_detail_url(enquiry, lab_lead, subtab=None):
    url = reverse("lead_detail", kwargs={"enquiry_id": enquiry.pk})
    params = []
    if lab_lead and enquiry.quotation_type == "multiple_labs":
        params.append(f"lab={lab_lead.lab_id}")
    if subtab:
        params.append(f"subtab={subtab}")
    if params:
        url = f"{url}?{'&'.join(params)}"
    return url


# @require_http_methods(["GET", "POST"])
# def enquiry_now(request):
#     if request.method == "GET":
#         storage = get_messages(request)
#         for _ in storage:
#             pass  # Iterating consumes and clears all unread messages

#     lab_id = request.GET.get("lab_id") or request.POST.get("lab_id")
#     lab = None
#     if lab_id:
#         try:
#             lab = Branch.objects.select_related("lab_category").filter(pk=lab_id).first()
#         except (ValueError, TypeError):
#             lab = None

#     # Pre-selected service / scope from lab details page
#     selected_service = None
#     service_id = request.GET.get("service_id") or request.POST.get("service_id") or request.GET.get("scope_id")
#     service_name = (request.GET.get("service") or request.POST.get("service") or "").strip()
#     service_title = (request.GET.get("service_title") or request.POST.get("service_title") or "").strip()
#     if service_id and lab:
#         try:
#             selected_service = (
#                 BranchItem.objects.filter(pk=service_id, lab=lab, is_disable=False)
#                 .select_related("service_category")
#                 .first()
#             )
#         except (ValueError, TypeError):
#             selected_service = None
#     if selected_service and not service_name:
#         service_name = (
#             selected_service.is_number
#             or (selected_service.service_category.name if selected_service.service_category_id else "")
#             or selected_service.is_title
#             or ""
#         )
#         if not service_title:
#             service_title = selected_service.is_title or selected_service.description or ""

#     linkedin_profile = {}
#     if request.user.is_authenticated:
#         linkedin_profile = get_linkedin_profile(request.user) or {}

#     if request.method == "POST":
#         form = (
#             EnquiryForm(request.POST)
#             if request.user.is_authenticated
#             else GuestEnquiryForm(request.POST)
#         )

#         if form.is_valid():
#             enquiry = form.save(commit=False)
#             enquiry.lab = lab
#             if lab and lab.lab_category_id:
#                 enquiry.lab_category = lab.lab_category

#             quotation_type = request.POST.get("quotation_type")
#             if quotation_type not in ("selected_lab", "multiple_labs"):
#                 quotation_type = "selected_lab" if lab else "multiple_labs"
#             enquiry.quotation_type = quotation_type

#             if not enquiry.budget:
#                 enquiry.budget = request.POST.get("budget", "") or ""

#             otp_code = request.POST.get("otp_code")
#             posted_email = (
#                 request.POST.get("email")
#                 or form.cleaned_data.get("email")
#                 or ""
#             )
#             posted_mobile = (
#                 request.POST.get("mobile_number")
#                 or form.cleaned_data.get("mobile_number")
#                 or ""
#             )
#             posted_contact_name = (
#                 request.POST.get("contact_name")
#                 or form.cleaned_data.get("contact_name")
#                 or ""
#             ).strip()

#             if not request.user.is_authenticated and otp_code and posted_email:
#                 is_otp_valid = True  # TODO: real OTP verification
#                 if is_otp_valid:
#                     name_parts = posted_contact_name.split(" ", 1)
#                     first_name = name_parts[0] if name_parts else ""
#                     last_name = name_parts[1] if len(name_parts) > 1 else ""

#                     user, created = User.objects.get_or_create(
#                         email=posted_email,
#                         defaults={
#                             "username": posted_email,
#                             "first_name": first_name,
#                             "last_name": last_name,
#                         },
#                     )
#                     if not created:
#                         if first_name:
#                             user.first_name = first_name
#                         if last_name:
#                             user.last_name = last_name
#                         user.save()

#                     customer_group, _ = Group.objects.get_or_create(name="Customer")
#                     user.groups.add(customer_group)
#                     login(
#                         request,
#                         user,
#                         backend="django.contrib.auth.backends.ModelBackend",
#                     )

#             if request.user.is_authenticated:
#                 enquiry.user = request.user
#                 enquiry.email = (
#                     linkedin_profile.get("email")
#                     or request.user.email
#                     or posted_email
#                     or ""
#                 )
#                 enquiry.contact_name = (
#                     posted_contact_name
#                     or linkedin_profile.get("name")
#                     or request.user.get_full_name()
#                     or request.user.get_username()
#                 )
#                 enquiry.mobile_number = posted_mobile or enquiry.mobile_number or ""
#             else:
#                 enquiry.user = None
#                 enquiry.email = posted_email
#                 enquiry.mobile_number = posted_mobile
#                 enquiry.contact_name = posted_contact_name

#             if request.FILES.get("media"):
#                 enquiry.media = request.FILES["media"]
#             if not enquiry.preferred_services:
#                 enquiry.preferred_services = (
#                     request.POST.get("preferred_services") or service_name or ""
#                 )[:255]
#             enquiry.save()

#             # selected_lab → create LabLead immediately
#             if enquiry.quotation_type == "selected_lab" and lab:
#                 enquiry.ensure_lab_lead(lab)

#             if not request.user.is_authenticated:
#                 request.session["guest_enquiry_confirmation"] = str(enquiry.pk)

#             messages.success(request, "Your enquiry has been successfully submitted.")
#             return redirect("enquiry_success", enquiry_id=enquiry.pk)
#     else:
#         form = (
#             EnquiryForm()
#             if request.user.is_authenticated
#             else GuestEnquiryForm()
#         )

#     # Prefill form for selected catalog service
#     if selected_service or service_name:
#         initial = {}
#         if service_name:
#             initial["preferred_services"] = service_name
#             if not getattr(form, "is_bound", False):
#                 if hasattr(form, "fields") and "preferred_services" in form.fields:
#                     form.fields["preferred_services"].initial = service_name
#                 form.initial = {**(getattr(form, "initial", None) or {}), **initial}
#                 if service_name and not form.initial.get("product_name"):
#                     form.initial["product_name"] = service_name

#     return render(
#         request,
#         "enquiries/enquiry_now.html",
#         {
#             "form": form,
#             "lab": lab,
#             "linkedin_profile": linkedin_profile,
#             "MOCK_LINKEDIN_LOGIN": MOCK_LINKEDIN_LOGIN,
#             "selected_service": selected_service,
#             "service_name": service_name,
#             "service_title": service_title,
#             "preselect_catalog": bool(selected_service or service_name),
#         },
#     )


from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User, Group
from django.contrib.messages import get_messages

# Import your models & forms accordingly
# from .models import Branch, BranchItem
# from .forms import EnquiryForm, GuestEnquiryForm
# from .utils import get_linkedin_profile, MOCK_LINKEDIN_LOGIN


class EnquiryNowView(View):
    template_name = "enquiries/enquiry_now.html"

    def get_lab_and_service(self, request):
        lab_id = request.GET.get("lab_id") or request.POST.get("lab_id")
        lab = None
        if lab_id:
            try:
                lab = Branch.objects.select_related("lab_category").filter(pk=lab_id).first()
            except (ValueError, TypeError):
                lab = None

        service_id = (
            request.GET.get("service_id")
            or request.POST.get("service_id")
            or request.GET.get("scope_id")
        )
        service_name = (request.GET.get("service") or request.POST.get("service") or "").strip()
        service_title = (request.GET.get("service_title") or request.POST.get("service_title") or "").strip()

        selected_service = None
        if service_id and lab:
            try:
                selected_service = (
                    BranchItem.objects.filter(pk=service_id, lab=lab, is_disable=False)
                    .select_related("service_category")
                    .first()
                )
            except (ValueError, TypeError):
                selected_service = None

        if selected_service and not service_name:
            service_name = (
                selected_service.is_number
                or (selected_service.service_category.name if selected_service.service_category_id else "")
                or selected_service.is_title
                or ""
            )
            if not service_title:
                service_title = selected_service.is_title or selected_service.description or ""

        return lab, selected_service, service_name, service_title

    def get_form_class(self, request):
        return EnquiryForm if request.user.is_authenticated else GuestEnquiryForm

    def get(self, request, *args, **kwargs):
        # Consume and clear unread session messages so past notifications don't leak onto this form
        storage = get_messages(request)
        for _ in storage:
            pass

        lab, selected_service, service_name, service_title = self.get_lab_and_service(request)

        linkedin_profile = {}
        if request.user.is_authenticated:
            linkedin_profile = get_linkedin_profile(request.user) or {}

        form_cls = self.get_form_class(request)
        form = form_cls()

        if selected_service or service_name:
            if hasattr(form, "fields") and "preferred_services" in form.fields:
                form.fields["preferred_services"].initial = service_name
            if hasattr(form, "fields") and "preferred_standards" in form.fields:
                form.fields["preferred_standards"].initial = service_name

            form.initial = {
                **(getattr(form, "initial", None) or {}),
                "preferred_services": service_name,
                "preferred_standards": service_name,
                "product_name": service_name,
            }

        context = {
            "form": form,
            "lab": lab,
            "linkedin_profile": linkedin_profile,
            "MOCK_LINKEDIN_LOGIN": globals().get("MOCK_LINKEDIN_LOGIN", False),
            "selected_service": selected_service,
            "service_name": service_name,
            "service_title": service_title,
            "preselect_catalog": bool(selected_service or service_name),
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        lab, selected_service, service_name, service_title = self.get_lab_and_service(request)
        post_data = request.POST.copy()
        if not post_data.get("description"):
            material = post_data.get("product_name", "")
            preferred_services = post_data.get("preferred_services", service_name)
            post_data["description"] = f"Testing enquiry for {preferred_services or material or 'materials'}."

        form_cls = self.get_form_class(request)
        form = form_cls(post_data, request.FILES)

        linkedin_profile = {}
        if request.user.is_authenticated:
            linkedin_profile = get_linkedin_profile(request.user) or {}

        if form.is_valid():
            enquiry = form.save(commit=False)
            enquiry.lab = lab
            if lab and lab.lab_category_id:
                enquiry.lab_category = lab.lab_category

            # Quotation Type
            allow_multiple = request.POST.get("allow_multiple_labs")
            quotation_type_raw = request.POST.get("quotation_type")
            if not lab:
                quotation_type = "multiple_labs"
            elif allow_multiple in ("on", "1", "true", "multiple_labs") or quotation_type_raw == "multiple_labs":
                quotation_type = "multiple_labs"
            else:
                quotation_type = "selected_lab"
            enquiry.quotation_type = quotation_type

        # Extract Posted Contact Details
            posted_email = (
                request.POST.get("email")
                or form.cleaned_data.get("email")
                or ""
            )
            posted_mobile = (
                request.POST.get("mobile_number")
                or form.cleaned_data.get("mobile_number")
                or ""
            )
            posted_contact_name = (
                request.POST.get("contact_name")
                or form.cleaned_data.get("contact_name")
                or ""
            ).strip()

            otp_code = request.POST.get("otp_code")

            # Handle OTP User Creation for Guests
            if not request.user.is_authenticated and otp_code and posted_email:
                is_otp_valid = True  # TODO: real OTP verification
                if is_otp_valid:
                    name_parts = posted_contact_name.split(" ", 1)
                    first_name = name_parts[0] if name_parts else ""
                    last_name = name_parts[1] if len(name_parts) > 1 else ""

                    user, created = User.objects.get_or_create(
                        email=posted_email,
                        defaults={
                            "username": posted_email,
                            "first_name": first_name,
                            "last_name": last_name,
                        },
                    )
                    if not created:
                        if first_name:
                            user.first_name = first_name
                        if last_name:
                            user.last_name = last_name
                        user.save()

                    customer_group, _ = Group.objects.get_or_create(name="Customer")
                    user.groups.add(customer_group)
                    login(
                        request,
                        user,
                        backend="django.contrib.auth.backends.ModelBackend",
                    )

            # Assign User and Contact Data
            if request.user.is_authenticated:
                enquiry.user = request.user
                enquiry.email = (
                    linkedin_profile.get("email")
                    or request.user.email
                    or posted_email
                    or ""
                )
                enquiry.contact_name = (
                    posted_contact_name
                    or linkedin_profile.get("name")
                    or request.user.get_full_name()
                    or request.user.get_username()
                )
                enquiry.mobile_number = posted_mobile or getattr(enquiry, "mobile_number", "") or ""
            else:
                enquiry.user = None
                enquiry.email = posted_email
                enquiry.mobile_number = posted_mobile
                enquiry.contact_name = posted_contact_name

            # Attach Media File
            if request.FILES.get("media"):
                enquiry.media = request.FILES["media"]

            # Preferred Standards / Services
            pref_service = (
                request.POST.get("preferred_standards")
                or request.POST.get("preferred_services")
                or service_name
                or ""
            )[:255]
            
            if hasattr(enquiry, "preferred_services") and not enquiry.preferred_services:
                enquiry.preferred_services = pref_service
            if hasattr(enquiry, "preferred_standards") and not enquiry.preferred_standards:
                enquiry.preferred_standards = pref_service

            # Ensure budget and urgency from POST are always saved
            budget_val = (request.POST.get("budget") or form.cleaned_data.get("budget") or "").strip()
            enquiry.budget = budget_val

            urgency_val = (request.POST.get("urgency") or form.cleaned_data.get("urgency") or "").strip()
            if urgency_val:
                enquiry.urgency = urgency_val

            enquiry.save()

            if lab:
                if hasattr(enquiry, "ensure_lab_lead"):
                    enquiry.ensure_lab_lead(lab)

            if not request.user.is_authenticated:
                request.session["guest_enquiry_confirmation"] = str(enquiry.pk)

            messages.success(request, "Your enquiry has been successfully submitted.")
            return redirect("enquiry_success", enquiry_id=enquiry.pk)

        else:
            # FIX 2: Show form validation errors so failures are not silent
            messages.error(request, "Please correct the errors below and submit again.")

        context = {
            "form": form,
            "lab": lab,
            "linkedin_profile": linkedin_profile,
            "selected_service": selected_service,
            "service_name": service_name,
            "service_title": service_title,
            # "preselect_catalog": bool(selected_service or service_name),
        }
        return render(request, self.template_name, context)

        
def enquiry_success(request, enquiry_id):
    enquiry = get_object_or_404(Enquiry, pk=enquiry_id)

    is_owner = (
        request.user.is_authenticated and enquiry.user_id == request.user.pk
    )
    is_guest_confirmation = (
        enquiry.user_id is None
        and request.session.get("guest_enquiry_confirmation") == str(enquiry.pk)
    )

    if not (is_owner or is_guest_confirmation or request.user.is_staff):
        return redirect("/")

    return render(
        request,
        "enquiries/enquiry_success.html",
        {"enquiry": enquiry},
    )


@login_required
def lead_detail(request, enquiry_id):
    enquiry = get_object_or_404(
        Enquiry.objects.select_related("lab", "lab_category", "user"),
        pk=enquiry_id,
    )

    user_branch = _branch_for_user(request.user)
    is_customer = enquiry.is_owned_by(request.user)
    is_staff = request.user.is_staff or request.user.is_superuser

    if is_customer and not user_branch and not is_staff:
        return redirect("customer_lead_detail", enquiry_id=enquiry.id)

    lab_lead = None
    target_lab = None

    if user_branch:
        visible = Enquiry.visible_to_branch_qs(user_branch).filter(pk=enquiry.pk).exists()
        if not visible and not is_staff:
            return HttpResponseForbidden(
                "This enquiry is not available to your laboratory."
            )
        lab_lead = enquiry.ensure_lab_lead(user_branch)
        target_lab = user_branch
    elif is_customer or is_staff:
        lab_param = request.GET.get("lab") or request.POST.get("lab")
        if lab_param:
            target_lab = Branch.objects.filter(pk=lab_param).first()
            if target_lab:
                lab_lead = LabLead.objects.filter(
                    enquiry=enquiry, lab=target_lab
                ).first()
        if lab_lead is None:
            leads = list(enquiry.lab_leads.select_related("lab").all()[:5])
            if len(leads) == 1:
                lab_lead = leads[0]
                target_lab = lab_lead.lab
            elif len(leads) > 1 and not lab_param:
                return render(
                    request,
                    "enquiries/lead_detail.html",
                    {
                        "enquiry": enquiry,
                        "lab_lead": None,
                        "lab_leads": leads,
                        "quotation": None,
                        "discussions": [],
                        "discussion_form": EnquiryDiscussionForm(),
                        "status_form": None,
                        "is_lab_side": False,
                        "is_customer": is_customer,
                        "accept_form": AcceptQuotationForm(),
                        "reject_form": RejectQuotationForm(),
                        "needs_lab_pick": True,
                    },
                )
    else:
        return HttpResponseForbidden(
            "You do not have permission to view this lead."
        )

    if lab_lead is None:
        return HttpResponseForbidden(
            "No laboratory conversation found for this enquiry."
        )

    if not lab_lead.can_view(request.user):
        return HttpResponseForbidden(
            "You do not have permission to view this lead."
        )

    is_lab_side = lab_lead.can_manage_as_lab(request.user)

    discussions_qs = lab_lead.discussions.select_related("sender", "lab")
    if is_customer and not is_staff:
        discussions_qs = discussions_qs.filter(is_internal=False)
    discussions = discussions_qs.all()

    discussion_form = EnquiryDiscussionForm()
    status_form = LeadStatusForm(instance=lab_lead)
    quotation = getattr(lab_lead, "quotation", None)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_status":
            if not is_lab_side:
                messages.error(request, "Only the laboratory can update lead status.")
                return redirect(_lead_detail_url(enquiry, lab_lead))

            status_form = LeadStatusForm(request.POST, instance=lab_lead)
            if status_form.is_valid():
                status_form.save()
                messages.success(
                    request,
                    f"Lead status updated to '{lab_lead.get_status_display()}'.",
                )
                subtab = request.POST.get("subtab") or "overview"
                return redirect(_lead_detail_url(enquiry, lab_lead, subtab=subtab))

        elif action == "add_message":
            discussion_form = EnquiryDiscussionForm(request.POST, request.FILES)
            if discussion_form.is_valid():
                msg = discussion_form.save(commit=False)
                msg.lab_lead = lab_lead
                msg.enquiry = enquiry
                msg.lab = lab_lead.lab
                msg.sender = request.user
                msg.sender_type = _resolve_sender_type(request.user, lab_lead)
                if msg.sender_type != "lab":
                    msg.is_internal = False
                msg.save()

                if lab_lead.status == "new":
                    lab_lead.status = "contacted"
                    lab_lead.save(
                        update_fields=["status", "status_changed_at", "updated_at"]
                    )

                messages.success(request, "Message posted successfully.")
                subtab = request.POST.get("subtab") or "chat"
                return redirect(_lead_detail_url(enquiry, lab_lead, subtab=subtab))

        elif action == "accept_quotation":
            if not is_customer and not is_staff:
                messages.error(request, "Only the customer can accept a quotation.")
                return redirect(_lead_detail_url(enquiry, lab_lead))
            if not quotation:
                messages.error(request, "No quotation exists for this conversation.")
                return redirect(_lead_detail_url(enquiry, lab_lead))

            form = AcceptQuotationForm(request.POST)
            if form.is_valid():
                quotation.mark_accepted()
                lab_lead.status = "won"
                lab_lead.save(
                    update_fields=["status", "status_changed_at", "updated_at"]
                )
                # Auto-decline all other labs on this multi-lab enquiry
                lab_lead.decline_competing_labs()
                messages.success(
                    request,
                    "Quotation accepted. Other laboratory quotes on this request were declined. "
                    "The laboratory will create an order to proceed.",
                )
                return redirect(_lead_detail_url(enquiry, lab_lead))

        elif action == "reject_quotation":
            if not is_customer and not is_staff:
                messages.error(request, "Only the customer can decline a quotation.")
                return redirect(_lead_detail_url(enquiry, lab_lead))
            if not quotation:
                messages.error(request, "No quotation exists for this conversation.")
                return redirect(_lead_detail_url(enquiry, lab_lead))

            form = RejectQuotationForm(request.POST)
            if form.is_valid():
                reason = form.cleaned_data.get("reason") or ""
                quotation.mark_rejected(reason)
                lab_lead.status = "lost"
                lab_lead.lost_reason = reason
                lab_lead.save(
                    update_fields=[
                        "status",
                        "status_changed_at",
                        "lost_reason",
                        "updated_at",
                    ]
                )
                messages.info(request, "Quotation declined. Lead marked as lost.")
                return redirect(_lead_detail_url(enquiry, lab_lead))

    return render(
        request,
        "enquiries/lead_detail.html",
        {
            "enquiry": enquiry,
            "lab_lead": lab_lead,
            "lab_leads": None,
            "quotation": quotation,
            "discussions": discussions,
            "discussion_form": discussion_form,
            "status_form": status_form,
            "is_lab_side": is_lab_side,
            "is_customer": is_customer,
            "accept_form": AcceptQuotationForm(),
            "reject_form": RejectQuotationForm(),
            "needs_lab_pick": False,
            "branch": user_branch or getattr(lab_lead, "lab", None),
            "active_tab": "leads",
            "subtab": request.GET.get("subtab", "overview"),
        },
    )


@login_required
def create_quotation(request, enquiry_id):
    enquiry = get_object_or_404(Enquiry, pk=enquiry_id)
    user_branch = _branch_for_user(request.user)

    if not user_branch and not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden(
            "Only a laboratory account can create a quotation."
        )

    if user_branch:
        lab = user_branch
    else:
        lab_id = request.GET.get("lab") or request.POST.get("lab")
        lab = get_object_or_404(Branch, pk=lab_id) if lab_id else None
        if not lab:
            return HttpResponseForbidden("Laboratory context required.")

    if not (
        request.user.is_staff
        or Enquiry.visible_to_branch_qs(lab).filter(pk=enquiry.pk).exists()
    ):
        return HttpResponseForbidden(
            "This enquiry is not available to your laboratory."
        )

    lab_lead = enquiry.ensure_lab_lead(lab)

    if not lab_lead.can_manage_as_lab(request.user):
        return HttpResponseForbidden(
            "Only the laboratory handling this lead can create a quotation."
        )

    if hasattr(lab_lead, "quotation") and lab_lead.quotation:
        messages.info(request, "A quotation already exists for this conversation.")
        return redirect(_lead_detail_url(enquiry, lab_lead))

    if request.method == "POST":
        quote_form = QuotationForm(request.POST)
        if quote_form.is_valid():
            quotation = quote_form.save(commit=False)
            quotation.lab_lead = lab_lead
            quotation.enquiry = enquiry
            quotation.lab = lab
            quotation.created_by = request.user
            quotation.quote_number = f"QT-{uuid.uuid4().hex[:8].upper()}"
            quotation.save()

            lab_lead.status = "quoted"
            lab_lead.save(
                update_fields=["status", "status_changed_at", "updated_at"]
            )

            EnquiryDiscussion.objects.create(
                lab_lead=lab_lead,
                enquiry=enquiry,
                lab=lab,
                sender=request.user,
                sender_type="lab",
                message=(
                    f"Formal quotation #{quotation.quote_number} has been issued.\n"
                    f"Amount: {quotation.currency} {quotation.total_amount}\n"
                    f"Estimated turnaround: {quotation.estimated_turnaround_days} day(s).\n"
                    f"Valid for {quotation.validity_days} day(s)."
                ),
            )

            messages.success(
                request,
                f"Quotation #{quotation.quote_number} generated successfully.",
            )
            return redirect(_lead_detail_url(enquiry, lab_lead))
        else:
            print("quote_form errors:", quote_form.errors)
    else:
        quote_form = QuotationForm()

    return render(
        request,
        "enquiries/create_quotation.html",
        {
            "enquiry": enquiry,
            "lab_lead": lab_lead,
            "quote_form": quote_form,
            "branch": lab,
            "active_tab": "leads",
        },
    )


@login_required
def mark_lead_won(request, enquiry_id):
    enquiry = get_object_or_404(Enquiry, pk=enquiry_id)
    user_branch = _branch_for_user(request.user)

    if not user_branch and not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden(
            "Only the laboratory can convert this lead into a LIMS job."
        )

    if user_branch:
        lab = user_branch
    else:
        lab_id = request.GET.get("lab") or request.POST.get("lab")
        lab = get_object_or_404(Branch, pk=lab_id) if lab_id else None
        if not lab:
            return HttpResponseForbidden("Laboratory context required.")

    lab_lead = LabLead.objects.filter(enquiry=enquiry, lab=lab).first()
    if not lab_lead:
        return HttpResponseForbidden("No lead participation found for your lab.")

    if not lab_lead.can_manage_as_lab(request.user):
        return HttpResponseForbidden(
            "Only the laboratory can convert this lead into a LIMS job."
        )

    if request.method != "POST":
        return redirect(_lead_detail_url(enquiry, lab_lead))

    if lab_lead.status not in ("quoted", "won"):
        messages.warning(
            request,
            "Lead should be in 'Quoted' or 'Won' status before conversion.",
        )
        return redirect(_lead_detail_url(enquiry, lab_lead))

    lab_lead.status = "won"
    lab_lead.save(update_fields=["status", "status_changed_at", "updated_at"])

    job_number = f"JOB-{uuid.uuid4().hex[:6].upper()}"
    accession_id = f"SMP-{uuid.uuid4().hex[:8].upper()}"

    lims_job, created = LIMSJobOrder.objects.get_or_create(
        lab_lead=lab_lead,
        defaults={
            "enquiry": enquiry,
            "job_number": job_number,
            "sample_accession_id": accession_id,
            "status": "sample_received",
            "sample_received_at": timezone.now(),
        },
    )

    lab_lead.status = "converted"
    lab_lead.save(update_fields=["status", "status_changed_at", "updated_at"])

    if created:
        EnquiryDiscussion.objects.create(
            lab_lead=lab_lead,
            enquiry=enquiry,
            lab=lab,
            sender=request.user,
            sender_type="lab",
            message=(
                f"Sample accessioned. LIMS Job #{lims_job.job_number} "
                f"created with Sample ID {lims_job.sample_accession_id}."
            ),
        )

    messages.success(
        request,
        f"Lead converted to LIMS Job Job/Order #{lims_job.job_number} "
        f"(Sample ID {lims_job.sample_accession_id}).",
    )
    return redirect(_lead_detail_url(enquiry, lab_lead))


def get_leads_dashboard_context(request, current_branch):
    """
    Visibility:
      selected_lab  → enquiry.lab == current_branch
      multiple_labs → enquiry.lab_category == current_branch.lab_category

    Status is per-lab (LabLead). Unengaged multi-lab enquiries show as 'new'.
    """
    visible_enquiries = (
        Enquiry.visible_to_branch_qs(current_branch)
        .select_related("user", "lab", "lab_category")
        .prefetch_related(
            Prefetch(
                "lab_leads",
                queryset=LabLead.objects.filter(lab=current_branch).select_related(
                    "lab"
                ),
                to_attr="my_lab_leads",
            )
        )
        .order_by("-created_at")
    )

    rows = []
    for enq in visible_enquiries:
        my_lead = enq.my_lab_leads[0] if enq.my_lab_leads else None
        effective_status = my_lead.status if my_lead else "new"
        rows.append(
            {
                "enquiry": enq,
                "lab_lead": my_lead,
                "status": effective_status,
                "status_display": (
                    my_lead.get_status_display() if my_lead else "Inbound Enquiry"
                ),
            }
        )

    def _count(status_key):
        return sum(1 for r in rows if r["status"] == status_key)

    counts = {
        "all": len(rows),
        "new": _count("new"),
        "contacted": _count("contacted"),
        "quoted": _count("quoted"),
        "won": _count("won"),
        "converted": _count("converted"),
        "lost": _count("lost"),
        "not_qualified": _count("not_qualified"),
        "in_progress": _count("contacted"),
        "interested": _count("quoted"),
    }

    status_filter = request.GET.get("status", "all")
    if status_filter in ("in_progress", "interested"):
        status_filter = "contacted" if status_filter == "in_progress" else "quoted"

    if status_filter != "all":
        rows = [r for r in rows if r["status"] == status_filter]

    # Attach per-lab status onto enquiry for template compatibility
    enquiries_out = []
    for r in rows:
        enq = r["enquiry"]
        enq.effective_status = r["status"]
        enq.effective_status_display = r["status_display"]
        enquiries_out.append(enq)

    context = {
        "lead_rows": rows,
        "enquiries": enquiries_out,
        "counts": counts,
        "active_status": request.GET.get("status", "all"),
        "current_branch": current_branch,
    }

    leads_html = render_to_string(
        "enquiries/includes/_leads_tab.html", context, request=request
    )
    return {"context": context, "rendered_html": leads_html}


def get_reviews_dashboard_context(request, current_branch):
    reviews = LabReview.objects.filter(
        lab=current_branch, is_approved=True
    ).prefetch_related("category_ratings__category").order_by("-created_at")

    total_count = reviews.count()
    overall_avg = (
        reviews.aggregate(Avg("overall_rating"))["overall_rating__avg"] or 0.0
    )

    active_categories = ReviewCategory.objects.filter(is_active=True)
    category_averages = []

    for cat in active_categories:
        avg_score = (
            LabReviewCategoryRating.objects.filter(
                review__lab=current_branch,
                review__is_approved=True,
                category=cat,
            ).aggregate(Avg("rating"))["rating__avg"]
            or 0.0
        )
        category_averages.append(
            {"name": cat.name, "avg_score": round(avg_score, 1)}
        )

    # Star distribution (5★ to 1★)
    star_breakdown = []
    if total_count > 0:
        counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        for r in reviews:
            r_val = int(round(float(r.overall_rating or 0)))
            r_val = max(1, min(5, r_val))
            counts[r_val] += 1
        for s in [5, 4, 3, 2, 1]:
            pct = round((counts[s] / total_count) * 100)
            star_breakdown.append({
                "stars": s,
                "label": f"{s}★",
                "count": counts[s],
                "pct": pct,
            })
    # else:
    #     # Default placeholder breakdown matching figma-screens/lab/Reviews.png
    #     default_dist = [(5, 72), (4, 19), (3, 6), (2, 2), (1, 1)]
    #     for s, pct in default_dist:
    #         star_breakdown.append({
    #             "stars": s,
    #             "label": f"{s}★",
    #             "count": 0,
    #             "pct": pct,
    #         })

    can_hide_reviews = current_branch.can_hide_reviews if current_branch else False

    context = {
        "reviews": reviews,
        "total_count": total_count,
        "display_count": total_count if total_count > 0 else 32,
        "overall_avg": round(overall_avg, 1) if overall_avg > 0 else 4.7,
        "category_averages": category_averages,
        "active_categories": active_categories,
        "star_breakdown": star_breakdown,
        "can_hide_reviews": can_hide_reviews,
    }

    rendered_html = render_to_string(
        "accounts/includes/_reviews_tab.html", context, request=request
    )
    return {"context": context, "rendered_html": rendered_html}


class SubmitLabReviewView(View):
    template_name = "enquiries/submit_review.html"

    def get(self, request, lab_id, *args, **kwargs):
        branch = get_object_or_404(Branch, pk=lab_id)
        categories = ReviewCategory.objects.filter(is_active=True).order_by(
            "sort_order", "name"
        )
        return render(
            request,
            self.template_name,
            {"branch": branch, "categories": categories},
        )

    def post(self, request, lab_id, *args, **kwargs):
        branch = get_object_or_404(Branch, pk=lab_id)

        if not request.user.is_authenticated:
            messages.error(
                request, "Please log in or sign up to submit your review."
            )
            return redirect("lab-detail", pk=lab_id)

        title = request.POST.get("title", "").strip()
        summary = request.POST.get("summary", "").strip()
        
        # Support both modal 'is_public' checkbox and standalone 'is_anonymous' field
        if "is_public" in request.POST:
            is_anonymous = not (request.POST.get("is_public") in ["1", "on", "true"])
        else:
            is_anonymous = request.POST.get("is_anonymous") == "on"

        # Create main review entry
        review = LabReview.objects.create(
            lab=branch,
            user=request.user,
            title=title if title else (summary[:50] if summary else "Lab Review"),
            summary=summary,
            is_anonymous=is_anonymous,
            is_approved=True,
        )

        # Dynamic category rating creation driven by active ReviewCategory objects
        categories = ReviewCategory.objects.filter(is_active=True)
        for cat in categories:
            rating_val = request.POST.get(f"category_rating_{cat.pk}")
            if rating_val:
                try:
                    LabReviewCategoryRating.objects.create(
                        review=review,
                        category=cat,
                        rating=Decimal(str(rating_val)),
                    )
                except (ValueError, TypeError):
                    pass

        # Calculate overall score dynamically from category ratings or fallback to explicit rating
        overall_val = request.POST.get("overall_rating")
        if overall_val:
            try:
                review.overall_rating = Decimal(str(overall_val))
                review.save(update_fields=["overall_rating"])
            except (ValueError, TypeError):
                review.calculate_overall_rating()
        else:
            review.calculate_overall_rating()

        messages.success(request, "Thank you! Your review has been submitted.")
        return redirect("lab-detail", pk=branch.pk)


class ReplyLabReviewView(View):
    def post(self, request, *args, **kwargs):
        review_id = request.POST.get("review_id")
        reply_message = request.POST.get("reply_message", "").strip()
        is_ajax = (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            or request.headers.get("accept", "").startswith("application/json")
        )

        review = get_object_or_404(LabReview, pk=review_id)

        if reply_message:
            review.lab_reply = reply_message
            review.replied_at = timezone.now()
            review.save(update_fields=["lab_reply", "replied_at", "updated_at"])
            if not is_ajax:
                messages.success(request, "Your reply has been published.")

        if is_ajax:
            return JsonResponse({"status": "success", "reply": reply_message, "message": "Your reply has been published."})
        return redirect(f"{reverse('dashboard')}?tab=reviews")


class ToggleHideLabReviewView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        review_id = request.POST.get("review_id")
        if not review_id:
            return JsonResponse({"status": "error", "message": "Missing review ID."}, status=400)

        review = get_object_or_404(LabReview, pk=review_id)
        lab = review.lab

        user = request.user
        is_authorized = (
            user.is_staff
            or user.is_superuser
            or lab.user == user
            or getattr(user, "branch", None) == lab
            or getattr(user, "user_type", None) == "lab"
        )
        if not is_authorized:
            return JsonResponse(
                {"status": "error", "message": "Unauthorized to manage reviews for this laboratory."},
                status=403,
            )

        if not lab.can_hide_reviews:
            return JsonResponse(
                {
                    "status": "upgrade_required",
                    "message": "Hiding reviews from your public profile is a Trusted Partner (Pro) feature. Upgrade your promotional package to unlock this feature.",
                },
                status=403,
            )

        review.is_hidden_by_lab = not review.is_hidden_by_lab
        review.save(update_fields=["is_hidden_by_lab", "updated_at"])

        status_text = "hidden from" if review.is_hidden_by_lab else "made visible on"
        return JsonResponse({
            "status": "success",
            "is_hidden": review.is_hidden_by_lab,
            "message": f"Review has been {status_text} your public profile.",
        })


class UpdateCustomerReviewView(LoginRequiredMixin, View):
    def post(self, request, review_id, *args, **kwargs):
        review = get_object_or_404(LabReview, pk=review_id, user=request.user)

        title = request.POST.get("title", "").strip()
        summary = request.POST.get("summary", "").strip()
        is_anonymous = request.POST.get("is_anonymous") == "on"

        if title and summary:
            review.title = title
            review.summary = summary
            review.is_anonymous = is_anonymous
            review.save()

            active_categories = ReviewCategory.objects.filter(is_active=True)
            for cat in active_categories:
                score = request.POST.get(f"category_rating_{cat.pk}")
                if score:
                    cat_rating, _ = LabReviewCategoryRating.objects.get_or_create(
                        review=review, category=cat
                    )
                    cat_rating.rating = float(score)
                    cat_rating.save()

            review.calculate_overall_rating()

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "success": True,
                        "message": "Your review has been updated successfully.",
                        "title": review.title,
                        "summary": review.summary,
                        "overall_rating": float(review.overall_rating),
                        "is_anonymous": review.is_anonymous,
                    }
                )

            messages.success(request, "Your review has been updated.")
            return redirect("dashboard")

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "success": False,
                    "message": "Title and summary content are required.",
                },
                status=400,
            )

        messages.error(request, "Failed to update review.")
        return redirect("dashboard")


# ---------------------------------------------------------------------------
# Create Order from won LabLead (lab side)
# ---------------------------------------------------------------------------

@login_required
def create_order_from_lead(request, enquiry_id):
    """Lab accepts won lead and creates a LIMSJobOrder for further work."""
    enquiry = get_object_or_404(Enquiry, pk=enquiry_id)
    user_branch = _branch_for_user(request.user)
    if not user_branch and not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden("Only the laboratory can create an order.")

    lab = user_branch
    if not lab:
        lab_id = request.GET.get("lab") or request.POST.get("lab")
        lab = get_object_or_404(Branch, pk=lab_id) if lab_id else None
        if not lab:
            return HttpResponseForbidden("Laboratory context required.")

    lab_lead = LabLead.objects.filter(enquiry=enquiry, lab=lab).first()
    if not lab_lead or not lab_lead.can_manage_as_lab(request.user):
        return HttpResponseForbidden("Not allowed.")

    if lab_lead.status not in ("won", "quoted"):
        messages.warning(request, "Lead must be Won before creating an order.")
        return redirect(_lead_detail_url(enquiry, lab_lead))

    if hasattr(lab_lead, "lims_job") and lab_lead.lims_job:
        messages.info(request, "Order already exists.")
        return redirect("order_detail", order_id=lab_lead.lims_job.pk)

    if request.method != "POST":
        return redirect(_lead_detail_url(enquiry, lab_lead))

    # Ensure won + decline competitors
    lab_lead.status = "won"
    lab_lead.save(update_fields=["status", "status_changed_at", "updated_at"])
    lab_lead.decline_competing_labs()

    job_number = f"JOB-{uuid.uuid4().hex[:8].upper()}"
    accession_id = f"SMP-{uuid.uuid4().hex[:8].upper()}"
    order = LIMSJobOrder.objects.create(
        lab_lead=lab_lead,
        enquiry=enquiry,
        lab=lab,
        customer=enquiry.user,
        job_number=job_number,
        sample_accession_id=accession_id,
        status="in_progress",
        sample_received_at=timezone.now(),
    )

    lab_lead.status = "converted"
    lab_lead.save(update_fields=["status", "status_changed_at", "updated_at"])

    OrderMessage.objects.create(
        order=order,
        sender=request.user,
        sender_type="lab",
        message=f"Job/Order #{order.job_number} created. Further communication continues on this order.",
    )

    messages.success(request, f"Job/Order #{order.job_number} created successfully.")
    return redirect("order_detail", order_id=order.pk)


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        LIMSJobOrder.objects.select_related(
            "lab_lead", "enquiry", "lab", "customer"
        ).prefetch_related("messages", "documents", "disputes"),
        pk=order_id,
    )
    if not order.is_participant(request.user):
        return HttpResponseForbidden("You cannot view this order.")

    user_branch = _branch_for_user(request.user)
    is_lab_side = bool(
        user_branch and user_branch.pk == order.lab_id
    ) or request.user.is_staff
    is_customer = order.customer_id == request.user.pk

    messages_qs = order.messages.select_related("sender").all()
    if is_customer and not request.user.is_staff:
        messages_qs = messages_qs.filter(is_internal=False)

    msg_form = OrderMessageForm()
    invoice_form = OrderInvoiceForm(instance=order)
    doc_form = OrderDocumentForm()
    dispute_form = DisputeForm()

    if request.method == "POST":
        action = request.POST.get("action")
        subtab = request.POST.get("subtab") or request.GET.get("subtab")

        def _redirect_with_subtab(target_subtab):
            st = subtab or target_subtab
            url = reverse("order_detail", kwargs={"order_id": order.pk})
            if st:
                url = f"{url}?subtab={st}"
            return redirect(url)

        if action == "add_message":
            msg_form = OrderMessageForm(request.POST, request.FILES)
            if msg_form.is_valid():
                m = msg_form.save(commit=False)
                m.order = order
                m.sender = request.user
                m.sender_type = "lab" if is_lab_side else "customer"
                if not is_lab_side:
                    m.is_internal = False
                m.save()
                messages.success(request, "Message sent.")
                return _redirect_with_subtab("chat")
            else:
                messages.error(request, f"Failed to send message: {msg_form.errors.as_text()}")
                return _redirect_with_subtab("chat")

        elif action == "upload_invoice" and is_lab_side:
            invoice_form = OrderInvoiceForm(request.POST, request.FILES, instance=order)
            if invoice_form.is_valid():
                o = invoice_form.save(commit=False)
                o.invoice_uploaded_at = timezone.now()
                o.save()
                messages.success(request, "Invoice uploaded.")
                return _redirect_with_subtab("qi")
            else:
                messages.error(request, f"Failed to upload invoice: {invoice_form.errors.as_text()}")
                return _redirect_with_subtab("qi")

        elif action == "upload_document":
            doc_form = OrderDocumentForm(request.POST, request.FILES)
            if doc_form.is_valid():
                d = doc_form.save(commit=False)
                d.order = order
                d.uploaded_by = request.user
                d.save()
                messages.success(request, "Document uploaded.")
                return _redirect_with_subtab("docs" if is_lab_side else "documents")
            else:
                messages.error(request, f"Failed to upload document: {doc_form.errors.as_text()}")
                return _redirect_with_subtab("docs" if is_lab_side else "documents")

        elif action == "mark_complete_customer" and is_customer:
            order.status = "completed"
            order.completed_at = timezone.now()
            order.completed_by = request.user
            order.completion_requested_by = ""
            order.save()
            messages.success(request, "Order marked as completed.")
            return _redirect_with_subtab("overview")

        elif action == "mark_complete_lab" and is_lab_side:
            order.status = "pending_customer_completion"
            order.completion_requested_by = "lab"
            order.save(update_fields=["status", "completion_requested_by", "updated_at"])
            messages.info(
                request,
                "Completion requested. Waiting for customer to confirm.",
            )
            return _redirect_with_subtab("overview")

        elif action == "confirm_completion_customer" and is_customer:
            if order.status == "pending_customer_completion":
                order.status = "completed"
                order.completed_at = timezone.now()
                order.completed_by = request.user
                order.completion_requested_by = ""
                order.save()
                messages.success(request, "Order completion confirmed.")
            return _redirect_with_subtab("overview")

        elif action == "decline_completion_customer" and is_customer:
            if order.status == "pending_customer_completion":
                order.status = "in_progress"
                order.completion_requested_by = ""
                order.save(update_fields=["status", "completion_requested_by", "updated_at"])
                messages.info(request, "Completion declined. Order remains in progress.")
            return _redirect_with_subtab("overview")

        elif action == "pay_advance" and is_customer:
            if order.status in ("payment", "new"):
                order.status = "sample_received"
                order.sample_received_at = timezone.now()
                order.save(update_fields=["status", "sample_received_at", "updated_at"])
            messages.success(request, "Advance payment placed in escrow. Please arrange sample dispatch.")
            return _redirect_with_subtab("payments")

        elif action == "raise_dispute":
            dispute_form = DisputeForm(request.POST)
            if dispute_form.is_valid():
                d = dispute_form.save(commit=False)
                d.order = order
                d.raised_by = request.user
                d.raised_by_type = "lab" if is_lab_side else "customer"
                d.status = "open"
                d.save()
                order.status = "disputed"
                order.save(update_fields=["status", "updated_at"])
                messages.warning(request, "Dispute raised. LabFinder team will review.")
                return _redirect_with_subtab("dispute")
            else:
                messages.error(request, f"Failed to raise dispute: {dispute_form.errors.as_text()}")
                return _redirect_with_subtab("dispute")

    if is_customer and not is_lab_side:
        # Customer-facing Order & Payment View (Figma Orders_Payments.png)
        total_amount = Decimal("0")
        quotation = getattr(getattr(order, "lab_lead", None), "quotation", None)
        if quotation and quotation.total_amount:
            total_amount = quotation.total_amount
        half_amount = (total_amount / Decimal("2")) if total_amount else Decimal("0")
        paid_amount = Decimal("0")
        if order.status in ("in_progress", "sample_received"):
            paid_amount = half_amount
        elif order.status in ("completed", "pending_customer_completion"):
            paid_amount = total_amount
        balance_amount = max(Decimal("0"), total_amount - paid_amount)

        # 5-step stepper indicator
        if order.status in ("payment", "new"):
            stepper_step = 1
        elif order.status == "sample_received":
            stepper_step = 2
        elif order.status == "in_progress":
            stepper_step = 3
        elif order.status == "pending_customer_completion":
            stepper_step = 4
        elif order.status == "completed":
            stepper_step = 5
        else:
            stepper_step = 1

        subtab = request.GET.get("subtab", "payments")

        # Fallback amounts for sample/demo orders - static data for now, can be removed once we have proper quotations in place
        if total_amount == Decimal("0"):
            total_amount = Decimal("3304")
            half_amount = Decimal("1652")
            balance_amount = Decimal("3304")

        return render(
            request,
            "customers/customer_order_detail.html",
            {
                "order": order,
                "quotation": quotation,
                "total_amount": total_amount,
                "half_amount": half_amount,
                "paid_amount": paid_amount,
                "balance_amount": balance_amount,
                "stepper_step": stepper_step,
                "active_tab": "orders",
                "subtab": subtab,
                "order_messages": messages_qs,
                "msg_form": msg_form,
                "doc_form": doc_form,
                "dispute_form": dispute_form,
                "active_dispute": order.disputes.filter(status__in=["open", "under_review"]).first(),
                "documents": order.documents.all(),
                "is_lab_side": is_lab_side,
                "is_customer": is_customer,
            },
        )

    return render(
        request,
        "enquiries/order_detail.html",
        {
            "order": order,
            "branch": user_branch or order.lab,
            "active_tab": "orders",
            "subtab": request.GET.get("subtab", "overview"),
            "order_messages": messages_qs,
            "msg_form": msg_form,
            "invoice_form": invoice_form,
            "doc_form": doc_form,
            "dispute_form": dispute_form,
            "is_lab_side": is_lab_side,
            "is_customer": is_customer,
            "active_dispute": order.disputes.filter(status__in=["open", "under_review"]).first(),
        },
    )


def _format_inr(amount):
    """Group a rupee amount the Indian way: 6844 -> 6,844."""
    if amount is None:
        return ""
    n = int(Decimal(amount).quantize(Decimal("1")))
    sign = "-" if n < 0 else ""
    digits = str(abs(n))
    if len(digits) <= 3:
        return sign + digits
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while head:
        groups.append(head[-2:])
        head = head[:-2]
    return sign + ",".join(reversed(groups)) + "," + tail


def _order_quotation(order):
    lead = getattr(order, "lab_lead", None)
    if not lead:
        return None
    try:
        return lead.quotation
    except Quotation.DoesNotExist:
        return None


# Labels and next steps follow the Orders list in the lab-portal designs.
_ORDER_LIST_LABELS = {
    "sample_received": "Sample received",
    "in_progress": "In testing",
    "pending_customer_completion": "Report ready",
    "completed": "Completed",
    "disputed": "Disputed",
    "cancelled": "Cancelled",
}
_ORDER_NEXT_ACTION = {
    "sample_received": "Upload report & mark ready",
    "in_progress": "Upload report & mark ready",
    "pending_customer_completion": "Mark order completed",
    "disputed": "Reply to customer",
    "completed": "",
    "cancelled": "",
}
_ORDER_FILTERS = {
    "all",
    "quote_sent",
    "confirmed",
    "sample_received",
    "in_progress",
    "pending_customer_completion",
    "completed",
    "disputed",
}


def get_orders_dashboard_context(request, current_branch):
    orders = (
        LIMSJobOrder.objects.filter(lab=current_branch)
        .select_related("enquiry", "customer", "lab_lead", "lab_lead__quotation")
        .order_by("-created_at")
    )
    status_filter = request.GET.get("order_status", "all")
    if status_filter not in _ORDER_FILTERS:
        status_filter = "all"
    if status_filter != "all":
        filtered = orders.filter(status=status_filter)
    else:
        filtered = orders

    new_cutoff = timezone.now() - timedelta(hours=48)
    outstanding = Decimal("0")
    active_count = 0
    action_count = 0
    rows = []
    for order in orders:
        quotation = _order_quotation(order)
        value = quotation.total_amount if quotation else None
        if order.status not in ("completed", "cancelled"):
            active_count += 1
            if value:
                outstanding += value
        if order.status in (
            "sample_received",
            "in_progress",
            "pending_customer_completion",
            "disputed",
        ):
            action_count += 1
        if order.status == "completed":
            payment_label = "Paid in full"
            payment_pct = 100
        elif order.invoice:
            payment_label = "Invoice sent"
            payment_pct = 50
        else:
            payment_label = ""
            payment_pct = 0
        rows.append(
            {
                "order": order,
                "is_new": order.created_at >= new_cutoff,
                "value_display": _format_inr(value) if value is not None else "",
                "payment_label": payment_label,
                "payment_pct": payment_pct,
                "status_label": _ORDER_LIST_LABELS.get(
                    order.status, order.get_status_display()
                ),
                "next_action": _ORDER_NEXT_ACTION.get(order.status, ""),
            }
        )

    counts = {
        "all": orders.count(),
        "quote_sent": 0,
        "confirmed": 0,
        "sample_received": orders.filter(status="sample_received").count(),
        "in_progress": orders.filter(status="in_progress").count(),
        "pending_customer_completion": orders.filter(
            status="pending_customer_completion"
        ).count(),
        "completed": orders.filter(status="completed").count(),
        "disputed": orders.filter(status="disputed").count(),
    }
    if status_filter == "all":
        visible_rows = rows
    else:
        visible_rows = [r for r in rows if r["order"].status == status_filter]

    context = {
        "orders": filtered,
        "order_rows": visible_rows,
        "order_counts": counts,
        "active_order_status": status_filter,
        "order_stats": {
            "active": active_count,
            "action": action_count,
            "outstanding": _format_inr(outstanding),
            "disputes": counts["disputed"],
        },
    }
    html = render_to_string(
        "enquiries/includes/_orders_tab.html", context, request=request
    )
    return {"context": context, "rendered_html": html}


def get_disputes_dashboard_context(request, current_branch):
    disputes = (
        Dispute.objects.filter(order__lab=current_branch)
        .select_related("order", "order__enquiry", "raised_by")
        .order_by("-created_at")
    )
    status_filter = request.GET.get("dispute_status", "all")
    if status_filter != "all":
        filtered = disputes.filter(status=status_filter)
    else:
        filtered = disputes

    counts = {
        "all": disputes.count(),
        "open": disputes.filter(status="open").count(),
        "under_review": disputes.filter(status="under_review").count(),
        "resolved": disputes.filter(status="resolved").count(),
    }
    context = {
        "disputes": filtered,
        "dispute_counts": counts,
        "active_dispute_status": status_filter,
    }
    html = render_to_string(
        "enquiries/includes/_disputes_tab.html", context, request=request
    )
    return {"context": context, "rendered_html": html}
