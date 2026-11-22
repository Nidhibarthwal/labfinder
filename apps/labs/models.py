import uuid
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.labs.services import validate_lab_data
from apps.utility.models import (
    GST, TEXT_REGEX, Brand, Discipline, EquipmentType, Trackable, Country, State, District, Department, Role, Tag, TagType,
    AccreditationMaster, TestingType, Profile, Unit, pincode_regex
)
from django.core.validators import FileExtensionValidator
import os
from apps.samples_configurations.models import Category, SubCategory, ParameterQualitativeValue, ParameterRangeValue, SampleClauseCategory, SampleClauseSubCategory, ServiceCategory, TestMethod
from django.utils.text import slugify


PRICING_METHOD = (("standard", 'Standard Wise'), ("parameter", 'Parameter Wise'))
UOM_VALUE_TYPE = (
    ('1', 'Greater than'), ('2', 'Not more than'), ('3', 'Not less than'),
    ('4', 'Maximum'), ('5', 'Minimum'), ('6', 'In Range'), ('7', 'Not Applicable'),
)

User = get_user_model()

REGIONS_CHOICES = (
    ("eastern","Eastern"),
    ("southern","Southern"),
    ("western","Western"),
    ("central","Central"),
    ("northern","Northern"),
    ("NER","North Eastern"),
    ("NWR","North Western"),
    ("NC","North Central"),
    ("HQ","Headquarter")  
)

DISCIPLINES_CHOICES = (('mechanical', 'Mechanical'), ('chemical', 'Chemical'), ('microbiological', 'Microbiological'))
ORGANIZATION_CHOICES = (('proprietorship', 'Proprietorship'), ('partnership', 'Partnership'),
                         ('pvt_ltd', 'Private Limited'), ('public_ltd', 'Public Limited'))
EMPLOYMENT_CHOICES = (('permanent', 'Permanent'), ('contract', 'Contract'))
MANPOWER_TYPE_CHOICES = (('technical', 'Technical'), ('administrative', 'Administrative'))
MANPOWER_STATUS = ((0, 'Pending'), (1, 'Approved'), (2, 'Rejected'))
PROFILE_TIER_CHOICES = (('free', 'Free'), ('silver', 'Silver'), ('gold', 'Gold'), ('platinum', 'Platinum'))

# --- New choices for Lab Hierarchy (LabFinder_360_Updated.docx, section 9) ---
LAB_TYPE_CHOICES = (
    ('organization', 'Organization Lab'),
    ('branch', 'Branch Lab'),
)
APPROVAL_STATUS_CHOICES = (
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
)


PRICING_METHOD = (("standard", 'Standard Wise'), ("parameter", 'Parameter Wise'))
UOM_VALUE_TYPE = (
    ('1', 'Greater than'), ('2', 'Not more than'), ('3', 'Not less than'),
    ('4', 'Maximum'), ('5', 'Minimum'), ('6', 'In Range'), ('7', 'Not Applicable'),
)



class LegalIdProofDocType(models.Model):
    type_name = models.CharField(max_length=255, blank=True, null=True, unique=True)

    class Meta:
        default_permissions = ()

    def __str__(self):
        return str(self.type_name)


class LabAddressProofDocType(models.Model):
    type_name = models.CharField(max_length=255, blank=True, null=True, unique=True)

    class Meta:
        default_permissions = ()

    def __str__(self):
        return str(self.type_name)

SOURCE_CHOICES = (
        ("nabl", "NABL"),
        ("bis", "BIS"),
        ("fssai", "FSSAI"),
        ("fddi", "FDDI"),
        ("cipet", "CIPET"),
        ("iocl", "IOCL"),
        ("vista", "Vista"),
        ("crawler", "Crawler"),
        ("other", "Other"),
    )


STATUS_CHOICES = (
    ('unclaimed','Unclaimed'),
    ('claimed','Claimed'),
    ('reviewed','Reviewed'),
    ('approved','Approved'),
    ('rejected','Rejected'),
    ('deleted','Deleted')
)


class LabCategory(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # 1. UI Form Definition & Validation Rules (JSON Schema standard)
    dynamic_schema = models.JSONField(
        default=dict,
        help_text="JSON Schema defining dynamic form fields, validation rules, and UI layout."
    )

    # 2. Crawler Configuration
    crawler_config = models.JSONField(
        default=dict,
        help_text="Target URL paths and selector extraction rules per field key."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Lab Categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class LabCategoryField(models.Model):
    FIELD_TYPES = [
        ("text", "Text"),
        ("textarea", "Textarea"),
        ("number", "Whole Number"),
        ("decimal", "Decimal"),
        ("boolean", "Yes/No"),
        ("date", "Date"),
        ("time", "Time"),
        ("email", "Email"),
        ("url", "URL"),
        ("select", "Dropdown"),
        ("multiselect", "Multiple Selection"),
    ]

    category = models.ForeignKey(
        LabCategory,
        on_delete=models.CASCADE,
        related_name="fields",
    )

    field_key = models.SlugField(max_length=100)
    label = models.CharField(max_length=200)
    field_type = models.CharField(
        max_length=20,
        choices=FIELD_TYPES,
    )

    help_text = models.CharField(max_length=300, blank=True)
    placeholder = models.CharField(max_length=200, blank=True)

    # Used for dropdown and multiselect fields
    options = models.JSONField(default=list, blank=True)

    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # Control where this field appears
    show_on_registration = models.BooleanField(default=True)
    show_on_review = models.BooleanField(default=True)

    # Optional validation configuration
    validation_rules = models.JSONField(default=dict, blank=True)

    section = models.CharField(max_length=100, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "field_key"],
                name="unique_lab_category_field_key",
            )
        ]

    def __str__(self):
        return f"{self.category.name} - {self.label}"



class BranchCategoryValue(models.Model):
    branch = models.ForeignKey(
        "labs.Branch",
        on_delete=models.CASCADE,
        related_name="category_values",
    )

    field = models.ForeignKey(
        LabCategoryField,
        on_delete=models.PROTECT,
        related_name="branch_values",
    )

    # Supports strings, numbers, booleans, lists, and other JSON values
    value = models.JSONField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "field"],
                name="unique_branch_category_field_value",
            )
        ]

    def __str__(self):
        return f"{self.branch_id} - {self.field.label}"

    
