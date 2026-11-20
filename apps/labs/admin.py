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
    LabConfiguration, BranchManpowerPermission,
    PromotionalPlan, PromotionalPlanFeature, PlanFeatureValue, PromotionalAddon,
    LabPlanSubscription, LabPromotionBanner, LabAddonPurchase
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


# ==============================================================================
# PROMOTIONAL PLANS & ADD-ONS ADMIN (figma-screens/promotional-packages.png & promotional-addon.png)
# ==============================================================================

class PlanFeatureValueInline(admin.TabularInline):
    """
    Allows superusers to add more features and customize values per plan.
    Matches: Packages features can be add by add more from admin panel from super user
    """
    model = PlanFeatureValue
    extra = 1
    fields = ('feature', 'value_text', 'is_included', 'sort_order')
    ordering = ('sort_order', 'feature__sort_order')
    autocomplete_fields = ('feature',)


@admin.register(PromotionalPlan)
class PromotionalPlanAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'slug', 'base_price', 'billing_period_days',
        'search_ranking_priority', 'trust_badge_type', 'banner_type',
        'is_active', 'sort_order'
    )
    list_editable = ('is_active', 'sort_order', 'base_price')
    list_filter = ('search_ranking_priority', 'trust_badge_type', 'banner_type', 'is_active')
    search_fields = ('name', 'slug', 'tagline')
    inlines = [PlanFeatureValueInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'tagline', 'base_price', 'billing_period_days', 'is_active', 'is_featured', 'sort_order')
        }),
        ('Search Ranking & Badge', {
            'fields': (
                'search_ranking_priority', 'priority_tier_level',
                'trust_badge_type', 'badge_label', 'requires_gst_license', 'requires_nabl_iso'
            )
        }),
        ('Promotional Banners & Video', {
            'fields': ('banner_type', 'max_header_banners', 'allow_video_banner')
        }),
        ('Direct Lead CTA Channels (Customer End)', {
            'fields': ('direct_cta_type', 'allow_direct_phone', 'allow_whatsapp', 'allow_instant_rfq')
        }),
        ('Visibility & Privacy Controls', {
            'fields': ('can_hide_reviews', 'hide_competitor_ads', 'monthly_shared_enquiries', 'is_unlimited_enquiries', 'home_page_listing')
        }),
    )


@admin.register(PromotionalPlanFeature)
class PromotionalPlanFeatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'sort_order', 'is_active')
    list_editable = ('sort_order', 'is_active')
    search_fields = ('name', 'code', 'description')
    prepopulated_fields = {'code': ('name',)}


@admin.register(PlanFeatureValue)
class PlanFeatureValueAdmin(admin.ModelAdmin):
    list_display = ('plan', 'feature', 'value_text', 'is_included', 'sort_order')
    list_filter = ('plan', 'is_included')
    search_fields = ('plan__name', 'feature__name', 'value_text')
    list_editable = ('value_text', 'is_included', 'sort_order')


@admin.register(PromotionalAddon)
class PromotionalAddonAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'code', 'tagging', 'base_price', 'max_price',
        'duration_days', 'max_inventory_slots', 'is_active', 'sort_order'
    )
    list_editable = ('is_active', 'base_price')
    list_filter = ('tagging', 'is_active')
    search_fields = ('name', 'code', 'placement', 'pricing_factor')
    prepopulated_fields = {'code': ('name',)}


class LabPromotionBannerInline(admin.TabularInline):
    model = LabPromotionBanner
    extra = 1
    fields = ('sort_order', 'image', 'title', 'subtitle', 'target_url', 'is_active')


@admin.register(LabPlanSubscription)
class LabPlanSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'lab', 'plan', 'status', 'verification_status', 'payment_status',
        'amount', 'is_current', 'starts_at', 'expires_at'
    )
    list_filter = ('status', 'verification_status', 'payment_status', 'plan', 'is_current')
    search_fields = (
        'lab__lab_name', 'gst_number', 'license_number',
        'nabl_accreditation_number', 'iso_certification_number', 'payment_reference'
    )
    raw_id_fields = ('lab', 'verified_by')
    inlines = [LabPromotionBannerInline]
    actions = ['approve_verification', 'reject_verification', 'activate_subscription_action']

    fieldsets = (
        ('Subscription Overview', {
            'fields': ('lab', 'plan', 'status', 'is_current', 'amount', 'payment_status', 'payment_reference', 'paid_at', 'starts_at', 'expires_at')
        }),
        ('Growth Plan Verification (GST / License)', {
            'fields': ('gst_number', 'license_number', 'gst_license_document')
        }),
        ('Pro Plan Verification (NABL / ISO)', {
            'fields': ('nabl_accreditation_number', 'nabl_document', 'iso_certification_number', 'iso_document')
        }),
        ('Verification Audit & Remarks', {
            'fields': ('verification_status', 'verification_remarks', 'verified_by', 'verified_at')
        }),
        ('Growth Plan Banner', {
            'fields': ('static_header_banner', 'static_banner_link')
        }),
        ('Pro Plan Media & Lead CTAs', {
            'fields': ('promotional_video_url', 'direct_phone', 'whatsapp_number', 'enable_instant_rfq', 'hide_reviews')
        }),
    )

    @admin.action(description="Approve verification for selected subscriptions")
    def approve_verification(self, request, queryset):
        queryset.update(
            verification_status='approved',
            verified_by=request.user,
            verified_at=timezone.now(),
            status='verified'
        )

    @admin.action(description="Reject verification for selected subscriptions")
    def reject_verification(self, request, queryset):
        queryset.update(
            verification_status='rejected',
            verified_by=request.user,
            verified_at=timezone.now(),
            status='rejected'
        )

    @admin.action(description="Activate selected subscriptions (Mark Paid & Active)")
    def activate_subscription_action(self, request, queryset):
        for sub in queryset:
            sub.activate_subscription()


@admin.register(LabAddonPurchase)
class LabAddonPurchaseAdmin(admin.ModelAdmin):
    list_display = (
        'lab', 'addon', 'target_category', 'price_paid',
        'status', 'starts_at', 'expires_at'
    )
    list_filter = ('addon', 'status')
    search_fields = ('lab__lab_name', 'payment_reference', 'banner_headline')
    raw_id_fields = ('lab', 'target_category', 'target_competitor_lab', 'target_country', 'target_state')

