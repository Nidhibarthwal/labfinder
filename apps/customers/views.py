from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
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


def get_customer_dashboard_context(request):
    """
    Build context for Customer Portal (Dashboard, Inquiries & Quotes, Orders, Profile, Reviews, Settings).
    """
    user = request.user
    base = (
        Enquiry.objects.filter(user=user)
        .select_related("lab", "lab_category")
        .prefetch_related(
            Prefetch(
                "lab_leads",
                queryset=LabLead.objects.select_related("lab", "quotation", "lims_job").order_by(
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

    user_reviews = list(
        LabReview.objects.filter(user=user)
        .select_related("lab")
        .order_by("-created_at")
    )

    customer_orders_qs = (
        LIMSJobOrder.objects.filter(customer=user)
        .select_related("lab", "enquiry", "lab_lead", "lab_lead__quotation")
        .order_by("-created_at")
    )
    customer_orders = list(customer_orders_qs)

    customer_disputes = (
        Dispute.objects.filter(order__customer=user)
        .select_related("order", "order__lab")
        .order_by("-created_at")
    )

    order_filter = request.GET.get("order_status", "all")
    if order_filter == "payment":
        filtered_orders = [o for o in customer_orders if o.status in ("sample_received", "in_progress")]
    elif order_filter == "send_sample":
        filtered_orders = [o for o in customer_orders if o.status == "sample_received"]
    elif order_filter == "in_testing":
        filtered_orders = [o for o in customer_orders if o.status == "in_progress"]
    elif order_filter == "report_ready":
        filtered_orders = [o for o in customer_orders if o.status == "pending_customer_completion"]
    elif order_filter == "completed":
        filtered_orders = [o for o in customer_orders if o.status == "completed"]
    else:
        filtered_orders = customer_orders

    # 1. Stat Cards Metrics (Exact Figma match)
    pending_quotes_count = Quotation.objects.filter(
        enquiry__user=user, is_accepted=False, rejected_at__isnull=True
    ).count()
    if pending_quotes_count == 0:
        pending_quotes_count = max(0, sum(e.quoted_count for e in all_items))

    active_tests_count = sum(
        1 for o in customer_orders if o.status in ("sample_received", "in_progress", "pending_customer_completion")
    )
    active_tests_count_formatted = f"{active_tests_count:02d}"

    completed_reports_count = sum(1 for o in customer_orders if o.status == "completed")

    # Expenditure YTD
    expenditure_sum = (
        Quotation.objects.filter(enquiry__user=user, is_accepted=True)
        .aggregate(s=models.Sum("total_amount"))["s"]
        or Decimal("0")
    )
    if not expenditure_sum:
        for o in customer_orders:
            q = getattr(getattr(o, "lab_lead", None), "quotation", None)
            if q and q.total_amount:
                expenditure_sum += q.total_amount

    if expenditure_sum >= 100000:
        testing_expenditure_display = f"{float(expenditure_sum)/100000:.1f}L"
    elif expenditure_sum >= 1000:
        testing_expenditure_display = f"{float(expenditure_sum)/1000:.1f}k"
    else:
        testing_expenditure_display = f"{expenditure_sum:,.0f}"

    # testing_expenditure_display = f"₹{float(expenditure_sum):,.0f}"
    testing_expenditure_display = f"{float(expenditure_sum):,.0f}"
    # 2. Recent Activities Overview (Left column)
    recent_activities = []
    for enq in all_items:
        title = enq.product_name or f"Enquiry #{enq.pk}"
        if enq.quotation_type == "multiple_labs":
            sub = f"+{enq.lab_lead_count - 1} more" if enq.lab_lead_count > 1 else "Multi-lab request"
        elif enq.lab:
            sub = enq.lab.lab_name
        else:
            sub = "+1 more"

        status = enq.effective_status
        if status == "new":
            badge_label = "New"
            badge_type = "new"
        elif status == "contacted":
            badge_label = "Pending Lab Response"
            badge_type = "pending"
        elif status == "quoted":
            badge_label = "Quotes Received"
            badge_type = "quotes"
        elif status in ("won", "converted"):
            completed = False
            for ll in getattr(enq, "prefetched_lab_leads", []):
                if hasattr(ll, "lims_job") and ll.lims_job and ll.lims_job.status == "completed":
                    completed = True
                    break
            if completed:
                badge_label = "Report Delivered"
                badge_type = "delivered"
            else:
                badge_label = "In Progress"
                badge_type = "in_progress"
        elif status == "lost":
            badge_label = "Declined"
            badge_type = "lost"
        else:
            badge_label = enq.effective_status_display or "Inbound"
            badge_type = "default"

        time_str = "Recently"
        if enq.created_at:
            diff = timezone.now() - enq.created_at
            secs = int(diff.total_seconds())
            if secs < 3600:
                time_str = f"{max(1, secs // 60)}m ago"
            elif secs < 86400:
                time_str = f"{secs // 3600}h ago"
            else:
                time_str = f"{diff.days}d ago"

        detail_subtab = "quotes" if enq.effective_status == "quoted" else "overview"
        recent_activities.append({
            "title": title,
            "subtitle": sub,
            "badge_label": badge_label,
            "badge_type": badge_type,
            "time_ago": time_str,
            "url": f"{reverse('customer_lead_detail', kwargs={'enquiry_id': enq.pk})}?subtab={detail_subtab}",
            "created_at": enq.created_at,
        })

    recent_activities = recent_activities[:6]

    # 3. Action Required (Right column, last 5 days)
    actions_required = []
    pending_quotes = (
        Quotation.objects.filter(
            enquiry__user=user,
            is_accepted=False,
            rejected_at__isnull=True,
        )
        .select_related("lab", "enquiry", "lab_lead")
        .order_by("-created_at")[:5]
    )
    for q in pending_quotes:
        actions_required.append({
            "icon_type": "quote",
            "title": f"Review Quote: #{q.quote_number}",
            "description": f"{q.lab.lab_name} submitted a quote for ₹{q.total_amount:,.0f}. Approve to start testing.",
            "link_text": "Review & Approve",
            "url": f"{reverse('customer_lead_detail', kwargs={'enquiry_id': q.enquiry_id})}?subtab=quotes&lab={q.lab_id}",
        })

    for o in [o for o in customer_orders if o.status == "completed"][:3]:
        test_title = o.enquiry.product_name if o.enquiry else "Testing"
        actions_required.append({
            "icon_type": "download",
            "title": "Download Final Report",
            "description": f"Order #{o.job_number} ({test_title}) is complete.",
            "link_text": "Download PDF",
            "url": f"{reverse('order_detail', kwargs={'order_id': o.pk})}?subtab=documents",
        })

    for o in [o for o in customer_orders if o.status == "pending_customer_completion"][:3]:
        actions_required.append({
            "icon_type": "payment",
            "title": f"Confirm Completion: #{o.job_number}",
            "description": f"Testing for {o.enquiry.product_name} is finished. Confirm to release escrow.",
            "link_text": "Confirm & Release",
            "url": f"{reverse('order_detail', kwargs={'order_id': o.pk})}?subtab=payments",
        })

    # Optional preview mode to inspect exact Figma mockup state
    if request.GET.get("preview") == "1" or (request.GET.get("demo") == "1" and not recent_activities):
        pending_quotes_count = 246
        active_tests_count_formatted = "03"
        completed_reports_count = 10
        testing_expenditure_display = "42.5k"
        recent_activities = [
            {
                "title": "Food Nutrition & Label Analy...",
                "subtitle": "+1 more",
                "badge_label": "New",
                "badge_type": "new",
                "time_ago": "2h ago",
                "url": "#",
            },
            {
                "title": "Food Nutrition & Label Analy...",
                "subtitle": "+1 more",
                "badge_label": "Pending Lab Response",
                "badge_type": "pending",
                "time_ago": "2h ago",
                "url": "#",
            },
            {
                "title": "Food Nutrition & Label Analy...",
                "subtitle": "+1 more",
                "badge_label": "Report Delivered",
                "badge_type": "delivered",
                "time_ago": "2h ago",
                "url": "#",
            },
        ]
        actions_required = [
            {
                "icon_type": "quote",
                "title": "Review Quote: #Q-4092",
                "description": "Meridian submitted a quote for ₹2,800. Approve to start testing.",
                "link_text": "Review & Approve",
                "url": "#",
            },
            {
                "icon_type": "download",
                "title": "Download Final Report",
                "description": "Order #ORD-9921 (PVC Pipe Test) is complete.",
                "link_text": "Download PDF",
                "url": "#",
            },
        ]

    tab = request.GET.get("tab") or "dashboard"
    if tab in ("leads", "inquiries"):
        tab = "inquiries"
    if tab not in ("dashboard", "inquiries", "orders", "profile", "reviews", "settings"):
        tab = "dashboard"

    context = {
        "enquiries": filtered,
        "all_enquiries": all_items,
        "counts": counts,
        "active_status": status_filter,
        "user_reviews": user_reviews,
        "reviews_count": len(user_reviews),
        "orders": filtered_orders,
        "all_orders": customer_orders,
        "active_order_status": order_filter,
        "order_counts": {
            "all": len(customer_orders),
            "in_progress": sum(1 for o in customer_orders if o.status == "in_progress"),
            "sample_received": sum(1 for o in customer_orders if o.status == "sample_received"),
            "pending_customer_completion": sum(1 for o in customer_orders if o.status == "pending_customer_completion"),
            "completed": sum(1 for o in customer_orders if o.status == "completed"),
            "disputed": sum(1 for o in customer_orders if o.status == "disputed"),
            "action_required": sum(1 for o in customer_orders if o.status in ("pending_customer_completion", "sample_received")),
        },
        "disputes": customer_disputes,
        "dispute_counts": {
            "all": customer_disputes.count(),
            "open": customer_disputes.filter(status__in=["open", "under_review"]).count(),
            "resolved": customer_disputes.filter(status="resolved").count(),
        },
        "active_tab": tab,
        # Metrics for stat cards
        "pending_quotes_count": pending_quotes_count,
        "active_tests_count": active_tests_count,
        "active_tests_count_formatted": active_tests_count_formatted,
        "completed_reports_count": completed_reports_count,
        "testing_expenditure_display": testing_expenditure_display,
        "recent_activities": recent_activities,
        "actions_required": actions_required,
    }
    return context


def render_customer_dashboard(request):
    """Customer dashboard: enquiries owned by the logged-in user."""
    context = get_customer_dashboard_context(request)
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

        # Master navigation active tab
        context["active_tab"] = "inquiries"

        # Determine subtab inside card: overview, quotes, activity
        subtab = self.request.GET.get("subtab")
        if not subtab:
            if self.request.GET.get("compare") == "1":
                subtab = "quotes"
            else:
                subtab = "overview"
        context["subtab"] = subtab

        # Quotes list & count
        quoted_leads = [ll for ll in lab_leads if getattr(ll, "quotation", None)]
        context["quoted_leads"] = quoted_leads
        context["quotes_count"] = len(quoted_leads)

        # Timeline activities
        timeline = []
        for ll in quoted_leads:
            q = ll.quotation
            timeline.append({
                "title": f"Quote received from {ll.lab.lab_name}",
                "time": q.created_at,
                "type": "quote",
            })
        if enquiry.created_at:
            timeline.append({
                "title": f"Enquiry sent to {len(lab_leads) or 1} labs",
                "time": enquiry.created_at,
                "type": "enquiry",
            })
        timeline.sort(key=lambda x: x["time"] if x["time"] else timezone.now(), reverse=True)
        context["timeline"] = timeline

        # Parse test items for "Tests requested"
        tests = []
        if enquiry.product_name:
            tests.append({
                "name": enquiry.product_name,
                "samples": enquiry.quantity_or_sample_info or "2 samples",
            })
        if enquiry.preferred_services:
            for s in enquiry.preferred_services.split(","):
                s = s.strip()
                if s and s != enquiry.product_name:
                    tests.append({
                        "name": s,
                        "samples": enquiry.quantity_or_sample_info or "2 samples",
                    })
        if not tests:
            tests.append({
                "name": "Standard Lab Testing Analysis",
                "samples": "2 samples",
            })
        context["tests_requested"] = tests

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        enquiry = self.object
        action = request.POST.get("action")

        if action == "edit_enquiry":
            enquiry.product_name = request.POST.get("product_name", enquiry.product_name).strip() or enquiry.product_name
            enquiry.description = request.POST.get("description", enquiry.description).strip() or enquiry.description
            enquiry.quantity_or_sample_info = request.POST.get("quantity_or_sample_info", enquiry.quantity_or_sample_info).strip()
            enquiry.budget = request.POST.get("budget", enquiry.budget).strip()
            enquiry.urgency = request.POST.get("urgency", enquiry.urgency)
            if request.FILES.get("media"):
                enquiry.media = request.FILES.get("media")
            enquiry.save()
            messages.success(request, "Enquiry updated successfully.")
            return redirect(f"{reverse('customer_lead_detail', kwargs={'enquiry_id': enquiry.pk})}?subtab=overview")

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