class Branch(Trackable):
    """
    This table can be called as Branches
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name='lab_user', db_index=True, null=True, blank=True)
    
    # ============================================================
    # SOURCE / IDENTIFICATION
    # ============================================================

    
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, blank=True, null=True, db_index=True)
    # ============================================================
    # SOURCE-SPECIFIC IDENTIFICATION
    # ============================================================
    lab_category = models.ForeignKey(
        LabCategory,
        on_delete=models.SET_NULL,
        related_name="branches",
        null=True,
        blank=True,
    )
    # Stores dynamic data values matching the category's dynamic_schema keys
    category_data = models.JSONField(default=dict, blank=True)
    lab_code = models.CharField(max_length=100, blank=True, null=True)
    BIS_code = models.CharField(max_length=100, blank=True, null=True, help_text="From BIS")
    NABL_code = models.CharField(max_length=100, blank=True, null=True, help_text="From NABL")
    VISTA_code = models.CharField(max_length=100, blank=True, null=True, help_text="From Vista")    
    cert_no = models.CharField(max_length=100, blank=True, null=True)
    # ============================================================
    # LAB TYPE / CLASSIFICATION
    # ============================================================

    lab_type = models.CharField(max_length=100, blank=True, null=True)
    standard = models.CharField(max_length=100, blank=True, null=True)
    assessment_types = models.CharField(max_length=100, blank=True, null=True)
    discipline_name = models.CharField(max_length=255, blank=True, null=True)
    group_name = models.TextField(blank=True, null=True)
    sub_group_name = models.TextField(blank=True, null=True)
    li_type_of_lab_by_service = models.CharField(max_length=100, blank=True, null=True)
    
    serial_digits = models.PositiveIntegerField(blank=True, null=True)    
    
    # ============================================================
    # CONTACT INFORMATION
    # ============================================================
    contact_person = models.CharField(max_length=150, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_mobile = models.CharField(max_length=20, blank=True, null=True)
    land_line = models.CharField(max_length=50, blank=True, null=True)
    fax = models.CharField(max_length=50, blank=True, null=True)

    # ============================================================
    # LABORATORY LOCATION
    # ============================================================
    longitude = models.DecimalField(max_digits=20, decimal_places=8, blank=True, null=True)
    latitude = models.DecimalField(max_digits=20, decimal_places=8, blank=True, null=True)
    lab_address = models.TextField(blank=True, null=True)
    lab_city = models.CharField(max_length=255, blank=True, null=True)
    lab_district = models.ForeignKey(District, on_delete=models.SET_NULL, blank=True, null=True, db_index=True, related_name="labdistrict")
    lab_state = models.ForeignKey(State, on_delete=models.PROTECT, blank=True, null=True, verbose_name='State')
    lab_country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name='user_country', blank=True, null=True, verbose_name='Country')
    lab_pincode = models.CharField(max_length=10, blank=True, null=True, validators=[pincode_regex])
    lab_region = models.CharField(choices=REGIONS_CHOICES, max_length=100, blank=True, null=True)

    # ============================================================
    # REGISTERED / CORPORATE OFFICE
    # ============================================================

    registered_office_same_as_lab = models.BooleanField(default=True)
    registered_office_address = models.TextField(blank=True, null=True)
    registered_office_city = models.CharField(max_length=255, blank=True, null=True)
    registered_office_district = models.ForeignKey(District, on_delete=models.SET_NULL, blank=True, null=True, related_name="registered_district")
    registered_office_state = models.ForeignKey(State, on_delete=models.SET_NULL, blank=True, null=True, related_name="registered_state")
    registered_office_country = models.ForeignKey(Country, on_delete=models.SET_NULL, blank=True, null=True, related_name="registered_country")
    registered_office_pincode = models.CharField(max_length=10, blank=True, null=True)
    registered_office_mobile = models.CharField(max_length=20, blank=True, null=True)
    registered_office_telephone = models.CharField(max_length=50, blank=True, null=True)
    registered_office_fax = models.CharField(max_length=50, blank=True, null=True)

    # ============================================================
        # Lab organization Address
    # ============================================================
    org_name = models.CharField(max_length=100, verbose_name='Organization Name', null=True, blank=True, validators=[TEXT_REGEX])
    org_address = models.TextField(blank=True, null=True, verbose_name="Organization Address", validators=[TEXT_REGEX])
    org_district = models.ForeignKey(District, on_delete=models.SET_NULL, blank=True, null=True, related_name="organization_district", verbose_name='Organization District')
    org_city = models.CharField(max_length=200, blank=True, null=True, verbose_name="Organization City", validators=[TEXT_REGEX])
    org_state = models.ForeignKey(State, on_delete=models.PROTECT, blank=True, null=True, related_name='organization_state', verbose_name="Organization State")
    org_country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name='organization_country', blank=True, null=True, verbose_name="Organization Country")
    org_zipcode = models.CharField(max_length=8, blank=True, null=True, verbose_name="Organization Zip code", validators=[pincode_regex])
    org_doc_other = models.CharField(max_length=20, blank=True, null=True, verbose_name="Organization Document", validators=[TEXT_REGEX])
    org_office_same_as_lab = models.BooleanField(default=False, verbose_name="Same as laboratory")    
    
    # ============================================================
    # ACCREDITATION / CERTIFICATE DATES
    # ============================================================

    issue_date = models.DateField(blank=True, null=True)
    extend_date = models.DateField(blank=True, null=True)
    to_date = models.DateField(blank=True, null=True)
    amendment_date = models.DateField(blank=True, null=True)
    certificate_url = models.URLField(blank=True, null=True)

    # ============================================================
    # FACILITY INFORMATION
    # ============================================================

    permanent_facility = models.BooleanField(null=True,blank=True)
    site_facility = models.BooleanField(null=True,blank=True)
    mobile_facility = models.BooleanField(null=True,blank=True)

    # ============================================================
    # WEBSITE / PUBLIC PROFILE
    # ============================================================

    lab_name = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    lab_name_hindi =models.CharField(max_length=255, blank=True, null=True, db_index=True)
    lab_logo = models.ImageField(upload_to='labs/logos/', blank=True, null=True)
    logo_base64 = models.TextField(blank=True, null=True)
    lab_footer_logo = models.ImageField(upload_to='labs/logos/', blank=True, null=True)
    logo_footer_base64 = models.TextField(blank=True, null=True)
    nabl_logo = models.ImageField(upload_to='labs/logos/nabl/', blank=True, null=True, verbose_name='NABL logo for sample testing')
    nabl_logo_calibration = models.ImageField(upload_to='labs/logos/nabl_calibration/', blank=True, null=True, verbose_name='NABL logo for Calibration')
    cover_picture = models.ImageField(null=True, blank=True, upload_to='labs/cover/', verbose_name="Recent Cover Photo", validators=[FileExtensionValidator(
            allowed_extensions=['png', 'jpg', 'jpeg'])]
    )
    cover_base64 = models.TextField(blank=True, null=True)        
    website_url = models.URLField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    address_in_hi=models.TextField(null=True,blank=True)
    establishment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Lab Establishment Date"
    ) # not in user
    establishment_year = models.PositiveSmallIntegerField(
        verbose_name="Lab Establishment Year",
        null=True,
        blank=True
    )
    organization_type = models.CharField(max_length=200, blank=True, null=True, choices=ORGANIZATION_CHOICES, verbose_name="Ownership Type")
    # ============================================================
    # STATUS
    # ============================================================

    is_active = models.BooleanField(default=True)
    subscription_expires_at = models.DateTimeField(blank=True, null=True)
    vista_tenant_id = models.CharField(
        max_length=64, blank=True, null=True,
        help_text='Set only after payment-triggered migration into Vista. Null = still LabFinder-only.'
    )
    is_public = models.BooleanField(default=True, help_text='Controls searchability on the client portal.')

    lab_hierarchy_type = models.CharField(max_length=20, choices=LAB_TYPE_CHOICES, default='organization')
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='branch_parent',
        help_text='Set only when lab_type = branch. The organization that administers this branch.'
    )
    approval_status = models.CharField(
        max_length=20, choices=APPROVAL_STATUS_CHOICES, default='approved',
        help_text=(
            "'pending' while a branch-lab request awaits organization approval, or after a organization "
            "rejects it and the lab falls back to organization-but-pending, per the registration flow."
        ),
    )
    status = models.CharField(max_length=40, choices=STATUS_CHOICES,
                                   default='unclaimed')

    # --- Testing type & department selection (doc section 10) ---
    # testing_types = models.ManyToManyField(TestingType, blank=True, related_name='labs',
    #                                         help_text='e.g. Food Testing, Pathology, Footwear Testing.')
    departments = models.ManyToManyField(Department, blank=True, related_name='labs_operating',
                                          help_text='e.g. Chemical, Mechanical, Microbiological.')
    disciplines = models.ManyToManyField(Discipline, blank=True)
    categories = models.ManyToManyField(Category, blank=True, related_name='labs_categories')
    subcategories = models.ManyToManyField(SubCategory, blank=True, related_name='labs_subcategories')

    # --- Crawler-enrichable profile fields (doc section 11) ---
    about_us = models.TextField(blank=True, null=True)
    products_offered = models.JSONField(blank=True, null=True, default=list)
    services_offered = models.JSONField(blank=True, null=True, default=list)
    min_order_value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    # raw_data = models.TextField()

    def __str__(self):
        return self.lab_name or "-"

    class Meta:
        verbose_name = "Branch"
        verbose_name_plural = "Branches"
        # indexes = [
        #     # GIN Index for ultra-fast JSON querying in PostgreSQL
        #     models.Index(fields=['category_data'], name='category_data_gin_idx', opclasses=['jsonb_path_ops']),
        # ]

    def get_lab_address(self):
        address = ''
        if self.lab_address:
            address += f'{self.lab_address},\n'
        if self.lab_city:
            address += f' {self.lab_city}, \n'
        if self.lab_district:
            address += f' {self.lab_district}, \n'
        if self.lab_state:
            address += f' {self.lab_state}, \n'
        if self.lab_country:
            address += f' {self.lab_country} - '
        if self.lab_pincode:
            address += f' {self.lab_pincode}'
        return address
    
    @property
    def is_organization_lab(self):
        return self.lab_type == 'organization' and self.branch_parent.exists()

    @property
    def get_accreditations(self):
        """
        Gathers distinct active & non-expired accreditations for this Branch from:
        1. Direct relation (Accreditation.lab)
        2. BranchItem -> Accreditation (BranchItem.certificate)
        3. BranchItem -> TestingScopeFacility -> Accreditation (TestingScopeFacility.certificate)
        """
        today = timezone.now().date()

        # Common filter condition for active and non-expired certificates
        valid_cert_filter = models.Q(active=True) & (
            models.Q(validity_to__isnull=True) | models.Q(validity_to__gte=today)
        )

        # 1. Direct Accreditations (via related_name='branch_accreditation')
        direct_certs = self.branch_accreditation.filter(valid_cert_filter)

        # 2. Accreditations via BranchItem.certificate (via related_name='lab_scope')
        item_certs = Accreditation.objects.filter(
            branchitem__lab=self
        ).filter(valid_cert_filter)

        # 3. Accreditations via TestingScopeFacility.certificate
        facility_certs = Accreditation.objects.filter(
            testingscopefacility__scope__lab=self
        ).filter(valid_cert_filter)

        # Combine all querysets
        all_certs = (direct_certs | item_certs | facility_certs).distinct().select_related('accred')

        names = []
        for cert in all_certs:
            # Prefer AccreditationMaster short_code or name, fallback to Accreditation.name
            if cert.accred and cert.accred.active:
                display_name = cert.accred.short_code or cert.accred.name
            else:
                display_name = cert.name
            if display_name and display_name not in names:
                names.append(display_name)

        return names
    
    def manageable_labs(self):
        """Self + branch labs, for the organization's superadmin-style dashboard scope."""
        return Branch.objects.filter(models.Q(pk=self.pk) | models.Q(parent_id=self.pk))

    @property
    def active_promotional_subscription(self):
        """Returns the currently active promotional subscription if valid, else None."""
        now = timezone.now()
        return self.promotional_subscriptions.filter(
            status='active',
            is_current=True,
            starts_at__lte=now,
            expires_at__gte=now
        ).select_related('plan').first()

    @property
    def promotional_tier(self):
        sub = self.active_promotional_subscription
        if sub and sub.plan:
            return sub.plan.slug  # 'growth' or 'pro'
        return 'basic'

    @property
    def priority_tier_level(self):
        """1 for Pro (Top Organic), 2 for Growth (Above Free), 3 for Basic/Free (Standard Algorithmic)."""
        sub = self.active_promotional_subscription
        if sub and sub.plan:
            return sub.plan.priority_tier_level
        return 3

    @property
    def is_verified_growth(self):
        return self.promotional_tier == 'growth'

    @property
    def is_trusted_partner_pro(self):
        return self.promotional_tier == 'pro'

    @property
    def can_hide_reviews(self):
        if self.is_trusted_partner_pro:
            return True
        sub = self.active_promotional_subscription
        if sub and sub.plan and getattr(sub.plan, 'can_hide_reviews', False):
            return True
        return False

    @property
    def should_hide_reviews(self):
        sub = self.active_promotional_subscription
        if sub and sub.plan and sub.plan.can_hide_reviews and getattr(sub, 'hide_reviews', False):
            return True
        return False

    @property
    def has_ad_free_profile(self):
        if self.is_trusted_partner_pro:
            return True
        sub = self.active_promotional_subscription
        if sub and sub.plan and getattr(sub.plan, 'hide_competitor_ads', False):
            return True
        return False

    @property
    def effective_country(self):
        if self.lab_country:
            return self.lab_country
        if self.lab_state and hasattr(self.lab_state, 'country') and self.lab_state.country:
            return self.lab_state.country
        from apps.utility.models import Country
        return Country.objects.filter(name__iexact='India').first()

    def get_category_ids(self):
        cat_ids = set(self.categories.values_list('id', flat=True))
        item_cat_ids = self.lab_scope.filter(category__isnull=False).values_list('category__id', flat=True)
        cat_ids.update(item_cat_ids)
        return list(cat_ids)

    def clean(self):
        super().clean()
        if getattr(self, "lab_category_id", None) and self.category_data:
            # Validates before saving via Django Admin or ModelForm
            validate_lab_data(self.lab_category.id, self.category_data)

    def save(self, *args, **kwargs):
        self.full_clean()  # Trigger clean() during manual model save calls
        super().save(*args, **kwargs)


