from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.labs.models import Branch, LabCategory


QUOTATION_TYPE_CHOICES = [
    ("selected_lab", "Selected laboratory only"),
    ("multiple_labs", "Selected and other relevant laboratories"),
]

ENQUIRY_STATUS_CHOICES = [
    ("new", "Inbound Enquiry"),
    ("contacted", "Qualification & Feasibility"),
    ("not_qualified", "Not Qualified"),
    ("quoted", "Quotation Sent"),
    ("won", "Won (Customer Approved)"),
    ("lost", "Lost / Declined"),
    ("converted", "Sample Received & Accessioned"),
]

SENDER_TYPE_CHOICES = [
    ("customer", "Customer"),
    ("lab", "Lab Officer"),
]

URGENCY_CHOICES = [
    ("immediate", "Immediately (Within 7 days)"),
    ("15_days", "15 Days"),
    ("30_days", "30 Days"),
    ("flexible", "Flexible / Planning Phase"),
    # legacy values retained for existing rows
    ("normal", "Normal"),
    ("urgent", "Urgent"),
    ("critical", "Critical / Express"),
]

ORDER_STATUS_CHOICES = [
    ("sample_received", "Sample Received"), # Payment Pending
    ("in_progress", "In Testing"),
    ("pending_customer_completion", "Awaiting Customer Confirmation"),
    ("report_ready", "Report Ready"),
    ("completed", "Completed"),
    ("disputed", "In Dispute"),
    ("cancelled", "Cancelled"),
]

ORDER_PAYMENT_STATUS_CHOICES = [
    ("not_paid", "Not Paid"),
    ("partially_paid", "Partially Paid"),
    ("paid", "Paid in full"),
]

DISPUTE_STATUS_CHOICES = [
    ("open", "Open"),
    ("under_review", "Under LabFinder Review"),
    ("resolved", "Resolved"),
    ("closed", "Closed"),
]

DISPUTE_RAISED_BY = [
    ("customer", "Customer"),
    ("lab", "Laboratory"),
]


