# apps/labs/admin.py
from django.contrib import admin
from django.utils import timezone
from import_export.admin import ImportExportModelAdmin
from import_export.admin import ImportExportMixin, ImportExportModelAdmin
from django.db import models
from apps.utility.models import AccreditationMaster
from django_json_widget.widgets import JSONEditorWidget


from .models import (
    BranchImage, BranchItem, BranchManpower, LabCategory, LabCategoryField, LabSocialLink, LabWebPage, LegalIdProofDocType, LabAddressProofDocType, Branch,
    Accreditation, ManpowerRoleDepartment, ManpowerRoles, ProductService, TestingPackage, TestingScopeFacility,
    LabConfiguration, BranchManpowerPermission
)


@admin.register(LegalIdProofDocType)
class LegalIdProofDocTypeAdmin(admin.ModelAdmin):
    list_display = ('type_name',)
    search_fields = ('type_name',)


@admin.register(LabAddressProofDocType)
class LabAddressProofDocTypeAdmin(admin.ModelAdmin):
    list_display = ('type_name',)
    search_fields = ('type_name',)


class AccreditationInline(admin.TabularInline):
    model = Accreditation
    extra = 0
    fields = ('accred', 'certificate_no', 'validity_from', 'validity_to', 'active')
    raw_id_fields = ('accred',)



class ChildLabInline(admin.TabularInline):
    """Shows a parent lab's child labs directly on its admin page."""
    model = Branch
    fk_name = 'parent'
    extra = 0
    fields = ('lab_name',)
    readonly_fields = ('lab_name',)
    can_delete = False
    verbose_name = 'Child Laboratory'
    verbose_name_plural = 'Child Labs'

    def has_add_permission(self, request, obj=None):
        return False  # child labs are created via registration/approval, not added inline


@admin.register(Branch)
class LabAdmin(ImportExportModelAdmin):
    list_display = (
        'lab_name', 'lab_code', 'BIS_code', 'NABL_code', 'lab_hierarchy_type', 'parent', 'status', 'approval_status',
        'lab_city', 'lab_state', 'lab_region', 'is_public',
        'source', 'vista_tenant_id',
    )
    list_filter = (
        'source','status', 'approval_status', 'lab_region', 'is_public',
        'lab_state', 'lab_country', 'departments','created_at'
    )
    search_fields = (
        'lab_name', 'BIS_code', 'NABL_code', 'lab_code')
    raw_id_fields = ()
    filter_horizontal =  ('departments',)
    readonly_fields = ('id', 'created_at', 'updated_at','vista_tenant_id')
    inlines = [AccreditationInline, ChildLabInline]
    list_per_page = 50

    # fieldsets = (
    #     (None, {'fields': ('lab_name', 'user', 'lab_code', 'BIS_code', 'NABL_code', 'lab_logo', 'cover_picture')}),
    #     ('Hierarchy & Approval', {
    #         'fields': ('lab_hierarchy_type', 'parent', 'status', 'approval_status'),
    #     }),
    #     ('Classification', {'fields': ('testing_types', 'departments', 'lab_region', 'discipline', 'group_name', 'sub_group_name')}),
    #     ('Location', {
    #         'fields': ('lab_address', 'lab_city', 'lab_district', 'lab_state', 'lab_country', 'lab_pincode',
    #                    'latitude', 'longitude', 'website_url'),
    #     }),
    #     # ('Organization & Compliance', {
    #     #     'fields': ('org_type', 'org_name', 'gst_number', 'nabl_testing_accred_num', 'nabl_calibration_accred_num'),
    #     # }),
    #     ('Contact', {'fields': ('contact_email', 'contact_mobile')}),
    #     ('Platform', {'fields': ('is_public', 'subscription_expires_at', 'source')}),
    # )
    exclude = ('created_by', 'updated_by', 'cancel_cheque', 'bank_cancel_cheque_file', 'bank_cancel_cheque_file_objectId',
               'bank_account_number', 'bank_ifsc_code', 'bank_account_name', 'bank_branch_name')
    raw_id_fields = ('user', 'lab_state', 'lab_country','lab_district','parent',
                     'registered_office_country','registered_office_state','registered_office_district')


    actions = ['mark_approved', 'mark_pending']

    @admin.action(description="Mark selected labs as Approved")
    def mark_approved(self, request, queryset):
        queryset.update(approval_status='approved')

    @admin.action(description="Mark selected labs as Pending")
    def mark_pending(self, request, queryset):
        queryset.update(approval_status='pending')