class BranchImage(Trackable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lab = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='facility_images')
    image = models.ImageField(upload_to='labs/photos/')
    is_active = models.BooleanField(default=False)
    
    def delete(self, *args, **kwargs):
        # Delete the actual file from storage before removing the DB record
        if self.image and os.path.isfile(self.image.path):
            try:
                os.remove(self.image.path)
            except Exception:
                pass
        super().delete(*args, **kwargs)

    class Meta:
        verbose_name = 'Branch Image'
        verbose_name_plural = 'Branch Images'
    
    


# --- Registration flow state machine (doc section 9) ---------------------------------

REGISTRATION_STATUS_CHOICES = (
    ('pending_email_verification', 'Pending Email Verification'),
    ('pending_org_check', 'Pending Organization Check'),
    ('pending_org_approval', 'Pending Organization Approval'),
    ('approved_as_org', 'Approved as Organization'),
    ('approved_as_branch', 'Approved as Branch'),
    ('rejected_by_organization', 'Rejected by Organization'),
)


class LabWebPage(Trackable):
    """
    Scraped/public website page belonging to a laboratory.
    Supports parent-child menu trees
    Also acts as the dynamic website menu configuration.
    """
    PAGE_TYPE_CHOICES = (
        ('ABOUT', _('About Us')),
        ('CONTACT', _('Contact Us')),
        ('SERVICE', _('Services')),
        ('PRODUCT', _('Products')),
        ('OTHER', _('Other')),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lab = models.ForeignKey(
        Branch, 
        on_delete=models.CASCADE, 
        related_name='web_pages', 
        verbose_name=_("Laboratory")
    )
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        blank=True, 
        null=True, 
        related_name='submenus',
        verbose_name=_("Parent Page/Menu")
    )
    menu_order = models.PositiveIntegerField(default=0, help_text=_("Ordering position in navigation bar"))
    show_in_menu = models.BooleanField(default=True)
    
    # -------------------------
    # Page information
    # -------------------------

    title = models.CharField(max_length=500, verbose_name=_("Page Title"))
    menu_title = models.CharField( max_length=255, blank=True, null=True)
    slug = models.SlugField(max_length=255, blank=True, null=True)
    page_type = models.CharField(max_length=20, choices=PAGE_TYPE_CHOICES, default='OTHER')
    url = models.URLField(max_length=1000, verbose_name=_("Original Page URL"))
    normalized_url = models.URLField(max_length=1000, blank=True, null=True)

    
    # -------------------------
    # Crawler information
    # -------------------------

    quality_score = models.FloatField(default=0.0)
    fetch_method = models.CharField(max_length=50, default='HTTP')
    content = models.TextField(blank=True, null=True, help_text=_("HTML/Markdown or raw body content"))
    source_type = models.CharField(max_length=30, default='crawler')

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _('Lab Web Page')
        verbose_name_plural = _('Lab Web Pages')
        ordering = ['menu_order', 'title']

        indexes = [
            models.Index(fields=['lab', 'is_active']),
            models.Index(fields=['lab', 'page_type']),
        ]

    def __str__(self):
        parent_str = f" -> {self.parent.title}" if self.parent else ""
        return f"{self.lab.lab_name}: {self.title}{parent_str}"
    

class LabSocialLink(Trackable):
    PLATFORM_CHOICES = (
        ('facebook', 'Facebook'),
        ('linkedin', 'LinkedIn'),
        ('instagram', 'Instagram'),
        ('youtube', 'YouTube'),
        ('twitter', 'Twitter'),
        ('other', 'Other'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lab = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='social_links')
    platform = models.CharField(max_length=30, choices=PLATFORM_CHOICES)
    url = models.URLField(max_length=1000)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['lab', 'platform'],
                name='unique_lab_social_platform'
            )
        ]

    def __str__(self):
        return f"{self.lab} - {self.platform}"


class ProductService(Trackable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lab = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='product_services')
    name = models.CharField(max_length=500, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    source_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)




def get_accreditation_logo_path(instance, filename):
    # Extract file extension
    ext = filename.split('.')[-1]
    
    # Get lab name slug safely
    if instance.lab and instance.lab.lab_name:
        lab_folder = slugify(instance.lab.lab_name)
    else:
        lab_folder = "unknown_lab"
        
    # Return formatted path
    return f"labs/{lab_folder}/accreditation_logos/{filename}"

def get_accreditation_cert_path(instance, filename):
    ext = filename.split('.')[-1]
    
    if instance.lab and instance.lab.lab_name:
        lab_folder = slugify(instance.lab.lab_name)
    else:
        lab_folder = "unknown_lab"
        
    return f"labs/{lab_folder}/accreditation_certificates/{filename}"

