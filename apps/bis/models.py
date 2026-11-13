from django.db import models


from django.core.validators import RegexValidator

from apps.utility.models import Trackable, pincode_regex, phone_regex


ORGANIZATION_CHOICES = (
    ('1', 'Private Ltd.'),
    ('2', 'Public Ltd.'),
    ('3', 'Partnership'),
    ('4', 'Sole Proprietorship'),
    ('5', 'Government'),
    ('other', 'Other'),
)

APPLICATION_TYPE = (
    ('1', 'New'),
    ('2', 'Renewal'),
    ('3', 'Inclusion'),
    ('4', 'Exclusion'),
    ('5', 'Amendment'),
)

STATUS_CHOICES = (
    ('1', 'Pending'),
    ('2', 'Active'),
    ('3', 'Suspended'),
    ('4', 'In Review'),
    ('5', 'Activated'),
)
SUSPENDED_CHOICES = (
    ('1', 'Complain'),
    ('2', 'Address Change'),
    ('3', 'Other'),
)
# Create your models here.
REGIONS_CHOICES = (
    ("51","Eastern"),
    ("61","Southern"),
    ("71","Western"),
    ("81","Central"),
    ("91","Northern"),
)

DISCIPLINES_CHOICES = (
    ("0","MULTIPLE"),
    ("1","CHEMICAL"),
    ("2","ELECTRICAL"),
    ("3","MECHANCIAL"),
)

STATES = (
        (0, 'Open'),
        (1, 'Submitted'),
        (2, 'Pending'),
        (3, 'Received'),
        (4, 'Recorded'),
        (5, 'Audit Assigned'),
        (6, 'Audited'),
        (7, 'Recognized'),
        (8, 'Returned'),
        (9, 'Rejected'),
        (10, 'Reopen'),
        (11, 'Recommended for Rejection'),
        (12, 'Rejection Notice Sent'),
        (13, 'Derecognized'),
        (14, 'Suspension Requested'),
        (15, 'Suspended'),
        (16, 'Recommended for Recognition'),
        (17, 'Approved for Recognition'),
        (18, 'Deferred'),
        (19, 'Partially Suspended'),


    )

from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator










REQUEST_CHOICES = (
    # (0, 'New'),
    (1, 'Pending'),
    # (2, 'Returned'),
    (3, 'Completed'),
)




    # @transition(field=request_status, source=[1, 2], target=2)
    # def return_request(self):
    #     pass

  




