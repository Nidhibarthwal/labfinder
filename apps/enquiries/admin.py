from django.contrib import admin
from .models import (
    Dispute,
    OrderDocument,
    OrderMessage,
    LIMSJobOrder,
    Enquiry,
    EnquiryDiscussion,
    LabLead,
    LabReview,
    LabReviewCategoryRating,
    LIMSJobOrder,
    Quotation,
    ReviewCategory,
)
from import_export.admin import ImportExportModelAdmin



class LabLeadInline(admin.TabularInline):
    model = LabLead
    extra = 0
    show_change_link = True
    readonly_fields = ("created_at", "status_changed_at")
    fields = ("lab", "status", "assigned_to", "status_changed_at", "created_at")
    raw_id_fields = ("lab", "assigned_to")


class EnquiryDiscussionInline(admin.TabularInline):
    model = EnquiryDiscussion
    extra = 0
    readonly_fields = ("created_at",)
    fields = (
        "lab_lead",
        "sender_type",
        "sender",
        "lab",
        "message",
        "is_internal",
        "created_at",
    )
    raw_id_fields = ("lab_lead", "sender", "lab")


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product_name",
        "quotation_type",
        "lab",
        "lab_category",
        "contact_name",
        "email",
        "urgency",
        "created_at",
    )
    list_filter = ("quotation_type", "urgency", "lab_category", "created_at")
    search_fields = (
        "product_name",
        "email",
        "mobile_number",
        "contact_name",
        "company_name",
        "description",
    )
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("user", "lab", "lab_category")
    inlines = [LabLeadInline]
    date_hierarchy = "created_at"


@admin.register(LabLead)
class LabLeadAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "enquiry",
        "lab",
        "status",
        "assigned_to",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "enquiry__product_name",
        "lab__lab_name",
        "enquiry__contact_name",
        "enquiry__email",
    )
    readonly_fields = ("created_at", "updated_at", "status_changed_at")
    raw_id_fields = ("enquiry", "lab", "assigned_to")
    inlines = [EnquiryDiscussionInline]


@admin.register(EnquiryDiscussion)
class EnquiryDiscussionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "lab_lead",
        "sender_type",
        "sender",
        "lab",
        "is_internal",
        "created_at",
    )
    list_filter = ("sender_type", "is_internal", "created_at")
    search_fields = ("message", "enquiry__product_name")
    raw_id_fields = ("lab_lead", "enquiry", "sender", "lab")


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = (
        "quote_number",
        "lab_lead",
        "lab",
        "total_amount",
        "currency",
        "is_accepted",
        "created_at",
    )
    list_filter = ("is_accepted", "created_at")
    search_fields = ("quote_number", "enquiry__product_name")
    readonly_fields = (
        "quote_number",
        "created_at",
        "updated_at",
        "accepted_at",
        "rejected_at",
    )
    raw_id_fields = ("lab_lead", "enquiry", "lab", "created_by")




@admin.register(ReviewCategory)
class ReviewCategoryAdmin(ImportExportModelAdmin):
    list_display = ("id","name", "review_type", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")


class CategoryRatingInline(admin.TabularInline):
    model = LabReviewCategoryRating
    extra = 0


@admin.register(LabReview)
class LabReviewAdmin(admin.ModelAdmin):
    list_display = (
        "lab",
        "user",
        "overall_rating",
        "is_anonymous",
        "is_approved",
        "created_at",
    )
    list_filter = ("is_approved", "is_anonymous", "created_at")
    inlines = [CategoryRatingInline]
    raw_id_fields = ("lab", "user")





@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "raised_by_type", "status", "created_at")
    list_filter = ("status", "raised_by_type", "created_at")
    search_fields = ("reason", "order__job_number")
    raw_id_fields = ("order", "raised_by", "resolved_by")

@admin.register(LIMSJobOrder)
class LIMSJobOrderAdmin(admin.ModelAdmin):
    list_display = (
        "job_number", "sample_accession_id", "lab", "status",
        "customer", "sample_received_at", "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("job_number", "sample_accession_id", "enquiry__product_name")
    raw_id_fields = ("lab_lead", "enquiry", "lab", "customer", "completed_by")