class Accreditation(Trackable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    accred = models.ForeignKey(AccreditationMaster, on_delete=models.PROTECT, blank=True, null=True)
    lab = models.ForeignKey(Branch, on_delete=models.SET_NULL, related_name='branch_accreditation', blank=True, null=True)
    certificate_no = models.CharField(max_length=255, blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    full_name = models.CharField(max_length=500, blank=True, null=True)
    validity_from = models.DateField(blank=True, null=True, verbose_name="Validity Date From")
    validity_to = models.DateField(blank=True, null=True, verbose_name="Validity Date To")
    renewal_date = models.DateField(blank=True, null=True, verbose_name="Renewal Date")
    # Set dynamic callable upload paths here
    logo = models.ImageField(upload_to=get_accreditation_logo_path, blank=True, null=True)
    logo_base64 = models.TextField(blank=True, null=True)
    certificate_img = models.ImageField(upload_to=get_accreditation_cert_path, blank=True, null=True)
    certificate_img_base64 = models.TextField(blank=True, null=True)
    # order = models.PositiveIntegerField(unique=True)
    exclude_failed_parameter = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Accreditation'
        verbose_name_plural = 'Accreditations'

    def __str__(self):
        return self.certificate_no or str(self.name)

    @property
    def is_expired(self):
        return self.validity_to and self.validity_to < timezone.now().date()



class ManpowerRoleDepartment(Trackable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lab = models.ForeignKey(Branch, on_delete=models.PROTECT, blank=True, null=True)
    group = models.ForeignKey(Role, on_delete=models.PROTECT, blank=True, null=True)
    departments = models.ManyToManyField(Department, blank=True)
    active_department = models.ForeignKey(Department, on_delete=models.PROTECT, blank=True, null=True,
                                           related_name="active_department")
    validity = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Manpower Role Department'
        verbose_name_plural = 'Manpower Role Departments'
        default_permissions = ()
        ordering = ['id']

    def __str__(self):
        return f"{self.group.code} of lab {self.lab}" if self.group else str(self.lab)



class BranchManpower(Trackable):
    # image = models.FileField(null=True,blank=True,storage=MediaStorage(),upload_to="manpower")
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lab = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='manpower_lab', null=True)
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name='manpower_user', db_index=True)
    type = models.CharField(choices=MANPOWER_TYPE_CHOICES, max_length=35, blank=True, null=True,)
    designation = models.CharField(max_length=35, verbose_name='Current Designation', blank=True, null=True,)
    emp_status = models.CharField(choices=EMPLOYMENT_CHOICES, max_length=35, blank=True, null=True, verbose_name="Employment Status")
    emp_number = models.CharField(max_length=200, blank=True, null=True, verbose_name="Employee Number")
    address = models.TextField(max_length=200, blank=True, null=True, verbose_name="Address")
    city = models.CharField(max_length=200, blank=True, null=True, verbose_name="City")
    country = models.CharField(max_length=200, blank=True, null=True, verbose_name="Country")
    zip_code = models.CharField(max_length=200, blank=True, null=True, verbose_name="Zip Code")
    joining_date = models.DateField(blank=True, null=True, verbose_name='Date of Joining')
    status = models.IntegerField(choices=MANPOWER_STATUS,default=0,verbose_name="Status")
    for_custom_is = models.BooleanField(default=False)  # for TR
    for_calibration = models.BooleanField(default=False) # for TR
    is_login_create = models.BooleanField(default=False)
    is_lab_head = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    user_disabled = models.BooleanField(default=False)
    remarks = models.TextField(blank=True, null=True)
    process_id = models.CharField(max_length=500, blank=True, null=True, verbose_name="Process ID")
    task_id = models.CharField(max_length=500, blank=True, null=True, verbose_name="Task ID")
    status_update = models.BooleanField(default=False)
    status_update_on = models.DateTimeField(auto_now=True)
    roles = models.ManyToManyField(ManpowerRoleDepartment, blank=True, through='ManpowerRoles') # this will store multiple roles to the manpower
    tags = models.ManyToManyField(Tag, blank=True, related_name="manpower_tags")
    group_assigned = models.ForeignKey(Group, on_delete=models.SET_NULL, blank=True, null=True)
    user_assigned = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True)
    camunda_workflow_key = models.CharField(max_length=255, blank=True, null=True)

    @property
    def get_is_number(self):
        return self.is_number
    
    def get_full_name(self):
        if self.user and self.user.first_name and self.user.last_name:
            return f'{self.user.first_name} {self.user.last_name}'
        elif self.user and self.user.first_name:
            return f'{self.user.first_name}'
        else:
            return ''

    def __str__(self):
        if self.user.email :
            return f'{self.user.email}'
        else:
            return f'{self.lab} - BranchManpower {self.id}'

    class Meta:
        verbose_name = 'Branch Manpower'
        verbose_name_plural = 'Branch Manpowers'

    def save(self, *args,**kwargs):
        super().save(*args, **kwargs)
        if not self.tags.all():
            if self.status == 0:
                pending = Tag.objects.filter(name__icontains="Pending", type__name="manpower")
                if pending:
                    self.tags.add(pending.last())
                else:
                    tag_type_obj, created = TagType.objects.get_or_create(name="manpower")
                    tag_obj = Tag.objects.create(name="Pending", type=tag_type_obj)
                    self.tags.add(tag_obj)


class ManpowerRoles(models.Model):
    manpower = models.ForeignKey(BranchManpower, on_delete=models.CASCADE, null=True)
    role = models.ForeignKey(ManpowerRoleDepartment, on_delete=models.CASCADE, null=True)
    default_role = models.BooleanField(default=False)
    order = models.SmallIntegerField(default=1) 
    # this field is used to store sorting order of manpower roles if the order is 1 then it will be default role. To make any default role change its order to 1.

    class Meta:
        verbose_name = 'Manpower Roles'
        verbose_name_plural = 'Manpower Roles'



# apps/labs/models.py — ADD these (taxonomy table is new; LabScope gets 4 new FK columns
# alongside its existing raw-text fields, which stay as-is for audit/fallback)

TAXONOMY_LEVEL_CHOICES = (
    ('category', 'Category'),
    ('group', 'Group'),
    ('subgroup', 'Sub-Group'),
    ('type', 'Type'),
)



class ItemMixins(models.Model):
    """
    Master Item Mixins Table used to store product or items for
    """
    ITEM_ROLE_CHOICES = [
        ('expense', _('Expense')),
        ('inventory', _('Inventory')),
        ('service', _('Service')),
        ('product', _('Product')),
    ]

    ITEM_TYPE_CHOICES = [
        ('labor', _('Labor')),
        ('material', _('Material')),
        ('equipment', _('Equipment')),
        ('lumpsum', _('Lump Sum')),
        ('other', _('Other')),
    ]
    REL_NAME_PREFIX = 'branch_item'
    # master items form fields for erp start from here....
    sku = models.CharField(max_length=50, blank=True, null=True, verbose_name=_('SKU Code'))
    upc = models.CharField(max_length=50, blank=True, null=True, verbose_name=_('UPC Code'))
    name = models.CharField(max_length=255, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    item_role = models.CharField(max_length=10, choices=ITEM_ROLE_CHOICES, null=True, blank=True)
    item_type = models.CharField(max_length=15, choices=ITEM_TYPE_CHOICES, null=True, blank=True)
    for_inventory = models.BooleanField(verbose_name=_('Is an item for inventory'), default=False,
                                        help_text=_('It is an item you require for your inventory.'))

    is_product_or_service = models.BooleanField(verbose_name=_('Is a product or service.'), default=False,
                                                help_text=_(
                                                    'Is a product or service you sell or provide to customers.'
                                                ))

    sold_as_unit = models.BooleanField(default=False)
    # inventory_account = models.ForeignKey(
    #     'accounting.Account',
    #     null=True,
    #     blank=True,
    #     verbose_name=_('Inventory Account'),
    #     related_name=f'{REL_NAME_PREFIX}_inventory_account',
    #     help_text=_('Inventory account where cost will be capitalized.'),
    #     on_delete=models.RESTRICT)
    # inventory_received = models.DecimalField(
    #     null=True,
    #     blank=True,
    #     decimal_places=3,
    #     max_digits=20,
    #     verbose_name=_('Total inventory received.'))
    # inventory_received_value = models.DecimalField(
    #     null=True,
    #     blank=True,
    #     decimal_places=2,
    #     max_digits=20,
    #     verbose_name=_('Total value of inventory received.'))
    # cogs_account = models.ForeignKey(
    #     'accounting.Account',
    #     null=True,
    #     blank=True,
    #     verbose_name=_('COGS Account'),
    #     related_name=f'{REL_NAME_PREFIX}_cogs_account',
    #     help_text=_('COGS account where cost will be recognized on Income Statement.'),
    #     on_delete=models.RESTRICT)
    # earnings_account = models.ForeignKey(
    #     'accounting.Account',
    #     null=True,
    #     blank=True,
    #     verbose_name=_('Earnings Account'),
    #     related_name=f'{REL_NAME_PREFIX}_earnings_account',
    #     help_text=_('Earnings account where revenue will be recognized on Income Statement.'),
    #     on_delete=models.RESTRICT)
    # expense_account = models.ForeignKey(
    #     'accounting.Account',
    #     null=True,
    #     blank=True,
    #     verbose_name=_('Expense Account'),
    #     related_name=f'{REL_NAME_PREFIX}_expense_account',
    #     help_text=_('Expense account where cost will be recognized on Income Statement.'),
    #     on_delete=models.RESTRICT)

    additional_info = models.JSONField(blank=True,
                                       null=True,
                                       default=dict,
                                       verbose_name=_('Item Additional Info')) # for subsub group as a json {"subsubgroup":}
    maximum_quantity = models.IntegerField(blank=True, null=True)
    stock_adjustment_type = models.CharField(max_length=55, blank=True, null=True,
                                             choices=[('Transfer/Indent', 'Transfer/Indent'), ('Return', 'Return'),
                                                      ('Production', 'Production')])
    serial = models.CharField(max_length=255, blank=True, null=True)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True)
    material_code = models.CharField(max_length=255, blank=True, null=True)
    min_stock_level = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    max_stock_level = models.DecimalField(max_digits=9, decimal_places=2, default=0)

    class Meta:
        abstract = True



ACCREDITATION_CHOICES = (
    ('nabl','NABL'),
    ('bis','BIS'),
    ('satra','Satra'),
    ('other','Other')
    )

# class ItemManager(models.Manager):
#     """
#     A custom defined ItemModelManager that implement custom QuerySet methods related to the ItemModel
#     """

#     # def for_entity(self, entity_slug, user_model):
#     #     """
#     #     Returns a QuerySet of ItemModel associated with a specific EntityModel & UserModel.
#     #     May pass an instance of EntityModel or a String representing the EntityModel slug.
#     #
#     #     Parameters
#     #     ----------
#     #     entity_slug: str or EntityModel
#     #         The entity slug or EntityModel used for filtering the QuerySet.
#     #     user_model
#     #         The request UserModel to check for privileges.
#     #
#     #     Returns
#     #     -------
#     #     ItemModelQuerySet
#     #         A Filtered ItemModelQuerySet.
#     #     """
#     #     qs = self.get_queryset()
#     #     if isinstance(entity_slug, lazy_loader.get_entity_model()):
#     #         return qs.filter(
#     #             Q(entity=entity_slug) &
#     #             (
#     #                     Q(entity__managers__in=[user_model]) |
#     #                     Q(entity__admin=user_model)
#     #             )
#     #         ).select_related('uom')
#     #     return qs.filter(
#     #         Q(entity__slug__exact=entity_slug) &
#     #         (
#     #                 Q(entity__managers__in=[user_model]) |
#     #                 Q(entity__admin=user_model)
#     #         )
#     #     ).select_related('uom')

#     def for_entity_active(self, entity_slug, user_model):
#         """
#         Returns a QuerySet of Active ItemModel associated with a specific EntityModel & UserModel.
#         May pass an instance of EntityModel or a String representing the EntityModel slug.