class Laboratory(Trackable):
   

    # user = models.OneToOneField(settings.AUTH_USER_MODEL, db_index=True, related_name="laboratory_user",
    #                             verbose_name='User', on_delete=models.CASCADE)
    lab_id_no = models.CharField(
        max_length=100, blank=True, null=True, unique=True, verbose_name='Laboratory id No')
    bis_code = models.CharField(
        max_length=100, blank=True, null=True, verbose_name='BIS Code')
    osl_code = models.CharField(
        max_length=100, blank=True, null=True, verbose_name='OSL Code',help_text='region+serial_digits+discipline+osl_code_lab_type')
    osl_code_generated_at = models.DateTimeField(blank=True, null=True)    
    region = models.CharField(choices=REGIONS_CHOICES, max_length=100, blank=True, null=True)
    discipline = models.CharField(choices=DISCIPLINES_CHOICES, max_length=100, blank=True, null=True)
    serial_digits = models.PositiveIntegerField(blank=True, null=True)
    osl_code_lab_type = models.PositiveIntegerField(blank=True, null=True)
    # recognition_document = models.FileField(
    #     null=True, blank=True,
    #     upload_to='lab_recognition_document/', validators=[FileExtensionValidator(allowed_extensions=['pdf'])]
    # )
    lab_name = models.CharField(max_length=100, verbose_name='Laboratory Name')
    lab_recent_logo_photograph_objectId = models.CharField(
        max_length=255, blank=True, null=True
    )
    # lab_unique_qrcode_value = models.CharField(
    #     max_length=255,
    #     blank=True,
    #     null=True,
    #     unique=True,
    #     default=random_string_generator_qrcode
    # )
    cover_picture = models.ImageField(
        null=True, blank=True,
        upload_to='cover/', verbose_name="Recent Cover Photo",
        validators=[FileExtensionValidator(
            allowed_extensions=['png', 'jpg', 'jpeg'])]
    )
    lab_address = models.TextField(
        blank=True, null=True, verbose_name='Address')
    # lab_district = models.CharField(
    #     max_length=50, blank=True, null=True, verbose_name='District')
    # lab_city_new = models.TextField(blank=True, null=True)
    lab_district = models.CharField(
        max_length=200, db_column='lab_district_id', blank=True, null=True, verbose_name='District')
    lab_city = models.CharField(
        max_length=200, blank=True, null=True, verbose_name='City')
    lab_state = models.CharField(
        max_length=200, db_column='lab_state_id', blank=True, null=True, verbose_name='State')
    lab_country = models.CharField(
        max_length=200, db_column='lab_country_id', blank=True, null=True, verbose_name='Country')
    lab_zipcode = models.CharField(
        max_length=8, blank=True, null=True, verbose_name='Zip Code', validators=[pincode_regex])
    registered_office_same_as_lab = models.BooleanField(
        default=False, verbose_name="Same as laboratory")
    registered_office_address = models.TextField(
        blank=True, null=True, verbose_name="Address")
    registered_office_district = models.CharField(
        max_length=200, db_column='registered_office_district_id', blank=True, null=True, verbose_name='District')
    registered_office_city = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name="City")
    registered_office_state = models.CharField(
        max_length=200, db_column='registered_office_state_id', blank=True, null=True, verbose_name="State")
    registered_office_country = models.CharField(
        max_length=200, db_column='registered_office_country_id', blank=True, null=True, verbose_name="Country")
    registered_office_zipcode = models.CharField(
        max_length=8, blank=True, null=True, verbose_name="Zip Code", validators=[pincode_regex])
    registered_office_mobile1_dialcode = models.CharField(
        max_length=10, blank=True, null=True, verbose_name="Dialcode")
    registered_office_mobile1 = models.CharField(
        max_length=10, blank=True, null=True, verbose_name="Mobile Number", validators=[phone_regex])
    registered_office_telephone_dialcode = models.CharField(
        max_length=10, blank=True, null=True, verbose_name="Dialcode")
    registered_office_telephone_areacode = models.CharField(
        max_length=10, blank=True, null=True, verbose_name="Areacode")
    registered_office_telephone = models.CharField(
        max_length=10, null=True, blank=True, verbose_name="Telephone Number", validators=[phone_regex])
    registered_office_fax = models.CharField(
        max_length=10, blank=True, null=True, verbose_name="Fax", validators=[phone_regex])
    working_hours_start = models.CharField(
        max_length=20, null=True, blank=True, verbose_name="Working Hours Start")
    working_hours_end = models.CharField(
        max_length=20, null=True, blank=True, verbose_name="Working Hours End")
    working_days = models.CharField(
        max_length=55, null=True, blank=True, verbose_name="Working Day(s)")
    legal_id_proof_doc_type_other = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Other (Please Specify)")
    # legal_id_proof_doc_type = models.ForeignKey(
    #     LegalIdProofDocType, related_name="legal_doc", on_delete=models.CASCADE, blank=True, null=True,
    #     verbose_name="Proof of Legal Identity")
    legal_id_proof_doc_id = models.CharField(
        max_length=10, blank=True, null=True, verbose_name="Document ID (Optional)")
    legal_id_proof_doc_file = models.CharField(
        max_length=100, blank=True, null=True,
        verbose_name="Legal Identity Proof Document (in low resolution)")
    legal_id_proof_doc_file_objectId = models.CharField(
        max_length=50, blank=True, null=True)
    address_proof_doc_type_other = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Other (Please Specify)")
    # address_proof_doc_type = models.ForeignKey(LabAddressProofDocType, related_name="address_proof",
    #                                            on_delete=models.CASCADE, blank=True, null=True,
    #                                            verbose_name="Proof of Laboratory Address")
    address_proof_doc_id = models.CharField(
        max_length=10, blank=True, null=True, verbose_name="Document ID (Optional)")
    address_proof_doc_file = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Address Proof Document (in low resolution)")
    address_proof_doc_file_objectId = models.CharField(
        max_length=50, blank=True, null=True)
    top_management_doc_file = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Top Management Document")
    top_management_doc_file_objectId = models.CharField(
        max_length=50, blank=True, null=True)
    organization_type_other = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="Other (Please Specify)")
    organization_type = models.CharField(
        choices=ORGANIZATION_CHOICES, max_length=20, null=True, blank=True, verbose_name="Organization Type")
    organization_name = models.CharField(
        max_length=100, verbose_name='Organization Name', null=True, blank=True)
    organization_address = models.TextField(
        blank=True, null=True, verbose_name="Address")
    organization_district = models.CharField(
        max_length=200, db_column='organization_district_id', blank=True, null=True, verbose_name='District')
    organization_city = models.CharField(
        max_length=200, blank=True, null=True, verbose_name="City")
    organization_state = models.CharField(
        max_length=200, db_column='organization_state_id', blank=True, null=True, verbose_name="State")
    organization_country = models.CharField(
        max_length=200, db_column='organization_country_id', blank=True, null=True, verbose_name="Country")
    organization_zipcode = models.CharField(
        max_length=8, blank=True, null=True, verbose_name="Zip code", validators=[pincode_regex])
    organization_doc_other = models.CharField(
        max_length=20, blank=True, null=True, verbose_name="Oraganization Document")
    organization_office_same_as_lab = models.BooleanField(
        default=False, verbose_name="Same as laboratory")
    status = models.CharField(choices=STATUS_CHOICES,
                              max_length=20, default='1', verbose_name="Status")
    current_state_date = models.DateField(blank=True, null=True)
    application_type = models.CharField(
        choices=APPLICATION_TYPE, max_length=20, default='1')
    date_of_submission = models.DateField(blank=True, null=True)
    date_of_derecognized = models.DateField(blank=True, null=True)
    date_of_submission_backup = models.DateField(blank=True, null=True)
    date_of_recognition = models.DateField(blank=True, null=True)
    date_of_renewal_recognition = models.DateField(blank=True, null=True)
    date_of_expiration = models.DateField(blank=True, null=True)
    date_of_referred_back = models.DateField(blank=True, null=True)
    payment_status = models.BooleanField(default=False)
    Total_10IS_condition = models.BooleanField(default=False)
    renewalreferback_status = models.BooleanField(default=False)
    record_comment = models.TextField(blank=True, null=True)

    record_at = models.DateField(blank=True, null=True)
    
    
    follow_up = models.IntegerField(default=0, blank=True, null=True)
    lab_type = models.CharField(
        choices=(('bis', 'BIS'), ('nth', 'NTH'), ('government', 'Empanelled'), ('osl', 'OSL')), max_length=20, default='osl')
    bank_account_name = models.CharField(
        max_length=100, verbose_name='A/C Name', null=True, blank=True,)
    bank_account_number = models.CharField(
        max_length=18, verbose_name='A/C Number', null=True, blank=True,)
    bank_ifsc_code = models.CharField(
        max_length=11, verbose_name='Ifcs Code', null=True, blank=True,)
    bank_branch_name = models.CharField(
        max_length=150, verbose_name='Branch Name', null=True, blank=True,)
    bank_cancel_cheque_file = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Cancel Cheque")
    bank_cancel_cheque_file_objectId = models.CharField(
        max_length=50, blank=True, null=True)
    gst_number = models.CharField(
        max_length=15, verbose_name='GST Number', null=True, blank=True)
    suspended_reason = models.CharField(choices=SUSPENDED_CHOICES, blank=True, null=True,
                              max_length=20, default='1')
    suspended_start_date = models.DateField(blank=True, null=True)
    suspended_end_date = models.DateField(blank=True, null=True)
   
    certificate_doc_type = models.CharField(
        choices=(('1', 'Public'), ('2', 'Private'), ('3', 'Recognize')), max_length=20, default='1')
    certificate_doc_file = models.CharField(
        max_length=100, blank=True, null=True,
        )
    certificate_doc_file_objectId = models.CharField(
        max_length=50, blank=True, null=True)

    lab_logo = models.ImageField(upload_to='logos/lab/', blank=True, null=True)
    nabl_logo = models.ImageField(upload_to='logos/nabl/', blank=True, null=True)
    # nabl_logo_test = CustomImageField(upload_to='logos/nabl_test/', blank=True, null=True)
    # nabl_logo_test2 = CustomImageField(upload_to='logos/nabl_test/', blank=True, null=True)
    surveillance_type = models.CharField(
        choices=(('1', 'NO'), ('2', 'Yes'), ('3', 'Other')), max_length=20, default='1')
    renewal_status = models.CharField(
        choices=(
        ('0', 'Not Submitted'),
        ('1', 'Not Verified'), 
        ('2', 'Verified'), 
        ('3', 'Referred back'),
        ('4', 'Audited'),# Request created by Head
        ('5', 'Recommendation for Desktop Audited'),# DO Recommendation of Lab Desktop Audited for Head
        # ('6', 'Audit Approved'),    #
        ('7', 'Recommended for Renewal'),   
        ('8', 'Approved for Renewal'),
        ('9', 'Recommended for Renewal Rejection'),
        ('10','Renewal Rejection Notice Sent'),
        ('11', 'Renewal Recognition Payment Done'),
        ('12', 'Renewal Recognition Letter Generated'),
        ('13', 'Renewal Recognition Letter Approved'),
        ('14', 'Referred Back Renewal recommendation'), 
        ), max_length=100, default='0')
    renewal_payment_status = models.BooleanField(default=False)
    disable_sample_flow = models.BooleanField(default=False)    # If True then lab should not be returned in lab suggestion api # This field is used for bis labs only.
    do_not_show_in_lab_suggestion = models.TextField(blank=True, null=True, verbose_name="Don’t show in lab suggestions (BIS ids)", help_text="Enter Comma Separated BIS ids without space")    # This field is used for bis labs only.
    
    annual_testing_target = models.IntegerField(blank=True, null=True)  # for bis labs MCR only 
    partial_suspended = models.BooleanField(default=False)
    recommendation_for_rejection = models.BooleanField(default=False)
    lab_rejection_notice_sent = models.BooleanField(default=False)
    recognition_payment_status = models.BooleanField(default=False)
    renewal_recognition_payment_status = models.BooleanField(default=False)
    date_of_expiration_old = models.DateField(blank=True, null=True)
    is_msme_women_entrepreneurs = models.BooleanField(default=False)    # Micro, Women and Small Scale Industries
    is_stqc = models.BooleanField(default=False) 
    state = models.IntegerField(default=0)
    # lab_scale = models.CharField(max_length=20, choices=LAB_SCALE, blank=True, null=True)

    class Meta:
        verbose_name = 'Laboratory'
        verbose_name_plural = 'Laboratories'
        default_permissions = ()
        permissions = (
            ('laboratory_all', 'Laboratory All'),
            ('assign_laboratory', 'Can Assign Laboratory'),
            ('view_assigned_laboratory', 'Can View Assigned Laboratory'),
            ('adequate_laboratory', 'Can Adequate Laboratory'),
            ('approve_laboratory', 'Can Approve Laboratory'),
            ('can_review_laboratory', 'Can Review Laboratory'),
            # ('receive_laboratory', 'Can Receive Laboratory'),
            ('record_laboratory', 'Can Record Laboratory'),
            ('view_recorded_laboratory', 'Can View Recorded Laboratory'),
            ('assign_audit', 'Can Assign Lab Audit'),
            ('view_assign_audit', 'Can View Lab Audit'),
            ('assign_scope', 'Can Assign Scope'),
            ('approve_scope_assignment', 'Can Approve Scope Assignment'),
            ('adequate_scope', 'Can Adequate Scope'),
            ('approve_scope', 'Can Approve Scope'),
            ('recommend_lab_rejection', 'Can Recommend Laboratory for Rejection'),
            ('reject_lab', 'Can Reject Laboratory'),
            ('view_rejected_labs', 'Can View Rejected Labs'),
            ('review_notice_appeal', 'Can Review Notice Appeal'),
            ('view_surveillance_labs', 'Can View Surveillance Labs'),
            ('view_surveillance_audits_approval', 'Can View Surveillance Audits Approval'),
            ('view_assigned_scope_request', 'Can View Assigned Scope Requests'),

            # ('received_lab_list', 'Can View Received Lab List'),
            # ('recorded_lab_list', 'Recorded Lab List'),
        )
        db_table = 'lrs_laboratory'

