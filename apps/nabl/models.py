from django.db import models

from apps.utility.models import Trackable

# Create your models here.

class NablLaboratory(Trackable):
    lab_id_no = models.CharField(max_length=30, blank=True, null=True, unique=True)
    lab_name = models.CharField(max_length=255, blank=True, null=True)
    standard = models.CharField(max_length=20, blank=True, null=True)
    assessment_types = models.CharField(max_length=50, blank=True, null=True)
    is_exten_date = models.CharField(max_length=50, blank=True, null=True)
    lab_type = models.CharField(max_length=50, blank=True, null=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_email = models.CharField(max_length=50, blank=True, null=True)
    contact_mobile = models.CharField(max_length=10, blank=True, null=True)
    prime_address = models.TextField(blank=True, null=True)
    country_id = models.CharField(max_length=10, blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    state = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    zone = models.CharField(max_length=10, blank=True, null=True)
    li_type_of_lab_by_service = models.CharField(max_length=50, blank=True, null=True)
    land_line = models.CharField(max_length=50, blank=True, null=True)
    pin = models.CharField(max_length=6, blank=True, null=True)
    fax = models.CharField(max_length=20, blank=True, null=True)
    cert_no = models.CharField(max_length=50, blank=True, null=True)
    issue_date = models.CharField(max_length=50, blank=True, null=True)
    extend_date = models.CharField(max_length=50, blank=True, null=True)
    to_date = models.CharField(max_length=50, blank=True, null=True)
    amendment_date = models.CharField(max_length=50, blank=True, null=True)
    certificate_url = models.URLField(blank=True, null=True)
    discipline_name = models.CharField(max_length=255, blank=True, null=True)
    group_name = models.TextField(blank=True, null=True)
    sub_grp_name = models.TextField(blank=True, null=True)
    permanent_facility = models.CharField(max_length=5, blank=True, null=True)
    site_facility = models.CharField(max_length=5, blank=True, null=True)
    mobile_facility = models.CharField(max_length=5, blank=True, null=True)
    osl_code = models.CharField(max_length=50, blank=True, null=True)
    whether_bis_lab = models.BooleanField(default=False)

    class Meta:
        db_table = 'lrs_nabllaboratory'

    def __str__(self):
        return "{}".format(self.lab_name)



class NablLaboratoryScopes(models.Model):
    lab_id = models.ForeignKey(NablLaboratory, blank=True, null=True, on_delete=models.CASCADE,
                               related_name='nabl_lab_scope')
    discipline = models.TextField(blank=True, null=True)
    product_material = models.TextField(blank=True, null=True)
    specific_test = models.TextField(blank=True, null=True)
    scope_year = models.TextField(blank=True, null=True)

    class Meta:
            db_table = 'lrs_nabllaboratoryscopes'

    def __str__(self):
        return "{}".format(self.lab_id)