#         Parameters
#         ----------
#         entity_slug: str or EntityModel
#             The entity slug or EntityModel used for filtering the QuerySet.
#         user_model
#             The request UserModel to check for privileges.

#         Returns
#         -------
#         ItemModelQuerySet
#             A Filtered ItemModelQuerySet.
#         """
#         qs = self.for_entity(entity_slug=entity_slug, user_model=user_model)
#         return qs.filter(is_active=True)

#     def for_invoice(self, entity_slug, user_model):
#         """
#         Returns a QuerySet of ItemModels that can only be used for InvoiceModels for a specific EntityModel &
#         UserModel. These types of items qualify as products or services sold.
#         May pass an instance of EntityModel or a String representing the EntityModel slug.

#         Parameters
#         ----------
#         entity_slug: str or EntityModel
#             The entity slug or EntityModel used for filtering the QuerySet.
#         user_model
#             The request UserModel to check for privileges.

#         Returns
#         -------
#         ItemModelQuerySet
#             A Filtered ItemModelQuerySet.
#         """
#         qs = self.for_entity_active(entity_slug=entity_slug, user_model=user_model)
#         return qs.filter(is_product_or_service=True)

#     def for_bill(self, entity_slug, user_model):
#         """
#         Returns a QuerySet of ItemModels that can only be used for BillModels for a specific EntityModel &
#         UserModel. These types of items qualify as expenses or inventory purchases.
#         May pass an instance of EntityModel or a String representing the EntityModel slug.

#         Parameters
#         ----------
#         entity_slug: str or EntityModel
#             The entity slug or EntityModel used for filtering the QuerySet.
#         user_model
#             The request UserModel to check for privileges.

#         Returns
#         -------
#         ItemModelQuerySet
#             A Filtered ItemModelQuerySet.
#         """
#         qs = self.for_entity_active(entity_slug=entity_slug, user_model=user_model)
#         return qs.filter(
#             (
#                     Q(is_product_or_service=False) &
#                     Q(for_inventory=False)
#             ) |
#             Q(for_inventory=True)
#         )

#     def for_po(self, entity_slug, user_model):
#         """
#         Returns a QuerySet of ItemModels that can only be used for PurchaseOrders for a specific EntityModel &
#         UserModel. These types of items qualify as inventory purchases.
#         May pass an instance of EntityModel or a String representing the EntityModel slug.

#         Parameters
#         ----------
#         entity_slug: str or EntityModel
#             The entity slug or EntityModel used for filtering the QuerySet.
#         user_model
#             The request UserModel to check for privileges.

#         Returns
#         -------
#         ItemModelQuerySet
#             A Filtered ItemModelQuerySet.
#         """
#         qs = self.for_entity(entity_slug=entity_slug, user_model=user_model)
#         return qs.inventory_all()

#     def for_estimate(self, entity_slug: str, user_model):
#         """
#         Returns a QuerySet of ItemModels that can only be used for EstimateModels for a specific EntityModel &
#         UserModel. These types of items qualify as products.
#         May pass an instance of EntityModel or a String representing the EntityModel slug.

#         Parameters
#         ----------
#         entity_slug: str or EntityModel
#             The entity slug or EntityModel used for filtering the QuerySet.
#         user_model
#             The request UserModel to check for privileges.

#         Returns
#         -------
#         ItemModelQuerySet
#             A Filtered ItemModelQuerySet.
#         """
#         qs = self.for_entity_active(entity_slug=entity_slug, user_model=user_model)
#         return qs.products()



class ItemManager(models.Manager):
    pass