class TestingType(models.Model):
    name = models.CharField(max_length=255)
    for_bis = models.BooleanField(default=True)
    for_osl = models.BooleanField(default=True)
    for_government = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.name}'

    class Meta:
        verbose_name = 'Testing Types'
        verbose_name_plural = 'Testing Types'
        default_permissions = ()

class ClauseNumberRange(Trackable):
    range_min = models.FloatField()
    range_max = models.FloatField()


class ManHourRate(models.Model):
    hour_rate = models.FloatField()

    def __str__(self):
        return f'{self.hour_rate}'

    class Meta:
        verbose_name = 'Man Hour Rate'
        verbose_name_plural = 'Man Hour Rates'
        default_permissions = ()


class ISNumber(models.Model):
    sort_order = models.CharField(max_length=100, blank=True, null=True)
    bis_id = models.PositiveIntegerField(default=0)
    is_number = models.CharField(max_length=255, blank=True, null=True,db_index=True)
    is_title = models.TextField(blank=True, null=True)
    ''' for Product start '''
    # prod_code = models.CharField(max_length=100, blank=True, null=True) # not in use
    is_prod = models.BooleanField(default=False, verbose_name="Is Product?")
    product_id = models.IntegerField(blank=True, null=True)
    variety_name = models.CharField(max_length=255, blank=True, null=True)
    component_name = models.CharField(max_length=255, blank=True, null=True)
    sub_component_name = models.CharField(max_length=255, blank=True, null=True)
    ''' for Product end '''    
    doc_prefix = models.CharField(max_length=255, blank=True, null=True)
    doc_no = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    part = models.CharField(max_length=255, blank=True, null=True)
    section = models.CharField(max_length=255, blank=True, null=True)
    year = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    amendments = models.IntegerField(blank=True, null=True, default=0, validators=[MinValueValidator(0)])
    bis_charges = models.FloatField(blank=True, null=True)
    all_india_first = models.BooleanField(default=False)
    aif_enable_date = models.DateTimeField(blank=True, null=True)
    all_india_first_archived = models.BooleanField(default=False)
    aif_archived_date = models.DateTimeField(blank=True, null=True)
    bo_name = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True,blank=True, null=True)
   

    class Meta:
        # unique_together = ('is_number', 'part', 'section', 'year')
        verbose_name = 'IS Numbers'
        verbose_name_plural = 'IS Numbers'
        default_permissions = ()


