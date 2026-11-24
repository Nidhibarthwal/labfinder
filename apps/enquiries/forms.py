from decimal import Decimal
from django import forms

from .models import (
    Enquiry,
    EnquiryDiscussion,
    LabLead,
    LabReview,
    OrderDocument,
    OrderMessage,
    Quotation,
    LIMSJobOrder,
    Dispute,
)


class EnquiryForm(forms.ModelForm):
    product_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Enter product or material name (e.g. Drinking Water, Cement, Steel)",
            "required": "required",
        }),
    )
    description = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "placeholder": "Describe testing parameters, standards (IS/ISO/ASTM), scope or special requirements",
            "rows": 4,
            "required": "required",
        }),
    )
    company_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Company / Organisation name (optional)"}),
    )
    quantity_or_sample_info = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "No. of samples / quantity / sample size (optional)"}),
    )
    preferred_services = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Preferred services e.g. Water Testing"}),
    )
    urgency = forms.ChoiceField(
        choices=[("", "Select urgency")] + list(Enquiry._meta.get_field("urgency").choices),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    budget = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Approximate budget (optional)"}),
    )

    class Meta:
        model = Enquiry
        fields = [
            "product_name", "description", "company_name",
            "quantity_or_sample_info", "preferred_services", "urgency", "budget", "media", "mobile_number"
        ]


class GuestEnquiryForm(EnquiryForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your email address (mandatory)",
            "required": "required",
        }),
    )
    mobile_number = forms.CharField(
        required=False, max_length=20,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Contact number (optional)", "inputmode": "tel"}),
    )
    contact_name = forms.CharField(
        required=False, max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Your full name"}),
    )

    class Meta(EnquiryForm.Meta):
        fields = EnquiryForm.Meta.fields + ["email", "mobile_number", "contact_name"]


class LeadStatusForm(forms.ModelForm):
    class Meta:
        model = LabLead
        fields = ["status"]
        widgets = {"status": forms.Select(attrs={"class": "form-select"})}


class EnquiryDiscussionForm(forms.ModelForm):
    class Meta:
        model = EnquiryDiscussion
        fields = ["message", "attachment", "is_internal"]
        widgets = {
            "message": forms.Textarea(attrs={
                "class": "form-control", "rows": 3,
                "placeholder": "Type your message or technical follow-up...",
                "required": "required",
            }),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
            "is_internal": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class QuotationForm(forms.ModelForm):
    total_amount = forms.DecimalField(
        required=True,
        min_value=Decimal("0.01"),
        error_messages={
            "required": "Please enter the total quotation amount.",
            "min_value": "Quotation amount must be greater than 0.",
        },
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. 5000.00",
            "step": "0.01",
            "min": "0.01",
            "required": "required",
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.pk:
            self.initial["total_amount"] = None

    class Meta:
        model = Quotation
        fields = [
            "total_amount",
            "estimated_turnaround_days",
            "validity_days",
            "scope_notes",
            "terms",
            "notes",
        ]
        widgets = {
            "estimated_turnaround_days": forms.NumberInput(attrs={
                "class": "form-control", "min": "1",
                "placeholder": "Days to complete testing after sample receipt",
            }),
            "validity_days": forms.NumberInput(attrs={
                "class": "form-control", "min": "1",
                "placeholder": "Days this price offer remains valid",
            }),
            "scope_notes": forms.Textarea(attrs={
                "class": "form-control", "rows": 3,
                "placeholder": "Included tests, methods, sample requirements...",
            }),
            "terms": forms.Textarea(attrs={
                "class": "form-control", "rows": 2,
                "placeholder": "Payment terms, cancellation policy...",
            }),
            "notes": forms.Textarea(attrs={
                "class": "form-control", "rows": 2,
                "placeholder": "Any additional notes...",
            }),
        }


class AcceptQuotationForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        label="I accept the quotation terms and pricing",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class RejectQuotationForm(forms.Form):
    reason = forms.CharField(
        required=False, max_length=255,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional reason for declining"}),
    )


class OrderMessageForm(forms.ModelForm):
    class Meta:
        model = OrderMessage
        fields = ["message", "attachment", "is_internal"]
        widgets = {
            "message": forms.Textarea(attrs={
                "class": "form-control", "rows": 3,
                "placeholder": "Message about this order...",
                "required": "required",
            }),
            "attachment": forms.FileInput(attrs={"class": "form-control"}),
            "is_internal": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class OrderInvoiceForm(forms.ModelForm):
    class Meta:
        model = LIMSJobOrder
        fields = ["invoice"]
        widgets = {"invoice": forms.FileInput(attrs={"class": "form-control"})}


class OrderDocumentForm(forms.ModelForm):
    class Meta:
        model = OrderDocument
        fields = ["title", "file"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Document title"}),
            "file": forms.FileInput(attrs={"class": "form-control"}),
        }


class DisputeForm(forms.ModelForm):
    class Meta:
        model = Dispute
        fields = ["reason"]
        widgets = {
            "reason": forms.Textarea(attrs={
                "class": "form-control", "rows": 4,
                "placeholder": "Describe the issue clearly...",
                "required": "required",
            }),
        }


class LabReviewForm(forms.ModelForm):
    class Meta:
        model = LabReview
        fields = ["title", "summary", "is_anonymous"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Headline for your review"}),
            "summary": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Share your experience..."}),
            "is_anonymous": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class LabReplyForm(forms.Form):
    review_id = forms.IntegerField(widget=forms.HiddenInput())
    reply_message = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Write your reply..."})
    )