class ItemQuerySet(models.QuerySet):
    """
    A custom-defined ItemQuerySet that implements custom QuerySet methods related to the ItemModel.
    """

    def lims_items(self):
        """
        Filters the QuerySet to only active Master Item Table.

        Returns
        -------
        MasterItemQuerySet
            A QuerySet with applied filters.
        """
        return self.filter(standard__form_type='lims')

    def erp_items(self):
        """
        Filters the QuerySet to only active Master Item Table.

        Returns
        -------
        MasterItemQuerySet
            A QuerySet with applied filters.
        """
        return self.filter(standard__form_type='erp')

    def active(self):
        """
        Filters the QuerySet to only active Item Models.

        Returns
        -------
        ItemModelQuerySet
            A QuerySet with applied filters.
        """
        return self.filter(disable=False)

    def products(self):
        """
        Filters the QuerySet to ItemModels that only qualify as products.

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        return self.filter(
            (
                    Q(is_product_or_service=True) &
                    Q(for_inventory=True)
            ) |
            Q(item_role='product')
        )

    def services(self):
        """
        Filters the QuerySet to ItemModels that only qualify as services.

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        return self.filter(
            (
                    Q(is_product_or_service=True) &
                    Q(for_inventory=False)
            ) |
            Q(item_role='service')
        )

    def expenses(self):
        """
        Filters the QuerySet to ItemModels that only qualify as expenses.

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        return self.filter(
            (
                    Q(is_product_or_service=False) &
                    Q(for_inventory=False)
            ) | Q(item_role='expense')
        )

    def inventory_wip(self):
        """
        Filters the QuerySet to ItemModels that only qualify as inventory.
        These types of items cannot be sold as they are not considered a finished product.

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        return self.filter(
            (
                    Q(is_product_or_service=False) &
                    Q(for_inventory=True)
            ) | Q(item_role='inventory')
        )

    def inventory_all(self):
        """
        Filters the QuerySet to ItemModels that only qualify as inventory.
        These types of items may be finished or unfinished.


        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        return self.filter(
            (
                    (
                            Q(is_product_or_service=False) &
                            Q(for_inventory=True)
                    ) | Q(item_role='inventory')
            ) |
            (
                    (
                            Q(is_product_or_service=True) &
                            Q(for_inventory=True)
                    ) |
                    Q(item_role='product')

            )
        )

    def bills(self):
        """
        Filters the QuerySet to ItemModels that are eligible only for bills..

        Returns
        -------
        ItemModelQuerySet
            A Filtered ItemModelQuerySet.
        """
        return self.filter(
            (
                    Q(is_product_or_service=False) &
                    Q(for_inventory=False)
            ) |
            Q(for_inventory=True)
        )

    def invoices(self):
        return self.filter(is_product_or_service=True)

    def estimates(self):
        return self.invoices()

    def purchase_orders(self):
        return self.inventory_all()



FORM_TYPE = (('lims', 'LIMS'), ('erp', 'ERP'))

class BranchItem(Trackable, ItemMixins):
    """
    LabFinder's version of Vista's BranchItem.

    Keeps the LIMS-related fields while excluding ERP-specific
    inventory and accounting functionality.
    """
    form_type = models.CharField(max_length=50, choices=FORM_TYPE, default='lims')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, blank=True, null=True, db_index=True)
    standard_id = models.CharField(max_length=255, blank=True, null=True, help_text="From Vista")
    isn_id = models.PositiveIntegerField(null=True, blank=True)
    is_number = models.CharField(max_length=550, blank=True, db_index=True, verbose_name='IS Number / Method Standard')
    is_title = models.TextField(blank=True, verbose_name='Title')
    lab = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='lab_scope')
    category = models.ForeignKey(
            'Category', 
            on_delete=models.SET_NULL, null=True, blank=True, 
            related_name='branch_items'
    )
    description = models.TextField(blank=True, null=True)
    # Category & Group mappings
    sort_order = models.CharField(max_length=100, blank=True, null=True)
    # NABL Mapping Fields
    sub_group = models.TextField(blank=True, null=True, help_text="Stores Subgroup/Group", verbose_name="Group / Sub Group")
    part = models.CharField(max_length=255, blank=True, null=True)
    year = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    is_non_isn = models.BooleanField(default=False, verbose_name="Is Non-IS ?")
    is_custom = models.BooleanField(default=False, verbose_name="Is Custom-IS ?")
    not_real_std = models.BooleanField(default=False, verbose_name="Not Real Standard ?")
    is_standard = models.BooleanField(default=False, verbose_name="Is Standard ?")
    is_calibration = models.BooleanField(default=False, verbose_name="Is Calibration ?")
    is_public = models.BooleanField(default=True, verbose_name="Is Publicly Visible ?")
    parallel_testing = models.BooleanField(default=True, verbose_name="Is Parallel Testing ?")
    automatic_split = models.BooleanField(default=True, verbose_name="Is Automatic Split ?")
    pricing_methodology = models.CharField(max_length=30, choices=PRICING_METHOD, default="parameter")
    # complete_testing_charge = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    complete_test_charges = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    minimum_quantity = models.IntegerField(blank=True, null=True)
    unic_number = models.PositiveIntegerField(null=True, blank=True)
    loq = models.CharField(max_length=550, null=True, blank=True)
    is_disable = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False, verbose_name="Is Standard Deleted")        
    unit = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL)
    gst = models.ForeignKey(GST, on_delete=models.SET_NULL, blank=True, null=True)
    accreditation = models.CharField(choices=ACCREDITATION_CHOICES, max_length=100, default='other')
    certificate = models.ManyToManyField(Accreditation, blank=True) # not in use
    # accrediation = BIS or NABL
    test_type = models.ManyToManyField(Department, verbose_name="Type of Test", blank=True)
    remarks = models.TextField(blank=True, null=True)
    
    all_parameters_selected = models.BooleanField(default=True)
    disable_at = models.DateField(blank=True, null=True)
    lab_capacity = models.IntegerField(blank=True, null=True)
    responsibilities = models.ManyToManyField(BranchManpower, blank=True)
    category = models.ManyToManyField(Category, blank=True)
    subcategory = models.ManyToManyField(SubCategory, blank=True)
    service_category = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL, null=True, verbose_name="Category of Service")
    objects = ItemManager.from_queryset(ItemQuerySet)()
    complete_request = models.TextField(null=True, blank=True)

    def __str__(self):
        return str(self.pk)

    class Meta:
        verbose_name = "Testing Scope"
        verbose_name_plural = "Testing Scopes"



class FacilityRangeValue(Trackable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    text = models.CharField(max_length=100, blank=True, null=True)
    value_type = models.CharField(max_length=20, choices=UOM_VALUE_TYPE, default='1')
    range_min = models.CharField(max_length=255, blank=True, null=True)
    range_max = models.CharField(max_length=255, blank=True, null=True)
    range_val = models.FloatField(blank=True, null=True)
    desc = models.TextField(blank=True, null=True)

    def __str__(self):
        return str(self.range_val)


class FacilitiesQualitativeValue(Trackable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    text = models.CharField(max_length=555, blank=True, null=True)
    value = models.CharField(max_length=100, default='1')
    desc = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.text or str(self.id)


class TestingScopeFacility(Trackable):
    ResultSource = (
        ('manual', 'Manual'),
        ('equipment', 'Equipment'),
        ('auto', 'Auto'),
    )

    TestingType = [
        ('Routine', 'Routine'),
        ('Acceptance', 'Acceptance'),
    ]

    RESULT_TYPE_CHOICES = (
        ('Qualitative', 'Qualitative'),
        ('Quantitative', 'Quantitative'),
    )

    FIELD_TYPE_CHOICES = (
        ('Input', 'Input'),
        ('Select', 'Select'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Scope and laboratory
    scope = models.ForeignKey(BranchItem, on_delete=models.PROTECT, related_name="facility_scope")
    additional_scopes = models.ManyToManyField(BranchItem, blank=True, related_name="additional_scopes_facilities")
    lab = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='lab_facility', blank=True, null=True)

    # Parameter / clause information
    parameter_id = models.CharField(max_length=255, blank=True, null=True, help_text="From Vista")
    testing_type = models.CharField(max_length=22, choices=TestingType, null=True, blank=True)
    clause_no = models.CharField(max_length=255, db_index=True)
    title = models.TextField(blank=True, null=True)
    parameter = models.TextField()
    test_description = models.TextField(blank=True, null=True)
    test_type = models.ForeignKey(Department, on_delete=models.SET_NULL, blank=True, null=True, verbose_name="Type of Test")
    clause_group = models.CharField(max_length=255, blank=True, null=True)

    # Charges and quantity
    quantity = models.PositiveIntegerField(default=1)
    certificate = models.ManyToManyField(Accreditation, blank=True)
    charges = models.FloatField(default=1)
    specimen_charge = models.FloatField(null=True, blank=True)
    billable_for_multiple_quantity = models.BooleanField(default=True)
    quantity_upgradable = models.BooleanField(default=True)

    # Result configuration
    result_type = models.CharField(max_length=20, choices=RESULT_TYPE_CHOICES, default="Quantitative", blank=True, null=True)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, blank=True, null=True)
    qualitative_text = models.CharField(max_length=555, blank=True, null=True)
    source_of_result = models.CharField(max_length=30, choices=ResultSource, blank=True, null=True)
    qualitative_values = models.ManyToManyField(FacilitiesQualitativeValue, blank=True)
    qualitative_values = models.ManyToManyField(ParameterQualitativeValue, blank=True)
    range_value = models.ManyToManyField(FacilityRangeValue, blank=True)
    range_values = models.ManyToManyField(ParameterRangeValue, blank=True)
    range_unit = models.ForeignKey(Unit, blank=True, null=True, on_delete=models.SET_NULL)
    allow_limit_edit = models.BooleanField(default=False)

    # Testing methods and categories
    method_test = models.ManyToManyField(TestMethod, blank=True)
    category = models.ManyToManyField(SampleClauseCategory, blank=True)
    subcategory = models.ManyToManyField(SampleClauseSubCategory, blank=True)

    # Clause flags and visibility
    is_clause_duplicate = models.BooleanField(default=False)
    is_clause_optional = models.BooleanField(default=False)
    visible_to_user = models.BooleanField(default=True)
    show_in_reports = models.BooleanField(default=True)
    highlight_clause = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # Equipment
    equipment = models.ForeignKey(EquipmentType, on_delete=models.PROTECT, blank=True, null=True)
    connected_with_equipment = models.BooleanField(default=False)

    # Testing time
    optimum_testing_time = models.PositiveIntegerField(default=1, verbose_name='Optimum Testing Time')

    # UOM / uncertainty of measurement
    uom_value_type = models.CharField(max_length=20, choices=UOM_VALUE_TYPE, blank=True, null=True)
    uom_range_min = models.CharField(max_length=255, blank=True, null=True)
    uom_range_max = models.CharField(max_length=255, blank=True, null=True)
    uom_val = models.FloatField(blank=True, null=True)

    # Lab configuration permissions
    can_change_uom = models.BooleanField(default=True)
    can_change_charges = models.BooleanField(default=True)
    can_change_range_limits = models.BooleanField(default=True)

    # Identifiers and limits
    short_name = models.CharField(max_length=555, blank=True, null=True)
    unic_number = models.PositiveIntegerField(null=True, blank=True)
    loq = models.CharField(max_length=550, null=True, blank=True)
    lod = models.CharField(max_length=550, null=True, blank=True)
    cas_no = models.CharField(max_length=255, blank=True, null=True)
    decimal_digits_limit = models.SmallIntegerField(default=4)
    status = models.CharField(max_length=255, blank=True, null=True)
    complete_request = models.TextField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Testing Scope Facility Available'
        verbose_name_plural = 'Testing Scope Facilities Available'
        # constraints = [
        #     models.UniqueConstraint(fields=['lab', 'scope', 'clause_no'], name='unique_lab_scope_clause')
        # ]

    def __str__(self):
        return f'{self.scope} {self.clause_no} ({self.parameter})'
    

class TestingPackage(Trackable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2, help_text='Overall package price')
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text='Discount percentage')
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # Products linked via Through Model
    lab = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='testing_packages', null=True)
    products = models.ManyToManyField(BranchItem, through='TestingPackageItem', related_name='packages')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Testing Package'
        verbose_name_plural = 'Testing Packages'
        ordering = ['name']
        unique_together = ('lab', 'name')  # Ensure unique package names per lab


class TestingPackageItem(Trackable):
    """Junction table mapping products to packages with extra metadata."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey(TestingPackage, on_delete=models.CASCADE, related_name='package_items')
    product = models.ForeignKey(BranchItem, on_delete=models.PROTECT, related_name='package_memberships')
    
    quantity = models.PositiveIntegerField(default=1)
    is_optional = models.BooleanField(default=False)

    class Meta:
        unique_together = ('package', 'product')


class LabConfiguration(Trackable):
    """Configuration table for lab dashboard settings and notifications."""
    branch = models.OneToOneField(
        Branch,
        on_delete=models.CASCADE,
        related_name="configuration",
        verbose_name="Laboratory / Branch",
    )
    # Notifications (Choose what you get alerted about)
    new_lead_received = models.BooleanField(
        default=True,
        verbose_name="New Lead Received",
        help_text="Email + push notification instantly when a new lead is received",
    )
    customer_messages = models.BooleanField(
        default=True,
        verbose_name="Customer Messages",
        help_text="Email when a customer replies or sends a message",
    )
    weekly_performance_summary = models.BooleanField(
        default=True,
        verbose_name="Weekly Performance Summary",
        help_text="Views, leads and response-time digest",
    )
    product_platform_updates = models.BooleanField(
        default=False,
        verbose_name="Product & Platform Updates",
        help_text="New features, announcements and policy changes",
    )

    # Account Settings (Permanent & Profile level actions)
    show_pricing_publicly = models.BooleanField(
        default=True,
        verbose_name="Show Pricing Publicly",
        help_text="Hide to require an enquiry before buyers see prices",
    )
    hide_from_competing_labs = models.BooleanField(
        default=False,
        verbose_name="Hide from Competing Labs",
        help_text="Don't appear in 'similar labs' on competitor pages",
    )
    is_deactivated = models.BooleanField(
        default=False,
        verbose_name="Deactivate Lab Profile",
        help_text="Hide this location from search temporarily",
    )

    # Plan & Billing
    plan_tier = models.CharField(
        max_length=50,
        default="free",
        choices=[
            ("free", "Verified Partner Lab (Free Plan)"),
            ("vista_sync", "Vista LIMS Sync Plan"),
            ("pro", "Pro Lab Plan"),
        ],
        verbose_name="Plan Tier",
    )
    extra_settings = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Lab Configuration"
        verbose_name_plural = "Lab Configurations"

    def __str__(self):
        branch_name = self.branch.lab_name if self.branch else "Unknown Lab"
        return f"Configuration for {branch_name}"