class ClauseNumber(Trackable):
    is_number = models.ForeignKey(ISNumber, on_delete=models.CASCADE)
    clause_no = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    man_hour_rate = models.ForeignKey(
        ManHourRate, on_delete=models.CASCADE, blank=True, null=True)
    testing_type = models.ManyToManyField(
        TestingType, verbose_name="Type of Test", blank=True)
    parameter = models.TextField(blank=True, null=True)
    man_hours = models.FloatField(blank=True, null=True)
    electricity_cost = models.FloatField(blank=True, null=True)
    consumables_cost = models.FloatField(blank=True, null=True)
    requirement = models.CharField(max_length=255, blank=True, null=True)  ### Not in use
    range = models.ManyToManyField(ClauseNumberRange, blank=True)
    range_unit = models.CharField(max_length=255, blank=True, null=True)
    
    range_minimum = models.FloatField(blank=True, null=True) # shows in clause test repor popup by default 
    range_value = models.FloatField(blank=True, null=True) 
    range_maximum = models.FloatField(blank=True, null=True) # shows in clause test repor popup by default 
    status = models.CharField(max_length=255, blank=True, null=True)
    is_disable = models.BooleanField(default=False)  # True means disable
    result_type = models.CharField(
        max_length=20, choices=(('Qualitative', 'Qualitative'), ('Quantitative', 'Quantitative')),
        blank=True, null=True)
    testing_description = models.TextField(blank=True, null=True)
    optimum_testing_time = models.PositiveIntegerField(blank=True, null=True)
    long_term_test = models.BooleanField(default=False)
    

    class Meta:
        # unique_together = ('is_number', 'clause_no')
        verbose_name = 'Clause Numbers'
        verbose_name_plural = 'Clause Numbers'
        default_permissions = ()

    def __str__(self):
        if self.parameter:
            return f'{str(self.clause_no)} ({self.parameter})'

        return str(self.clause_no)

    def save(self, *args, **kwargs):
        if self.range_maximum or self.range_minimum:
            self.result_type = 'Quantitative'
        super().save(*args, **kwargs)

    # def clean(self):

    #     if self.range_unit == '' and self.requirement == '':
    #         raise ValidationError('Please insert Either Requirement or Range')

    #     if (self.range_unit != '' or self.range_minimum != '' or self.range_maximum !='') and (self.requirement == ''):
    #         raise ValidationError('Please insert value in all Range Unit, Range Minimum and Range Maximum')