@admin.register(LabWebPage)
class LabWebPageAdmin(admin.ModelAdmin):
    list_display = ('id','title','lab','parent','menu_order',)
    search_fields = ('lab__lab_name',)
    raw_id_fields = ('lab','parent')
    exclude = ('created_by','updated_by')


@admin.register(LabSocialLink)
class LabSocialLinkAdmin(admin.ModelAdmin):
    list_display = ('id','lab','platform','url','is_active')
    search_fields = ('lab__lab_name',)
    raw_id_fields = ('lab',)
    exclude = ('created_by','updated_by')
    list_filter = ('platform','is_active')

@admin.register(ProductService)
class ProductServiceAdmin(admin.ModelAdmin):
    list_display = ('id','lab', 'name', 'summary', 'source_url')
    search_fields = ('lab__lab_name',)
    raw_id_fields = ('lab',)
    exclude = ('created_by','updated_by')
    list_filter = ('lab','is_active')

# @admin.register(LabParentApprovalRequest)
# class LabParentApprovalRequestAdmin(admin.ModelAdmin):
#     list_display = ('requesting_lab', 'parent_lab', 'status', 'decided_by', 'decided_at', 'created_at')
#     list_filter = ('status',)
#     search_fields = ('requesting_lab__lab_name', 'parent_lab__lab_name')
#     raw_id_fields = ('requesting_lab', 'parent_lab', 'decided_by')
#     readonly_fields = ('id', 'created_at', 'updated_at', 'decided_at')

#     actions = ['approve_requests', 'reject_requests']

#     @admin.action(description="Approve selected requests")
#     def approve_requests(self, request, queryset):
#         for req in queryset.filter(status='pending'):
#             req.approve()

#     @admin.action(description="Reject selected requests")
#     def reject_requests(self, request, queryset):
#         for req in queryset.filter(status='pending'):
#             req.reject(reason="Rejected via admin bulk action.")




# @admin.register(LabWebsiteCrawl)
# class LabWebsiteCrawlAdmin(admin.ModelAdmin):
#     list_display = ('lab', 'source_url', 'status', 'applied_to_profile', 'started_at', 'finished_at')
#     list_filter = ('status', 'applied_to_profile')
#     search_fields = ('lab__lab_name', 'source_url')
#     raw_id_fields = ('lab',)
#     readonly_fields = (
#         'id', 'created_at', 'updated_at', 'started_at', 'finished_at', 'applied_at',
#         'extracted_about_us', 'extracted_products', 'extracted_services', 'extracted_contact',
#     )

#     actions = ['apply_to_profile']

#     @admin.action(description="Apply extracted data to the lab profile (only fills blank fields)")
#     def apply_to_profile(self, request, queryset):
#         for crawl in queryset.filter(status='success', applied_to_profile=False):
#             crawl.apply_to_lab_profile()



@admin.register(AccreditationMaster)
class AccreditationMasterAdmin(admin.ModelAdmin):
    list_display = ('id','name','short_code','order')

@admin.register(Accreditation)
class AccreditationAdmin(admin.ModelAdmin):
    list_display = ('lab', 'accred', 'certificate_no', 'validity_from', 'validity_to', 'active', 'is_expired')
    list_filter = ('active', 'accred', 'exclude_failed_parameter')
    search_fields = ('certificate_no', 'lab__lab_name')
    raw_id_fields = ('lab', 'accred')
    readonly_fields = ('id', 'created_at', 'updated_at')



class BranchManpowerPermissionInline(admin.StackedInline):
    model = BranchManpowerPermission
    can_delete = True
    extra = 0
    verbose_name = "Portal Repository Permissions"
    verbose_name_plural = "Portal Repository Permissions"


@admin.register(BranchManpower)
class BranchManpowerAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ['id', 'user', 'lab', 'designation',
                    'is_deleted', 'created_at', 'updated_at']
    search_fields = ('lab__lab_name', 'user__username', 'designation',)
    raw_id_fields = ('lab', 'created_by', 'updated_by')
    list_filter = ('is_deleted', 'tags')
    inlines = [BranchManpowerPermissionInline]


@admin.register(ManpowerRoleDepartment)
class ManpowerRoleDepartmentAdmin(ImportExportMixin, admin.ModelAdmin):
    list_display = ['id', 'lab', 'group', 'get_departments',
                    'validity', 'created_at', 'updated_at']

    def get_departments(self, obj):
        return [department.name for department in obj.departments.all()]