class BranchManpowerPermission(Trackable):
    """
    Git repository-like portal access and granular section permissions for lab management.
    their portal access level (Lab Admin, Lead Manager, Viewer, Custom) and section permissions.
    """
    ROLE_CHOICES = (
        ("admin", "Lab Admin"),
        ("manager", "Lead Manager"),
        ("viewer", "Viewer"),
        ("custom", "Custom"),
    )
    STATUS_CHOICES = (
        ("active", "Active"),
        ("suspended", "Suspended"),
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="manpower_permissions",
        verbose_name="Laboratory / Branch",
    )
    manpower = models.OneToOneField(
        BranchManpower,
        on_delete=models.CASCADE,
        related_name="portal_permission",
        verbose_name="Branch Manpower Employee",
    )
    role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        default="manager",
        verbose_name="Portal Repository Role",
    )

    # Section / Feature Permissions (Git repository-style access control)
    can_manage_leads = models.BooleanField(
        default=True,
        verbose_name="Leads Access",
        help_text="View and reply to inbound customer leads",
    )
    can_manage_orders = models.BooleanField(
        default=True,
        verbose_name="Orders & Payments",
        help_text="Manage active orders, milestone approvals, and payments",
    )
    can_manage_scope = models.BooleanField(
        default=False,
        verbose_name="Test & Scope Management",
        help_text="Add, edit, and publish testing parameters and scopes",
    )
    can_manage_profile = models.BooleanField(
        default=False,
        verbose_name="Profile & Facility Details",
        help_text="Edit lab contact details, facility pictures, and accreditations",
    )
    can_manage_reviews = models.BooleanField(
        default=True,
        verbose_name="Customer Reviews",
        help_text="View customer ratings and publish official lab replies",
    )
    can_view_analytics = models.BooleanField(
        default=True,
        verbose_name="Analytics & Reports",
        help_text="View traffic, conversion rates, and performance statistics",
    )
    can_manage_settings = models.BooleanField(
        default=False,
        verbose_name="Settings & Team Access",
        help_text="Manage lab notification preferences, billing, and team members",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        verbose_name = "Branch Manpower Portal Permission"
        verbose_name_plural = "Branch Manpower Portal Permissions"
        ordering = ["-role", "manpower__user__first_name"]

    def __str__(self):
        name = self.get_full_name()
        desig = self.manpower.designation if self.manpower and self.manpower.designation else "Staff"
        return f"{name} ({desig}) — {self.get_role_display()} at {self.branch.lab_name if self.branch else ''}"

    @property
    def name(self):
        return self.get_full_name()

    @property
    def email(self):
        return self.manpower.user.email if self.manpower and self.manpower.user else ""

    @property
    def designation(self):
        return self.manpower.designation if self.manpower else ""

    def get_full_name(self):
        if not self.manpower or not self.manpower.user:
            return "Team Member"
        full = self.manpower.get_full_name()
        return full if full else (self.manpower.user.get_full_name() or self.manpower.user.username)

    def get_initials(self):
        nm = self.get_full_name()
        if not nm or nm == "Team Member":
            em = self.email
            return (em[:2] if em else "TM").upper()
        parts = nm.strip().split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        return nm[:2].upper()

    def apply_role_preset(self, role):
        self.role = role
        if role == "admin":
            self.can_manage_leads = True
            self.can_manage_orders = True
            self.can_manage_scope = True
            self.can_manage_profile = True
            self.can_manage_reviews = True
            self.can_view_analytics = True
            self.can_manage_settings = True
        elif role == "manager":
            self.can_manage_leads = True
            self.can_manage_orders = True
            self.can_manage_scope = False
            self.can_manage_profile = False
            self.can_manage_reviews = True
            self.can_view_analytics = True
            self.can_manage_settings = False
        elif role == "viewer":
            self.can_manage_leads = False
            self.can_manage_orders = False
            self.can_manage_scope = False
            self.can_manage_profile = False
            self.can_manage_reviews = False
            self.can_view_analytics = True
            self.can_manage_settings = False


# Backward compatibility alias
LabTeamMember = BranchManpowerPermission


# ==============================================================================
# PROMOTIONAL PLANS & ADD-ONS
# ==============================================================================

class PromotionalPlan(Trackable):
    """
    3 Promotional Plans for laboratories to purchase for promotion:
    1. Basic (Free) - Base price ₹0 / 30 Days
    2. Verified Lab (Growth) - Base price ₹4,999 / 30 Days
    3. Trusted Partner (Pro) - Base price ₹14,999 / 30 Days
    """
    PLAN_TIER_CHOICES = (
        ('basic', 'Basic (Free)'),
        ('growth', 'Verified Lab (Growth)'),
        ('pro', 'Trusted Partner (Pro)'),
    )

    SEARCH_RANKING_CHOICES = (
        ('standard', 'Standard (Algorithmic)'),
        ('tier_2', 'Priority Tier 2 (Above Free)'),
        ('tier_1', 'Priority Tier 1 (Top Organic)'),
    )

    TRUST_BADGE_CHOICES = (
        ('basic', 'Basic Listed'),
        ('verified_lab', 'Verified Lab Badge (GST/License)'),
        ('trusted_partner', 'NABL / ISO Verified Highlight Badge'),
    )

    BANNER_TYPE_CHOICES = (
        ('none', 'No Banner'),
        ('static_header', '1 Static Header Banner'),
        ('carousel_video', 'Carousel Banner (Up to 3) + Video'),
    )

    DIRECT_CTA_CHOICES = (
        ('request_quote', 'Request Quote'),
        ('send_enquiry', 'Send Enquiry'),
        ('all_channels', 'Send Enquiry, Direct Phone, WhatsApp & Instant RFQ'),
    )

    HOME_PAGE_LISTING_CHOICES = (
        ('random', 'Random'),
        ('high_priority', 'High Priority Listing'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, help_text='Plan Name, e.g. Basic (Free), Verified Lab (Growth), Trusted Partner (Pro)')
    slug = models.SlugField(max_length=120, unique=True, choices=PLAN_TIER_CHOICES)
    tagline = models.CharField(max_length=255, blank=True, help_text='Short description or promotional subtitle')
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text='Base Price (30 Days INR)')
    billing_period_days = models.PositiveIntegerField(default=30, help_text='Duration in days, defaults to 30')

    # Search Ranking Priority
    search_ranking_priority = models.CharField(max_length=50, choices=SEARCH_RANKING_CHOICES, default='standard')
    priority_tier_level = models.PositiveSmallIntegerField(
        default=3,
        help_text='1 = Priority Tier 1 (Top Organic), 2 = Priority Tier 2 (Above Free), 3 = Standard (Algorithmic)'
    )

    # Trust & Compliance Badge
    trust_badge_type = models.CharField(max_length=50, choices=TRUST_BADGE_CHOICES, default='basic')
    badge_label = models.CharField(max_length=100, default='Basic Listed', help_text='Badge label text shown on lab cards')
    requires_gst_license = models.BooleanField(default=False, help_text='Requires filling GST / License details (Growth plan)')
    requires_nabl_iso = models.BooleanField(default=False, help_text='Requires verifying NABL / ISO details (Pro plan)')

    # Profile Promotional Banner
    banner_type = models.CharField(max_length=50, choices=BANNER_TYPE_CHOICES, default='none')
    max_header_banners = models.PositiveSmallIntegerField(default=0, help_text='0 = None, 1 = Static Header Banner, 3 = Carousel Banners')
    allow_video_banner = models.BooleanField(default=False, help_text='Allows embedding promotional video (Pro plan)')

    # Direct Lead CTA Buttons (Customer End)
    direct_cta_type = models.CharField(max_length=50, choices=DIRECT_CTA_CHOICES, default='request_quote')
    allow_direct_phone = models.BooleanField(default=False, help_text='Direct Phone CTA button visible at customer end')
    allow_whatsapp = models.BooleanField(default=False, help_text='WhatsApp CTA button visible at customer end')
    allow_instant_rfq = models.BooleanField(default=False, help_text='Instant RFQ CTA button visible at customer end')

    # Review & Competitor Visibility Controls
    can_hide_reviews = models.BooleanField(default=False, help_text='Lab can hide reviews with this plan (Trusted Partner / Pro)')
    hide_competitor_ads = models.BooleanField(default=False, help_text='Competitor ads hidden (Ad-free profile for Pro plan)')

    # Enquiries & Home Page Priority
    monthly_shared_enquiries = models.IntegerField(default=2, help_text='Shared enquiries per month: 2 for Basic, 10 for Growth, -1 for Unlimited')
    is_unlimited_enquiries = models.BooleanField(default=False, help_text='Unlimited shared enquiries')
    home_page_listing = models.CharField(max_length=50, choices=HOME_PAGE_LISTING_CHOICES, default='random')

    # Administrative Controls
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text='Highlight as Recommended / Most Popular')
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Promotional Plan'
        verbose_name_plural = 'Promotional Plans'
        ordering = ['sort_order', 'base_price']

    def __str__(self):
        return f"{self.name} (₹{self.base_price:.0f})"