SCOPE_STATUS_CHOICES = (
    ('1', 'Pending Review'), # using
    ('2', 'Approved'), # using
    # ('3', 'Inclusion (Pending Review)'),# Not in use
    # ('4', 'Amendment (Pending Review)'),# Not in use
    # ('5', 'Deletion (Pending Review)'),# Not in use
    ('6', 'Deleted Scope'), # using
    # ('7', 'Not Adequate'),# Not in use
    # ('8', 'Adequate'),# Not in use
    # ('9', 'Deletion Disapproved'),# Not in use
    # ('10', 'Resent Application'), # Not in use
    # ('11', 'Draft'),  # Not in use
    # ('12', 'Suspension Requested'), # Not in use
    ('13', 'Suspended'), # using
)

SCOPE_STATE_CHOICES = (
    ('1', 'Pending Review'),
    ('2', 'Approved'),
    ('3', 'Inclusion (Pending Review)'),
    ('4', 'Amendment (Pending Review)'),
    ('5', 'Deletion (Pending Review)'),
    ('6', 'Deleted Scope'),
    ('7', 'Not Adequate'),
    ('8', 'Adequate'),
    ('9', 'Deletion Disapproved'),
    ('10', 'Resent Application'),
    ('11', 'Draft'),
    ('12', 'Suspension Requested'),
    ('13', 'Suspended'),
)




