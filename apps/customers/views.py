from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView

from apps.enquiries.models import (
    Dispute,
    Enquiry,
    EnquiryDiscussion,
    LabLead,
    LabReview,
    Quotation,
    LIMSJobOrder,
)


# Status priority for customer-facing aggregate (highest first)
_STATUS_RANK = {
    "converted": 70,
    "won": 60,
    "quoted": 50,
    "contacted": 40,
    "new": 30,
    "not_qualified": 20,
    "lost": 10,
}


def _aggregate_status(lab_leads):
    """
    Best status across all lab participations for dashboard chips/pills.
    No lab engaged yet → 'new'.
    """
    if not lab_leads:
        return "new", "Inbound Enquiry"
    best = max(lab_leads, key=lambda ll: _STATUS_RANK.get(ll.status, 0))
    return best.status, best.get_status_display()


def _annotate_enquiries(queryset):
    """Attach aggregate status + lab_lead list for templates."""
    items = []
    for enq in queryset:
        leads = list(enq.lab_leads.all()) if hasattr(enq, "lab_leads") else []
        # If prefetched with to_attr
        if hasattr(enq, "prefetched_lab_leads"):
            leads = enq.prefetched_lab_leads
        status, status_display = _aggregate_status(leads)
        enq.effective_status = status
        enq.effective_status_display = status_display
        enq.lab_lead_count = len(leads)
        enq.quoted_count = sum(1 for ll in leads if ll.status == "quoted")
        items.append(enq)
    return items


def render_customer_dashboard(request):
    """Customer dashboard: enquiries owned by the logged-in user."""
    base = (
        Enquiry.objects.filter(user=request.user)
        .select_related("lab", "lab_category")
        .prefetch_related(
            Prefetch(
                "lab_leads",
                queryset=LabLead.objects.select_related("lab", "quotation").order_by(
                    "-updated_at"
                ),
                to_attr="prefetched_lab_leads",
            )
        )
        .order_by("-created_at")
    )

    all_items = _annotate_enquiries(list(base))

    status_filter = request.GET.get("status", "all")
    if status_filter != "all":
        filtered = [e for e in all_items if e.effective_status == status_filter]
    else:
        filtered = all_items

    def _count(key):
        return sum(1 for e in all_items if e.effective_status == key)

    counts = {
        "all": len(all_items),
        "new": _count("new"),
        "contacted": _count("contacted"),
        "quoted": _count("quoted"),
        "won": _count("won"),
        "converted": _count("converted"),
        "lost": _count("lost"),
    }

    user_reviews = (
        LabReview.objects.filter(user=request.user)
        .select_related("lab")
        .order_by("-created_at")
    )

    customer_orders = (
        LIMSJobOrder.objects.filter(customer=request.user)
        .select_related("lab", "enquiry", "lab_lead")
        .order_by("-created_at")
    )
    customer_disputes = (
        Dispute.objects.filter(order__customer=request.user)
        .select_related("order", "order__lab")
        .order_by("-created_at")
    )

    context = {
        "enquiries": filtered,
        "counts": counts,
        "active_status": status_filter,
        "user_reviews": user_reviews,
        "reviews_count": user_reviews.count(),
        "orders": customer_orders,
        "order_counts": {
            "all": customer_orders.count(),
            "in_progress": customer_orders.filter(status="in_progress").count(),
            "completed": customer_orders.filter(status="completed").count(),
            "disputed": customer_orders.filter(status="disputed").count(),
        },
        "disputes": customer_disputes,
        "dispute_counts": {
            "all": customer_disputes.count(),
            "open": customer_disputes.filter(status__in=["open", "under_review"]).count(),
            "resolved": customer_disputes.filter(status="resolved").count(),
        },
        "active_tab": request.GET.get("tab", "leads"),
    }
    return render(request, "customers/customer_dashboard.html", context)


