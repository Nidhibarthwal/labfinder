import uuid
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, FileExtensionValidator
from django.db import models
from mptt.models import MPTTModel, TreeForeignKey

User = settings.AUTH_USER_MODEL

pincode_regex = RegexValidator(regex=r'^[a-zA-Z0-9 ]{3,10}$', message="Please enter a valid pincode")
TEXT_REGEX = RegexValidator(regex=r'^[\w\s.,\-&()/]+$', message="Enter a valid value.")
phone_regex = RegexValidator(regex=r'\d{1,10}', message="Please enter a valid phone number")
long_lat_regex = RegexValidator(regex=r'^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?),\s*[-+]?(180(\.0+)?|((1[0-7]\d)|([1-9]?\d))(\.\d+)?)$', message="Please enter a valid location")
pancard_regex = RegexValidator(regex=r'^[A-Z]{5}[0-9]{4}[A-Z]$', message="Please enter valid pancard")
variable_regex = RegexValidator(regex=r'^\{"eq-\d+": \["[a-zA-Z0-9_]{1,220}"(?:, "[a-zA-Z0-9_]{1,220}")\](?:, "manual": \["[a-zA-Z0-9_]{1,220}"(?:, "[a-zA-Z0-9_]{1,220}")\])?\}$', message="Please enter valid variable")
formula_regex = RegexValidator(regex=r'^\{"eq-\d+": \["[a-zA-Z0-9_]{1,220}"(?:, "[a-zA-Z0-9_]{1,220}")\](?:, "manual": \["[a-zA-Z0-9_]{1,220}"(?:, "[a-zA-Z0-9_]{1,220}")\])?\}$', message="Please enter valid formula")

GENDER_CHOICES = ((1, 'Male'), (2, 'Female'), (3, 'Other'))
EXPIRE_IN = (('30', '30 days'), ('60', '60 days'), ('90', '90 days'), ('never', 'Never'))


class Trackable(models.Model):
    """Mirrors Vista's Trackable abstract base: who/when created & modified."""
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='%(app_label)s_%(class)s_created')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='%(app_label)s_%(class)s_updated')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=5, blank=True, null=True)
    status = models.BooleanField(default=True)

    class Meta:
        default_permissions = ()

    def __str__(self):
        return self.name


class State(models.Model):
    name = models.CharField(max_length=100)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='states')
    status = models.BooleanField(default=True)

    class Meta:
        unique_together = ('name', 'country')
        default_permissions = ()

    def __str__(self):
        return self.name


class District(Trackable):
    name = models.CharField(max_length=50)
    state = models.ForeignKey(State, on_delete=models.CASCADE)
    status = models.BooleanField(default=True)

    class Meta:
        unique_together = ('state', 'name')
        verbose_name = 'District'
        verbose_name_plural = 'Districts'
        default_permissions = ()

    def __str__(self):
        return self.name


class City(Trackable):
    name = models.CharField(max_length=50)
    district = models.ForeignKey(District, on_delete=models.CASCADE)
    status = models.BooleanField(default=True)

    class Meta:
        unique_together = ('district', 'name')
        verbose_name = 'City'
        verbose_name_plural = 'Cities'
        default_permissions = ()

    def __str__(self):
        return self.name

class TagType(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=100)
    type = models.ForeignKey(TagType, on_delete=models.CASCADE, related_name='tags')

    def __str__(self):
        return self.name


class Role(models.Model):
    """Vista's Role master (distinct from django Group, used for lab manpower roles)."""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=30, blank=True, null=True)

    def __str__(self):
        return self.name


class TestingType(models.Model):
    """
    The high-level testing domain a lab operates in — Food Testing, Pathology,
    Footwear Testing, Equipment Calibration, etc. Selected first during lab
    profile setup, before the lab picks its Department(s) (see labs.Lab.departments).
    """
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=100, blank=True, null=True, help_text="Icon key/class for the portal UI.")
    active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
 
    class Meta:
        ordering = ['order', 'name']
 
    def __str__(self):
        return self.name
 

