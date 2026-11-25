import uuid
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.samples_configurations.models import Category
from apps.utility.models import State, District


class SEOTemplate(models.Model):
    """
    Template patterns for bulk-generating meta titles, descriptions, headings,
    intro content, and structured FAQ schemas.
    """
    PAGE_TYPE_CHOICES = (
        ("category_city", "Category + City (e.g. Top 5 Food Testing Labs in Delhi)"),
        ("category_state", "Category + State (e.g. Top Food Testing Labs in Maharashtra)"),
        ("category_region", "Category + Region (e.g. Top Food Testing Labs in Delhi-NCR)"),
        ("city_only", "City Only (e.g. Top Testing Labs in Delhi)"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page_type = models.CharField(
        max_length=50,
        choices=PAGE_TYPE_CHOICES,
        unique=True,
        help_text="Target page type for this template"
    )
    title_pattern = models.CharField(
        max_length=255,
        default="Top {count} {category} Labs in {location} (NABL Accredited) | LabFinder",
        help_text="Variables: {count}, {category}, {location}"
    )
    meta_desc_pattern = models.TextField(
        default="Find and compare top {count} {category} testing laboratories in {location}. View NABL & BIS accreditations, testing turnaround times, sample parameters, and request instant quotation on LabFinder.",
        help_text="Variables: {count}, {category}, {location}"
    )
    meta_keywords_pattern = models.CharField(
        max_length=255,
        default="{category} testing labs in {location}, top {category} labs {location}, NABL accredited {category} lab {location}",
        help_text="Variables: {category}, {location}"
    )
    h1_pattern = models.CharField(
        max_length=255,
        default="Top {count} {category_phrase} Laboratories in {location}",
        help_text="Variables: {count}, {category}, {category_phrase}, {location}"
    )
    intro_pattern = models.TextField(
        default="Looking for certified {category_phrase} laboratories in {location}? Browse our verified directory of accredited laboratories equipped with advanced testing instrumentation, experienced scientific personnel, and quick turnaround times. Request direct quotations or compare multiple responses effortlessly.",
        help_text="Variables: {count}, {category}, {category_phrase}, {location}"
    )
    faq_pattern = models.JSONField(
        default=list,
        blank=True,
        help_text="List of JSON objects with 'question' and 'answer' patterns using {category}, {location}, {count}."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "SEO Template"
        verbose_name_plural = "SEO Templates"
        ordering = ["page_type"]

    def __str__(self):
        return dict(self.PAGE_TYPE_CHOICES).get(self.page_type, self.page_type)

    def get_default_faq_patterns(self):
        if self.faq_pattern:
            return self.faq_pattern
        return [
            {
                "question": "Which are the best {category} testing laboratories in {location}?",
                "answer": "LabFinder curates the top verified {category} testing laboratories in {location} based on NABL/BIS accreditation, testing facility scope, customer ratings, and turnaround compliance."
            },
            {
                "question": "How can I request a quotation for {category} testing in {location}?",
                "answer": "You can click 'Request Quote' directly on any laboratory listed above, or submit a single enquiry to receive competitive quotations from multiple accredited labs in {location}."
            },
            {
                "question": "Are the {category} laboratories in {location} NABL accredited?",
                "answer": "Yes, listed laboratories feature accreditation details, scope certificates, and valid compliance records verified against NABL and BIS standards."
            }
        ]


class SEOLandingPage(models.Model):
    """
    Dedicated database table storing every programmatic SEO landing page.
    Indexed, searchable, and manageable in bulk.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    page_type = models.CharField(max_length=50, default="category_city", db_index=True)

    # Core relationship hooks according to project tables
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="seo_landing_pages",
        null=True,
        blank=True,
        help_text="Target category from apps.samples_configurations.models.Category"
    )
    group_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Target group from Branch.group_name"
    )
    city = models.CharField(max_length=255, db_index=True, help_text="e.g. Delhi, Ghaziabad, Mumbai")
    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        related_name="seo_landing_pages",
        null=True,
        blank=True
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        related_name="seo_landing_pages",
        null=True,
        blank=True
    )
    region = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. northern, Delhi-NCR")

    # SEO Meta Tags
    meta_title = models.CharField(max_length=255)
    meta_description = models.TextField()
    meta_keywords = models.CharField(max_length=255, blank=True)
    h1_heading = models.CharField(max_length=255)
    intro_content = models.TextField(blank=True)

    # Rich Google JSON-LD FAQ schema
    faq_schema = models.JSONField(
        default=list,
        blank=True,
        help_text="List of {question, answer} dictionaries rendered as JSON-LD FAQPage for Google"
    )

    # Metric tracking & publication status
    lab_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of active verified laboratories matching this combination"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="If False, page is 404 or excluded from sitemap to prevent thin-content penalties"
    )
    is_customized = models.BooleanField(
        default=False,
        help_text="Set to True if manually edited by marketing/SEO team so automated bulk re-generation won't overwrite custom copy."
    )

    # Audit timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "SEO Landing Page"
        verbose_name_plural = "SEO Landing Pages"
        ordering = ["-lab_count", "city", "slug"]
        indexes = [
            models.Index(fields=["category", "city"]),
            models.Index(fields=["group_name", "city"]),
            models.Index(fields=["is_active", "lab_count"]),
            models.Index(fields=["page_type", "is_active"]),
        ]

    @property
    def display_category(self):
        if self.category_id:
            return self.category.name
        return self.group_name or "Testing"

    def __str__(self):
        return f"{self.h1_heading} ({self.lab_count} labs)"

    def get_absolute_url(self):
        return reverse("seo_landing_page", kwargs={"slug": self.slug})