class Enquiry(models.Model):
    """
    Customer test request. Visibility:
      - selected_lab  → only `lab`
      - multiple_labs → every Branch with the same `lab_category`
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="lab_enquiries",
    )
    lab = models.ForeignKey(
        Branch, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="originated_enquiries",
    )
    lab_category = models.ForeignKey(
        LabCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="enquiries",
    )
    quotation_type = models.CharField(
        max_length=20, choices=QUOTATION_TYPE_CHOICES, default="selected_lab"
    )
    product_name = models.CharField(max_length=255)
    description = models.TextField()
    company_name = models.CharField(max_length=255, blank=True)
    budget = models.CharField(max_length=100, blank=True)
    quantity_or_sample_info = models.CharField(max_length=255, blank=True)
    preferred_services = models.CharField(max_length=255, blank=True)
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default="normal")
    email = models.EmailField(blank=True)
    mobile_number = models.CharField(max_length=20, blank=True)
    contact_name = models.CharField(max_length=255, blank=True)
    media = models.FileField(upload_to="enquiries/media/%Y/%m/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Enquiries"
        indexes = [
            models.Index(fields=["quotation_type", "-created_at"]),
            models.Index(fields=["lab_category", "-created_at"]),
        ]

    def __str__(self):
        return f"#{self.pk} {self.product_name} – {self.contact_name or self.email}"

    def is_owned_by(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        return self.user_id == user.pk

    def save(self, *args, **kwargs):
        if self.lab_id and not self.lab_category_id:
            cat_id = getattr(self.lab, "lab_category_id", None)
            if cat_id:
                self.lab_category_id = cat_id
        super().save(*args, **kwargs)

    def ensure_lab_lead(self, lab: Branch) -> "LabLead":
        """
        Get or create the per-lab participation record.
        Called when a lab first opens / messages / quotes on this enquiry.
        """
        lead, _ = LabLead.objects.get_or_create(
            enquiry=self, lab=lab, defaults={"status": "new"}
        )
        return lead

    @classmethod
    def visible_to_branch_qs(cls, branch: Branch):
        """
        Enquiries a given lab should see on its dashboard.
          - selected_lab  → enquiry.lab == branch
          - multiple_labs → same lab_category (and category is set)
        """
        if not branch:
            return cls.objects.none()
        selected = Q(quotation_type="selected_lab", lab=branch)
        multi = Q(quotation_type="multiple_labs")
        if branch.lab_category_id:
            multi &= Q(lab_category_id=branch.lab_category_id)
        else:
            multi &= Q(lab=branch)
        return cls.objects.filter(selected | multi).distinct()

    @property
    def display_name(self):
        if self.user:
            full_name = self.user.get_full_name()
            return full_name if full_name and full_name.strip() else self.user.email
        return "Anonymous User"

class LabLead(models.Model):
    """
    One laboratory's participation on a customer enquiry.
    Owns its own pipeline status, discussion thread, quotation and LIMS job.
    """

    enquiry = models.ForeignKey(
        Enquiry, on_delete=models.CASCADE, related_name="lab_leads"
    )
    lab = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="participating_leads"
    )
    status = models.CharField(
        max_length=50, choices=ENQUIRY_STATUS_CHOICES, default="new", db_index=True
    )
    status_changed_at = models.DateTimeField(null=True, blank=True)
    lost_reason = models.CharField(max_length=255, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="assigned_lab_leads",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("enquiry", "lab")
        verbose_name = "Lab Lead"
        verbose_name_plural = "Lab Leads"
        indexes = [models.Index(fields=["lab", "status", "-created_at"])]

    def __str__(self):
        lab_name = getattr(self.lab, "lab_name", None) or str(self.lab_id)
        return f"Lead #{self.enquiry_id} @ {lab_name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old = LabLead.objects.get(pk=self.pk)
                if old.status != self.status:
                    self.status_changed_at = timezone.now()
            except LabLead.DoesNotExist:
                pass
        elif not self.status_changed_at:
            self.status_changed_at = timezone.now()
        super().save(*args, **kwargs)

    def is_lab_staff(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "lab_user", None) and user.lab_user.pk == self.lab_id:
            return True
        if self.lab.contact_email and user.email:
            return self.lab.contact_email.lower() == user.email.lower()
        return False

    def can_view(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        if self.enquiry.is_owned_by(user):
            return True
        return self.is_lab_staff(user)

    def can_manage_as_lab(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        return self.is_lab_staff(user)

    def decline_competing_labs(self, reason: str = "Another laboratory was selected by the customer"):
        others = LabLead.objects.filter(enquiry_id=self.enquiry_id).exclude(pk=self.pk)
        for other in others:
            if other.status in ("lost", "converted", "won"):
                continue
            other.status = "lost"
            other.lost_reason = reason[:255]
            other.save(update_fields=["status", "status_changed_at", "lost_reason", "updated_at"])
            q = getattr(other, "quotation", None)
            if q and not q.rejected_at:
                q.mark_rejected(reason)


class EnquiryDiscussion(models.Model):
    """
    Message in a per-lab conversation thread.
    Always tied to a LabLead so lab A never sees lab B's chat with the customer.
    """

    lab_lead = models.ForeignKey(
        LabLead, on_delete=models.CASCADE, related_name="discussions"
    )
    enquiry = models.ForeignKey(
        Enquiry, on_delete=models.CASCADE, related_name="all_discussions"
    )
    lab = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="enquiry_messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    sender_type = models.CharField(
        max_length=20, choices=SENDER_TYPE_CHOICES, default="customer"
    )
    message = models.TextField()
    attachment = models.FileField(
        upload_to="enquiry_discussions/%Y/%m/", blank=True, null=True
    )
    is_internal = models.BooleanField(
        default=False,
        help_text="Internal lab note – not visible to customer.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Enquiry Message"
        verbose_name_plural = "Enquiry Messages"

    def __str__(self):
        return f"Msg by {self.sender_type} on LabLead #{self.lab_lead_id}"

    def save(self, *args, **kwargs):
        if self.lab_lead_id:
            if not self.enquiry_id:
                self.enquiry_id = self.lab_lead.enquiry_id
            if not self.lab_id:
                self.lab_id = self.lab_lead.lab_id
        super().save(*args, **kwargs)


class Quotation(models.Model):
    """Official quotation issued by one laboratory against its LabLead."""

    lab_lead = models.OneToOneField(
        LabLead, on_delete=models.CASCADE, related_name="quotation"
    )
    enquiry = models.ForeignKey(
        Enquiry, on_delete=models.CASCADE, related_name="quotations"
    )
    lab = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="sent_quotations"
    )
    quote_number = models.CharField(max_length=50, unique=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, default="INR")
    estimated_turnaround_days = models.PositiveIntegerField(default=7)
    validity_days = models.PositiveIntegerField(
        default=15,
        help_text="Number of days this quotation remains valid.",
    )
    scope_notes = models.TextField(
        blank=True,
        help_text="Included tests, methods, sample requirements, exclusions.",
    )
    terms = models.TextField(
        blank=True,
        help_text="Payment terms, cancellation policy, etc.",
    )
    notes = models.TextField(blank=True)
    is_accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="created_quotations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Quote #{self.quote_number} – {self.currency} {self.total_amount}"

    def save(self, *args, **kwargs):
        if self.lab_lead_id:
            if not self.enquiry_id:
                self.enquiry_id = self.lab_lead.enquiry_id
            if not self.lab_id:
                self.lab_id = self.lab_lead.lab_id
        super().save(*args, **kwargs)

    def mark_accepted(self):
        self.is_accepted = True
        self.accepted_at = timezone.now()
        self.rejected_at = None
        self.rejection_reason = ""
        self.save(update_fields=[
            "is_accepted", "accepted_at", "rejected_at", "rejection_reason", "updated_at"
        ])

    def mark_rejected(self, reason: str = ""):
        self.is_accepted = False
        self.rejected_at = timezone.now()
        self.rejection_reason = (reason or "")[:255]
        self.save(update_fields=[
            "is_accepted", "rejected_at", "rejection_reason", "updated_at"
        ])


class LIMSJobOrder(models.Model):
    """
    Single post-win order/job. Created when lab accepts a won lead.
    Holds accession, invoice, completion, chat, documents, disputes.
    """
    lab_lead = models.OneToOneField(
        LabLead, on_delete=models.CASCADE, related_name="lims_job"
    )
    enquiry = models.ForeignKey(
        Enquiry, on_delete=models.CASCADE, related_name="lims_jobs"
    )
    lab = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="lims_job_orders",
        null=True, blank=True,
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="lims_job_orders",
    )
    job_number = models.CharField(max_length=50, unique=True)
    sample_accession_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=40, choices=ORDER_STATUS_CHOICES,
        default="in_progress", db_index=True,
    )
    payment_status = models.CharField(
            max_length=40, choices=ORDER_PAYMENT_STATUS_CHOICES,
            default="not_paid", db_index=True,
    )
    sample_received_at = models.DateTimeField(null=True, blank=True)
    invoice = models.FileField(
        upload_to="orders/invoices/%Y/%m/", blank=True, null=True
    )
    invoice_uploaded_at = models.DateTimeField(null=True, blank=True)
    completion_requested_by = models.CharField(max_length=20, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="completed_lims_jobs",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "LIMS Job / Order"
        verbose_name_plural = "LIMS Jobs / Orders"

    def __str__(self):
        return f"Job #{self.job_number} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if self.lab_lead_id:
            if not self.enquiry_id:
                self.enquiry_id = self.lab_lead.enquiry_id
            if not self.lab_id:
                self.lab_id = self.lab_lead.lab_id
            if not self.customer_id and self.lab_lead.enquiry.user_id:
                self.customer_id = self.lab_lead.enquiry.user_id
        super().save(*args, **kwargs)

    def is_participant(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        if self.customer_id == user.pk:
            return True
        return self.lab_lead.is_lab_staff(user)


class OrderMessage(models.Model):
    order = models.ForeignKey(
        LIMSJobOrder, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    sender_type = models.CharField(
        max_length=20, choices=SENDER_TYPE_CHOICES, default="customer"
    )
    message = models.TextField()
    attachment = models.FileField(
        upload_to="orders/messages/%Y/%m/", blank=True, null=True
    )
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class OrderDocument(models.Model):
    order = models.ForeignKey(
        LIMSJobOrder, on_delete=models.CASCADE, related_name="documents"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    title = models.CharField(max_length=255, blank=True)
    file = models.FileField(upload_to="orders/documents/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Dispute(models.Model):
    order = models.ForeignKey(
        LIMSJobOrder, on_delete=models.CASCADE, related_name="disputes"
    )
    raised_by_type = models.CharField(max_length=20, choices=DISPUTE_RAISED_BY)
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20, choices=DISPUTE_STATUS_CHOICES, default="open", db_index=True
    )
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="resolved_disputes",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Dispute #{self.pk} on {self.order.job_number} ({self.get_status_display()})"


class ReviewCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    review_type = models.CharField(
        max_length=50,
        choices=(("positive", "Positive"), ("negative", "Negative")),
        default="positive",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "Review Categories"

    def __str__(self):
        return self.name


class LabReview(models.Model):
    lab = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lab_reviews"
    )
    title = models.CharField(max_length=255)
    summary = models.TextField()
    overall_rating = models.DecimalField(max_digits=3, decimal_places=1, default=5.0)
    is_anonymous = models.BooleanField(
        default=False, help_text="Hide user identity publicly"
    )
    lab_reply = models.TextField(blank=True, null=True)
    replied_at = models.DateTimeField(blank=True, null=True)
    is_approved = models.BooleanField(default=True)
    is_hidden_by_lab = models.BooleanField(
        default=False, db_index=True, help_text="Hidden by lab from public profile"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def calculate_overall_rating(self):
        ratings = self.category_ratings.all()
        if ratings.exists():
            avg = sum(r.rating for r in ratings) / len(ratings)
            self.overall_rating = round(avg, 1)
            self.save(update_fields=["overall_rating", "updated_at"])

    @property
    def display_name(self):
        if self.is_anonymous:
            return "Anonymous User"
        full_name = self.user.get_full_name()
        return full_name if full_name and full_name.strip() else self.user.email

    # def __str__(self):
    #     lab_name = getattr(self.lab, "lab_name", None) or str(self.lab_id)
    #     return f"{self.display_name} – {self.overall_rating}★ ({lab_name})"


class LabReviewCategoryRating(models.Model):
    review = models.ForeignKey(
        LabReview, on_delete=models.CASCADE, related_name="category_ratings"
    )
    category = models.ForeignKey(ReviewCategory, on_delete=models.CASCADE)
    rating = models.DecimalField(
        max_digits=3, decimal_places=1,
        validators=[MinValueValidator(1.0), MaxValueValidator(5.0)],
    )

    class Meta:
        unique_together = ("review", "category")

    # def __str__(self):
    #     return f"{self.category.name}: {self.rating}★"