class EquipmentType(models.Model):
    name = models.CharField(max_length=150, unique=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class AccreditationMaster(models.Model):
    name = models.CharField(max_length=150, unique=True)   # e.g. NABL, BIS, SATRA
    vista_id = models.CharField(max_length=255, blank=True, null=True)
    short_code = models.CharField(max_length=20, blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class EducationDegree(models.Model):
    name = models.CharField(max_length=150, unique=True)

    def __str__(self):
        return self.name


class Brand(Trackable):
    """ model for create brand  """
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    country_of_origin = models.ForeignKey(Country, null=True, blank=True, on_delete=models.SET_NULL)
    established_year = models.PositiveIntegerField(null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    logo = models.ImageField(upload_to='brand_logos/', null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return "{}".format(self.name)


class Unit(Trackable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    desc = models.TextField(blank=True, null=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class GST(Trackable):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True)
    tax_type = models.CharField(choices=(("gst", "GST"), ("vat", "VAT")), max_length=20, blank=True, null=True)
    tax = models.FloatField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Discipline(Trackable):
    '''
    Its a broad scientific or technical domain under which
    lab get accreditation of NABL or ISO/IEC 17025 / ISO 15189.
    These are primary accreditation domains
    ex:
    Chemical
    Biological
    Mechanical
    Electrical
    Radiological
    '''
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=155, blank=True, null=True)
    order = models.PositiveIntegerField(default=1, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# class DepartmentType(models.Model):
#     name = models.CharField(max_length=100, unique=True)

#     def __str__(self):
#         return self.name
    
DEPARTMENT_TYPE_CHOICES = (
    ('lab', 'Lab'),
    ('administrative', 'Administrative'),
    ('MAO', 'MAO'),
    ('PLF', 'PLF'),
    ('PVC', 'PVC'),
    ('RPP', 'RPP'),
    ('TYF', 'TYF'),
    ('CWC', 'CWC')
)

class Department(MPTTModel):
# class Department(Trackable):
    '''
    NABL Department
    ❖ Chemical
    ❖ Biological
    ❖ Mechanical
    ❖ Electrical
    ❖ Electronics
    ❖ Fluid Flow
    ❖ Forensic
    ❖ Non-Destructive (NDT)
    ❖ Photometry
    ❖ Radiological
    ❖ Diagnostic Radiology QA Testing
    ❖ Software & IT System
    '''
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=300, unique=True)
    code = models.CharField(max_length=30, blank=True, null=True)
    discipline = models.ForeignKey(
        'Discipline',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='departments',
    )
    is_testing_type = models.BooleanField(default=False)
    is_sub_department = models.BooleanField(default=False)
    department_type = models.CharField(
        max_length=30, choices=DEPARTMENT_TYPE_CHOICES, default='lab')
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    order = models.PositiveIntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    # class MPTTMeta:
    #     order_insertion_by = ['name']

    class Meta:
        ordering = ['order', 'name']

    def clean(self):
        qs = Department.objects.filter(name__iexact=self.name)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.exists():
            raise ValidationError({
                'name': (
                    f'Department with name "{self.name}" already exists'
                    ' (case-insensitive check).'
                )
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.order is None:
            self.order = Department.objects.all().count() + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f'{self.name} ({self.discipline.name})'
            if self.discipline
            else self.name
        )


# class Category(Trackable):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     name = models.CharField(max_length=255)
#     slug = models.SlugField(max_length=180, unique=True)
#     code = models.CharField(max_length=30, blank=True, null=True)
#     department = models.ForeignKey(
#         'Department',
#         on_delete=models.SET_NULL, null=True, blank=True,
#         related_name='categories',
#     )
#     order = models.PositiveIntegerField(blank=True, null=True)
#     is_active = models.BooleanField(default=True)
#     description = models.TextField(blank=True)

#     class Meta:
#         ordering = ['order', 'name']
#         unique_together = ('department', 'name')

#     def __str__(self):
#         if self.department:
#             return f'{self.name} ({self.department.name})'
#         return self.name
class Profile(models.Model):
    """
    Same shape as Vista's Profile. `hasattr` checks in __str__ point at whichever
    related object LabFinder actually defines the reverse relation for
    (lab_user on Branch, customer_user on CustomerDetails) — trimmed vs Vista's
    bis_user/auditor since those roles don't exist on LabFinder's side.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_profile')
    verified_by_admin = models.BooleanField(default=True)
    temp_groups = models.ManyToManyField(
        Group, verbose_name='All Groups', blank=True,
        help_text='The groups this user belongs to. Only one is active at a time.',
        related_name="labfinder_user_temp_groups_set",
        related_query_name="labfinder_user",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.PositiveSmallIntegerField(choices=GENDER_CHOICES, blank=True, null=True)
    mobile = models.BigIntegerField(blank=True, null=True)
    password_expires_in = models.CharField(choices=EXPIRE_IN, max_length=20, blank=True, null=True)
    password_changed = models.DateTimeField(blank=True, null=True)
    alt_mobile = models.BigIntegerField(blank=True, null=True, verbose_name="Alternate Mobile Number",
                                         validators=[phone_regex])
    order = models.PositiveIntegerField(default=0)
    profile_pic = models.ImageField(
        upload_to='profile/', default='profile/default_pic.jpg', verbose_name='User Photograph',
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])]
    )

    def __str__(self):
        group = self.user.groups.all().first()
        role = group.name if hasattr(group, 'name') else 'N/A'
        if hasattr(self, 'lab_user'):
            return f'{self.lab_user.lab_name} ({role})'
        if hasattr(self, 'customer_user'):
            return f'{self.customer_user.first_name} {self.customer_user.last_name} ({role})'
        return f'{self.user.username} ({role})'

    def roles(self):
        return ",".join(str(p) for p in self.temp_groups.all())

    @property
    def selected_role(self):
        return self.user.groups.all().first()

    def has_group(self, group_name):
        return self.temp_groups.filter(name=group_name).exists()