@admin.register(ManpowerRoles)
class ManpowerRolesAdmin(admin.ModelAdmin):
    list_display = ["id", "manpower", "role", "default_role",
                    'get_department', "order", "get_current_department"]
    list_filter = ('manpower', 'role')

    def get_department(self, obj):
        try:
            department_list = []
            for dept in obj.role.departments.all():
                department_list.append(dept.name)
            return department_list
        except Exception as e:
            return "-"

    get_department.short_description = 'Departments'

    def get_current_department(self, obj):
        try:
            if obj.role.active_department:
                return obj.role.active_department.name
        except Exception as e:
            return "-"

    get_current_department.short_description = "Current Department"


@admin.register(TestingPackage)
class TestingPackageAdmin(ImportExportModelAdmin):
    list_display = ['id', 'lab', 'name', 'description', 'is_active', 'created_at', 'updated_at']
    list_filter = ('is_active', 'lab')
    search_fields = ('lab__lab_name', 'lab__user__username', 'name')
    raw_id_fields = ('lab',)
    show_full_result_count = True
    

@admin.register(BranchItem)
class BranchItemAdmin(ImportExportModelAdmin):
    list_display = ['id', 'is_number', 'is_title', 'sub_group', 'lab',  'disable_at', 'created_at', 'updated_at']
    list_filter = ('test_type','lab',)
    search_fields = ('lab__lab_name', 'lab__user__username')
    raw_id_fields = ('lab', 'created_by', 'updated_by')
    show_full_result_count = False

    def get_assigned_manpower(self, obj):
        try:
            assignee_list = []
            assignees = obj.responsibilities.all()
            for assignee in assignees:
                assignee_list.append(assignee.user.email)
            return assignee_list
        except Exception as e:
            return "-"

    get_assigned_manpower.short_description = 'Responsible manpower'


@admin.register(BranchImage)
class BranchImageAdmin(ImportExportModelAdmin):
    list_display = ['id', 'lab', 'image', 'is_active', 'created_at', 'updated_at']
    list_filter = ('is_active', 'lab')
    search_fields = ('lab__lab_name', 'lab__user__username')
    raw_id_fields = ('lab', )
    show_full_result_count = False
    exclude = ('created_by', 'updated_by')


@admin.register(TestingScopeFacility)
class TestingScopeFacilityAdmin(admin.ModelAdmin):
    list_display = ['id', 'lab', 'clause_no', 'title', 'is_active', 'created_at', 'updated_at']
    list_filter = ('is_active', 'lab')
    search_fields = ('lab__lab_name', 'lab__user__username')
    raw_id_fields = ('lab', 'scope', 'additional_scopes')
    show_full_result_count = False
    exclude = ('created_by', 'updated_by')


@admin.register(LabCategory)
class LabCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget},
    }

@admin.register(LabCategoryField)
class LabCategoryFieldAdmin(admin.ModelAdmin):
    list_display = ('id','category','field_key')


@admin.register(LabConfiguration)
class LabConfigurationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'branch', 'plan_tier',
        'new_lead_received', 'customer_messages', 'weekly_performance_summary',
        'product_platform_updates', 'show_pricing_publicly', 'hide_from_competing_labs',
        'is_deactivated', 'created_at', 'updated_at'
    )
    list_filter = (
        'plan_tier', 'new_lead_received', 'customer_messages', 'weekly_performance_summary',
        'product_platform_updates', 'show_pricing_publicly', 'hide_from_competing_labs', 'is_deactivated'
    )
    search_fields = ('branch__lab_name', 'branch__lab_code', 'branch__contact_email')
    raw_id_fields = ('branch',)


@admin.register(BranchManpowerPermission)
class BranchManpowerPermissionAdmin(admin.ModelAdmin):
    list_display = (
        'get_member_name', 'get_member_email', 'get_member_designation', 'branch', 'role', 'status',
        'can_manage_leads', 'can_manage_orders', 'can_manage_scope',
        'can_manage_profile', 'can_manage_reviews', 'can_view_analytics', 'can_manage_settings',
        'created_at'
    )
    list_filter = (
        'role', 'status',
        'can_manage_leads', 'can_manage_orders', 'can_manage_scope',
        'can_manage_profile', 'can_manage_reviews', 'can_view_analytics', 'can_manage_settings'
    )
    search_fields = ('manpower__user__username', 'manpower__user__email', 'manpower__designation', 'branch__lab_name')
    raw_id_fields = ('branch', 'manpower')

    def get_member_name(self, obj):
        return obj.name
    get_member_name.short_description = "Name"

    def get_member_email(self, obj):
        return obj.email
    get_member_email.short_description = "Email"

    def get_member_designation(self, obj):
        return obj.designation
    get_member_designation.short_description = "Company Designation"