ACTION_WHILE = (
    ('red_form','Red Form'),
    ('yellow_form','Yellow Form'),
    ('blue_form','Blue Form'),
    ('clause_disable','Clause Disable Functionality')
)


class LaboratoryScopes(Trackable):
    lab = models.ForeignKey(
        Laboratory, on_delete=models.CASCADE, related_name='lab_scope')
    is_number = models.ForeignKey(
        ISNumber, on_delete=models.CASCADE, blank=True, null=True, verbose_name="Indian Standard Number")
    is_title = models.CharField(max_length=25, blank=True, null=True)
    part = models.CharField(max_length=50, blank=True, null=True)
    section = models.CharField(
        max_length=150, blank=True, null=True, verbose_name='Part / Section')
    year = models.CharField(max_length=4, blank=True, null=True)
    amendments = models.IntegerField(
        blank=True, null=True, default=0, validators=[MinValueValidator(0)])
    grade = models.CharField(max_length=255, blank=True, null=True,
                             verbose_name="Grade / Type / Size / Designation etc.")
    grade_by_do = models.CharField(max_length=255, blank=True, null=True,
                             verbose_name="Grade Suggested by DO")
    testing_type = models.ManyToManyField(
        TestingType, verbose_name="Fields of Testing Applicable")
    testing_days = models.IntegerField(blank=True, null=True, validators=[
        MinValueValidator(0)], verbose_name="Testing Time for Each Sample")
    testing_capacity = models.IntegerField(blank=True, null=True, validators=[
        MinValueValidator(0)], verbose_name="Testing Capacity per month")
    capacity_multiplying_factor = models.FloatField(default=1.0,validators=[MinValueValidator(1.0)])
    testing_capacity_by_lrmd = models.IntegerField(blank=True, null=True, validators=[
        MinValueValidator(0)], verbose_name="Testing Capacity by LRMD")
    remarks = models.TextField(blank=True, null=True)
    delete_remarks = models.TextField(blank=True, null=True)
    red_form_remarks = models.TextField(blank=True, null=True)  ##### by DO    
    yellow_form_remarks = models.TextField(blank=True, null=True)
    scope_pdf_remarks = models.TextField(blank=True, null=True)
    test_exclusion = models.CharField(max_length=255, blank=True, null=True)
    complete_testing_charge = models.CharField(max_length=55, blank=True, null=True)
    test_charges_remarks = models.TextField(blank=True, null=True)
    is_refrence_material = models.BooleanField(blank=True, null=True, verbose_name="Reference Material is Not Applicable")
    is_facilities_unavailable = models.BooleanField(blank=True, null=True, verbose_name="All Facilities are available")
    is_exclusions = models.BooleanField(blank=True, null=True, verbose_name="Exclusion is Not Applicable")
    status = models.BooleanField(default=False)
    scope_status = models.CharField(
        max_length=20, default='1', choices=SCOPE_STATUS_CHOICES, blank=True, null=True)
    scope_state = models.CharField(
        max_length=20, default='1', choices=SCOPE_STATE_CHOICES, blank=True, null=True)
    payment_status = models.BooleanField(default=False, blank=True, null=True)
    # requestid = models.ForeignKey('lrs.RequestModel',on_delete=models.SET_NULL, blank=True, null=True, related_name='scope_request_id')
    # deletion_status = models.BooleanField(default=False)
    is_complete = models.BooleanField(default=False,verbose_name="Is Complete Facility") # default is Partial
    is_complete_remarks = models.TextField(blank=True, null=True, verbose_name="Partial/Complete remarks")
    partial_suspended = models.BooleanField(default=False)
    partial_suspended_at = models.DateField(
        blank=True, null=True, verbose_name="Suspended Date")
    disable = models.BooleanField(default=False)
    disable_at = models.DateField(
        blank=True, null=True, verbose_name="Disable Date")
    is_active = models.BooleanField(default=True)
    disable_while = models.CharField(max_length=50, choices=ACTION_WHILE, blank=True, null=True)
    recent_inclusion = models.BooleanField(default=False)
   

    def __str__(self):
        return str(self.pk)

    class Meta:
        verbose_name = 'Laboratory Scopes'
        verbose_name_plural = 'Laboratory Scopes'
        default_permissions = ()
  