class CustomerLeadDetailView(LoginRequiredMixin, DetailView):
    """
    Customer view of an enquiry.
    Multi-lab: lists every LabLead (lab responses) with separate chat/quote.
    Optional ?lab=<uuid> focuses on one lab conversation.
    """

    model = Enquiry
    template_name = "customers/customer_lead_detail.html"
    context_object_name = "enquiry"
    pk_url_kwarg = "enquiry_id"

    def get_queryset(self):
        return (
            Enquiry.objects.filter(user=self.request.user)
            .select_related("lab", "lab_category")
            .prefetch_related(
                Prefetch(
                    "lab_leads",
                    queryset=LabLead.objects.select_related(
                        "lab", "quotation", "lims_job"
                    ).prefetch_related(
                        Prefetch(
                            "discussions",
                            queryset=EnquiryDiscussion.objects.filter(
                                is_internal=False
                            ).select_related("sender", "lab"),
                        )
                    ),
                )
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enquiry = self.object
        lab_leads = list(enquiry.lab_leads.all())

        status, status_display = _aggregate_status(lab_leads)
        context["effective_status"] = status
        context["effective_status_display"] = status_display
        context["lab_leads"] = lab_leads

        # Optional focused lab thread
        lab_param = self.request.GET.get("lab")
        active_lead = None
        if lab_param:
            active_lead = next(
                (ll for ll in lab_leads if str(ll.lab_id) == str(lab_param)), None
            )
        elif len(lab_leads) == 1:
            active_lead = lab_leads[0]

        context["active_lab_lead"] = active_lead
        if active_lead:
            context["quotation"] = getattr(active_lead, "quotation", None)
            context["discussions"] = [
                d for d in active_lead.discussions.all() if not d.is_internal
            ]
        else:
            context["quotation"] = None
            context["discussions"] = []

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        enquiry = self.object
        message_text = request.POST.get("message", "").strip()
        lab_id = request.POST.get("lab") or request.GET.get("lab")

        if not message_text:
            messages.error(request, "Message cannot be empty.")
            return redirect(self._detail_url(enquiry, lab_id))

        lab_lead = None
        if lab_id:
            lab_lead = LabLead.objects.filter(enquiry=enquiry, lab_id=lab_id).first()
        if lab_lead is None:
            # Only one participation → use it
            leads = list(enquiry.lab_leads.all()[:2])
            if len(leads) == 1:
                lab_lead = leads[0]

        if lab_lead is None:
            messages.error(
                request,
                "Select a laboratory conversation before sending a message.",
            )
            return redirect(self._detail_url(enquiry, None))

        EnquiryDiscussion.objects.create(
            lab_lead=lab_lead,
            enquiry=enquiry,
            lab=lab_lead.lab,
            sender=request.user,
            sender_type="customer",
            message=message_text,
            attachment=request.FILES.get("attachment"),
            is_internal=False,
        )
        if lab_lead.status == "new":
            lab_lead.status = "contacted"
            lab_lead.save(update_fields=["status", "status_changed_at", "updated_at"])

        messages.success(request, "Your message has been sent to the lab.")
        return redirect(self._detail_url(enquiry, lab_lead.lab_id))

    @staticmethod
    def _detail_url(enquiry, lab_id):
        url = reverse("customer_lead_detail", kwargs={"enquiry_id": enquiry.pk})
        if lab_id:
            url = f"{url}?lab={lab_id}"
        return url


class ProcessCustomerDecisionView(LoginRequiredMixin, View):
    """Accept or decline a quotation for a specific LabLead."""

    def post(self, request, enquiry_id, *args, **kwargs):
        enquiry = get_object_or_404(Enquiry, pk=enquiry_id, user=request.user)
        action = request.POST.get("action")
        lab_id = request.POST.get("lab") or request.GET.get("lab")

        lab_lead = None
        if lab_id:
            lab_lead = LabLead.objects.filter(enquiry=enquiry, lab_id=lab_id).select_related(
                "quotation"
            ).first()
        if lab_lead is None:
            # Fallback: single lead
            leads = list(enquiry.lab_leads.select_related("quotation").all()[:2])
            if len(leads) == 1:
                lab_lead = leads[0]

        if lab_lead is None:
            messages.error(request, "Could not find the laboratory quotation.")
            return redirect("customer_lead_detail", enquiry_id=enquiry.pk)

        quotation = getattr(lab_lead, "quotation", None)

        if action == "accept":
            if quotation:
                quotation.mark_accepted()
            lab_lead.status = "won"
            lab_lead.save(update_fields=["status", "status_changed_at", "updated_at"])
            lab_lead.decline_competing_labs()
            messages.success(
                request,
                "Quotation accepted! Other labs on this request were declined. "
                "The lab will create an order to proceed.",
            )
        elif action == "reject":
            reason = request.POST.get("reason", "")
            if quotation:
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
            messages.info(request, "You have declined this quotation.")

        url = reverse("customer_lead_detail", kwargs={"enquiry_id": enquiry.pk})
        return redirect(f"{url}?lab={lab_lead.lab_id}")