class PromotionalPlanFeature(Trackable):
    """
    Extensible feature definitions that superusers can add / modify from Django Admin.
    Allows dynamic feature comparison tables and custom feature offerings.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, unique=True, help_text='e.g. Search Ranking Priority, Manage Reviews')
    code = models.SlugField(max_length=150, unique=True, help_text='Unique slug, e.g. search_ranking, manage_reviews')
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Promotional Plan Feature'
        verbose_name_plural = 'Promotional Plan Features'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class PlanFeatureValue(Trackable):
    """
    Mapping between PromotionalPlan and PromotionalPlanFeature with customizable value text.
    Managed via TabularInline in PromotionalPlanAdmin for superusers to add more features.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(PromotionalPlan, on_delete=models.CASCADE, related_name='feature_values')
    feature = models.ForeignKey(PromotionalPlanFeature, on_delete=models.CASCADE, related_name='plan_values')
    value_text = models.CharField(
        max_length=255,
        help_text='Display text, e.g. "Priority Tier 2 (Above Free)", "1 Static Header Banner", "Can hide reviews"'
    )
    is_included = models.BooleanField(default=True, help_text='Whether this feature is included in the plan (checkmark vs cross)')
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Plan Feature Value'
        verbose_name_plural = 'Plan Feature Values'
        ordering = ['sort_order', 'feature__sort_order']
        unique_together = ('plan', 'feature')

    def __str__(self):
        return f"{self.plan.name} -> {self.feature.name}: {self.value_text}"


class PromotionalAddon(Trackable):
    """
    Promotional Add-on products from figma-screens/promotional-addon.png:
    - Category Featured Lab Pin (Top 3 search results per category/country, Sponsored, Max 3 slots, ₹2999 - ₹7999)
    - Competitor Targeting (Top banner on other labs profile, Promoted/Ad, 3 rotating slots, ₹4,999)
    - Home Page Listing (Listing on home page for particular category, Sponsored, 1 per category)
    """
    ADDON_CODE_CHOICES = (
        ('category_featured_pin', 'Category Featured Lab Pin'),
        ('competitor_targeting', 'Competitor Targeting'),
        ('home_page_listing', 'Home Page Listing'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150, unique=True)
    code = models.SlugField(max_length=150, unique=True, choices=ADDON_CODE_CHOICES)
    placement = models.CharField(max_length=255, help_text='Placement description, e.g. Top 3 search results per category/country')
    tagging = models.CharField(max_length=100, default='Sponsored', help_text='Tagging label, e.g. Sponsored or Promoted / Ad')
    inventory_cap_text = models.CharField(max_length=150, help_text='e.g. Max 3 slots per category/country, 3 rotating slots')
    max_inventory_slots = models.PositiveSmallIntegerField(default=3, help_text='Numeric cap for slots per category/region')
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text='Base Price (30 Days INR)')
    max_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Upper range for dynamic pricing, e.g. 7999')
    pricing_factor = models.CharField(max_length=255, blank=True, help_text='e.g. Category & city search demand, Category traffic volume')
    duration_days = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Promotional Add-on'
        verbose_name_plural = 'Promotional Add-ons'
        ordering = ['sort_order', 'name']

    def __str__(self):
        price_display = f"₹{self.base_price:.0f}"
        if self.max_price:
            price_display = f"₹{self.base_price:.0f} - ₹{self.max_price:.0f}"
        return f"{self.name} ({price_display} / {self.duration_days} Days)"


class LabPlanSubscription(Trackable):
    """
    Represents a Lab's application / subscription to a PromotionalPlan.
    Handles verification form data (GST/License for Growth, NABL/ISO for Pro),
    banner uploads, direct contact channels (Phone/WhatsApp/RFQ), and approval workflow.
    """
    STATUS_CHOICES = (
        ('draft', 'Draft (Form In Progress)'),
        ('submitted', 'Submitted (Pending Verification)'),
        ('verified', 'Verified (Awaiting Payment)'),
        ('active', 'Active (Paid & Published)'),
        ('rejected', 'Verification Rejected'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('waived', 'Waived / Free'),
    )

    VERIFICATION_STATUS_CHOICES = (
        ('not_required', 'Not Required'),
        ('pending', 'Pending Verification'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lab = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='promotional_subscriptions')
    plan = models.ForeignKey(PromotionalPlan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft', db_index=True)
    is_current = models.BooleanField(default=False, db_index=True, help_text='Flags this as the actively applying/active plan for the lab')

    # Pricing & Payment (Price displayed & paid in the last step)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text='Price in INR to pay in last step')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_reference = models.CharField(max_length=150, blank=True, null=True, help_text='Payment transaction ID / Razorpay / Stripe ID')
    paid_at = models.DateTimeField(null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Growth Plan Verification: GST / License
    gst_number = models.CharField(max_length=50, blank=True, null=True, help_text='Required for Verified Lab Badge (Growth plan)')
    license_number = models.CharField(max_length=100, blank=True, null=True, help_text='Drug/Trade/Operating License Number')
    gst_license_document = models.FileField(
        upload_to='labs/promotions/verification/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        help_text='Upload GST Certificate or Trade License'
    )

    # Pro Plan Verification: NABL / ISO Details
    nabl_accreditation_number = models.CharField(max_length=100, blank=True, null=True, help_text='NABL Certificate / Accreditation No.')
    nabl_document = models.FileField(
        upload_to='labs/promotions/verification/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        help_text='Upload NABL Certificate'
    )
    iso_certification_number = models.CharField(max_length=100, blank=True, null=True, help_text='ISO Standard Certification No. (e.g. ISO 9001 / ISO 17025)')
    iso_document = models.FileField(
        upload_to='labs/promotions/verification/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])],
        help_text='Upload ISO Certificate'
    )

    # Admin Verification Workflow
    verification_status = models.CharField(max_length=30, choices=VERIFICATION_STATUS_CHOICES, default='pending')
    verification_remarks = models.TextField(blank=True, null=True, help_text='Internal notes or rejection reason')
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_lab_subscriptions')
    verified_at = models.DateTimeField(null=True, blank=True)

    # Growth Plan Banner: 1 Static Header Banner
    static_header_banner = models.ImageField(
        upload_to='labs/promotions/banners/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
        help_text='1 Static Header Banner for Verified Lab (Growth) plan'
    )
    static_banner_link = models.URLField(blank=True, null=True, help_text='Optional destination link when clicking the banner')

    # Pro Plan Media: Video
    promotional_video_url = models.URLField(
        blank=True,
        null=True,
        help_text='Promotional video link (YouTube / Vimeo / Direct MP4) for Trusted Partner (Pro) plan'
    )

    # Pro Plan CTAs & Direct Contact Channels (Customer end)
    direct_phone = models.CharField(max_length=25, blank=True, null=True, help_text='Direct Phone number for Instant Call CTA')
    whatsapp_number = models.CharField(max_length=25, blank=True, null=True, help_text='WhatsApp Number (with country code)')
    enable_instant_rfq = models.BooleanField(default=True, help_text='Enable Instant RFQ button on profile')

    # Pro Plan Privacy & Competitor controls
    hide_reviews = models.BooleanField(default=False, help_text='Trusted Partner labs can hide reviews on customer page')

    class Meta:
        verbose_name = 'Lab Plan Subscription'
        verbose_name_plural = 'Lab Plan Subscriptions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.lab.lab_name} - {self.plan.name} ({self.get_status_display()})"

    def activate_subscription(self):
        """Activates subscription upon payment/approval, expiring previous active subscriptions."""
        LabPlanSubscription.objects.filter(lab=self.lab, is_current=True).exclude(pk=self.pk).update(is_current=False)
        self.status = 'active'
        self.payment_status = 'paid'
        self.is_current = True
        self.starts_at = timezone.now()
        self.expires_at = timezone.now() + timezone.timedelta(days=self.plan.billing_period_days)
        self.save()


class LabPromotionBanner(Trackable):
    """
    Carousel Banners (Up to 3) for Trusted Partner (Pro) plan.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(LabPlanSubscription, on_delete=models.CASCADE, related_name='carousel_banners')
    image = models.ImageField(
        upload_to='labs/promotions/carousel/',
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])]
    )
    title = models.CharField(max_length=150, blank=True)
    subtitle = models.CharField(max_length=255, blank=True)
    target_url = models.URLField(blank=True, null=True)
    sort_order = models.PositiveSmallIntegerField(default=1, help_text='Sort sequence: 1, 2, or 3')
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Lab Carousel Banner'
        verbose_name_plural = 'Lab Carousel Banners'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"Banner #{self.sort_order} for {self.subscription.lab.lab_name}"


class LabAddonPurchase(Trackable):
    """
    Lab purchase of an add-on product (Category Featured Pin, Competitor Targeting, Home Page Listing).
    """
    STATUS_CHOICES = (
        ('pending', 'Pending Payment / Verification'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lab = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='addon_purchases')
    addon = models.ForeignKey(PromotionalAddon, on_delete=models.PROTECT, related_name='purchases')
    
    # Targeting specifications
    target_category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='targeted_addon_promotions',
        help_text='Target sample/test category for Category Featured Lab Pin or Competitor Targeting'
    )
    target_country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    target_state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Competitor Targeting
    target_competitor_lab = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='targeted_by_competitor_ads',
        help_text='Target competitor lab profile to display top banner on'
    )

    # Banner / Ad Creative
    banner_image = models.ImageField(
        upload_to='labs/promotions/addons/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
        help_text='Ad Banner creative'
    )
    banner_headline = models.CharField(max_length=200, blank=True)
    banner_link = models.URLField(blank=True, null=True)

    # Pricing & Duration
    price_paid = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        verbose_name = 'Lab Add-on Purchase'
        verbose_name_plural = 'Lab Add-on Purchases'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.lab.lab_name} - {self.addon.name} ({self.status})"
