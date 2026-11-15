import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

class WorkflowState(models.TextChoices):
    PENDING = 'PENDING', _('Pending')
    VALIDATING_URL = 'VALIDATING_URL', _('Validating URL')
    DISCOVERING = 'DISCOVERING', _('Discovering')
    PLANNING = 'PLANNING', _('Planning')
    SELECTING_PAGES = 'SELECTING_PAGES', _('Selecting Pages')
    FETCHING = 'FETCHING', _('Fetching')
    EXTRACTING = 'EXTRACTING', _('Extracting')
    CLASSIFYING = 'CLASSIFYING', _('Classifying')
    ANALYSING = 'ANALYSING', _('Analysing')
    VALIDATING = 'VALIDATING', _('Validating')
    AGGREGATING = 'AGGREGATING', _('Aggregating')
    FINAL_VALIDATION = 'FINAL_VALIDATION', _('Final Validation')
    COMPLETED = 'COMPLETED', _('Completed')
    FAILED = 'FAILED', _('Failed')

class PageType(models.TextChoices):
    ABOUT = 'ABOUT', _('About')
    COMPANY = 'COMPANY', _('Company')
    PRODUCT = 'PRODUCT', _('Product')
    PRODUCT_DETAIL = 'PRODUCT_DETAIL', _('Product Detail')
    SERVICE = 'SERVICE', _('Service')
    SERVICE_DETAIL = 'SERVICE_DETAIL', _('Service Detail')
    SOLUTION = 'SOLUTION', _('Solution')
    INDUSTRY = 'INDUSTRY', _('Industry')
    LEADERSHIP = 'LEADERSHIP', _('Leadership')
    TEAM = 'TEAM', _('Team')
    CUSTOMER = 'CUSTOMER', _('Customer')
    CASE_STUDY = 'CASE_STUDY', _('Case Study')
    PARTNER = 'PARTNER', _('Partner')
    TECHNOLOGY = 'TECHNOLOGY', _('Technology')
    CAREERS = 'CAREERS', _('Careers')
    CONTACT = 'CONTACT', _('Contact')
    PRESS = 'PRESS', _('Press')
    NEWS = 'NEWS', _('News')
    RESOURCE = 'RESOURCE', _('Resource')
    BLOG = 'BLOG', _('Blog')
    OTHER = 'OTHER', _('Other')

class Website(models.Model):
    domain = models.CharField(max_length=255, unique=True, db_index=True)
    root_url = models.URLField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['domain']),
        ]

    def __str__(self):
        return self.domain

class AnalysisJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='jobs')
    objective = models.CharField(max_length=100, default='company_intelligence', db_index=True)
    status = models.CharField(
        max_length=30,
        choices=WorkflowState.choices,
        default=WorkflowState.PENDING,
        db_index=True
    )
    error_code = models.CharField(max_length=100, null=True, blank=True)
    error_detail = models.TextField(null=True, blank=True)
    budget_usage = models.JSONField(default=dict, blank=True)
    options = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Job {self.id} - {self.website.domain} ({self.status})"

class Page(models.Model):
    website = models.ForeignKey(Website, on_delete=models.CASCADE, related_name='pages')
    url = models.TextField()
    normalized_url = models.TextField(db_index=True)
    page_type = models.CharField(
        max_length=30,
        choices=PageType.choices,
        default=PageType.OTHER,
        db_index=True
    )
    title = models.CharField(max_length=500, blank=True)
    http_status = models.IntegerField(null=True, blank=True)
    content_hash = models.CharField(max_length=64, db_index=True, blank=True)
    clean_text = models.TextField(blank=True)
    quality_score = models.FloatField(default=0.0)
    fetch_method = models.CharField(max_length=20, default='HTTP')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['website', 'normalized_url'], name='unique_website_page')
        ]
        indexes = [
            models.Index(fields=['page_type']),
            models.Index(fields=['content_hash']),
        ]

    def __str__(self):
        return f"{self.page_type}: {self.url[:60]}"

class PageLink(models.Model):
    source_page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='outgoing_links')
    target_url = models.TextField()
    anchor_text = models.CharField(max_length=500, blank=True)
    is_internal = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source_page_id} -> {self.target_url[:50]}"

class PageAnalysis(models.Model):
    job = models.ForeignKey(AnalysisJob, on_delete=models.CASCADE, related_name='page_analyses')
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='analyses')
    summary = models.TextField(blank=True)
    raw_output = models.JSONField(default=dict, blank=True)
    model_used = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Analysis {self.id} for Page {self.page_id}"

class Evidence(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='evidence_items')
    quote = models.TextField()
    char_start = models.IntegerField(default=-1)
    char_end = models.IntegerField(default=-1)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Evidence [{self.char_start}:{self.char_end}] verified={self.verified}"

class Fact(models.Model):
    job = models.ForeignKey(AnalysisJob, on_delete=models.CASCADE, related_name='facts')
    evidence = models.ForeignKey(Evidence, on_delete=models.SET_NULL, null=True, blank=True, related_name='facts')
    category = models.CharField(max_length=100, db_index=True)
    field = models.CharField(max_length=100)
    value = models.TextField()
    confidence = models.FloatField(default=1.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Fact [{self.category}.{self.field}]: {self.value[:40]}"

class AnalysisResult(models.Model):
    job = models.OneToOneField(AnalysisJob, on_delete=models.CASCADE, related_name='result')
    summary_markdown = models.TextField(blank=True)
    structured_data = models.JSONField(default=dict, blank=True)
    conflicts = models.JSONField(default=list, blank=True)
    missing_fields = models.JSONField(default=list, blank=True)
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Result for Job {self.job_id}"
