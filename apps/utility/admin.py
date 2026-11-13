# apps/core/admin.py
from django.contrib import admin
from .models import (
    Country, Discipline, District, State, TagType, Tag, Role, EquipmentType, Department, Profile,
)
from import_export.admin import ImportExportMixin, ImportExportModelAdmin
from import_export import resources

class CountryResource(resources.ModelResource):
    class Meta:
        model = Country
        skip_unchanged = True
        report_skipped = True

@admin.register(Country)
class CountryAdmin(ImportExportMixin,admin.ModelAdmin):
    resource_class = CountryResource
    list_display = ('name', 'code')
    search_fields = ('name',)
    exclude = ('created_by','updated_by')


class StateResource(resources.ModelResource):
    class Meta:
        model = State
        skip_unchanged = True
        report_skipped = True

@admin.register(State)
class StateAdmin(ImportExportMixin,admin.ModelAdmin):
    resource_class = StateResource
    list_display = ('id','name', 'country')
    search_fields = ('name',)
    raw_id_fields = ('country',)
    exclude = ('created_by','updated_by')
    list_filter = ('country',)


class DistrictResource(resources.ModelResource):
    class Meta:
        model = District
        skip_unchanged = True
        report_skipped = True

@admin.register(District)
class DistrictAdmin(ImportExportMixin,admin.ModelAdmin):
    resource_class = DistrictResource
    list_display = ('id','name','state')
    search_fields = ('name',)
    raw_id_fields = ('state',)
    exclude = ('created_by','updated_by')
    list_filter = ('state',)


# class CityResource(resources.ModelResource):
#     class Meta:
#         model = City
#         skip_unchanged = True
#         report_skipped = True

# @admin.register(City)
# class CityAdmin(ImportExportMixin,admin.ModelAdmin):
#     resource_class = CityResource
#     list_display = ('name', 'district')
#     raw_id_fields = ('district',)    
#     exclude = ('created_by','updated_by')



# @admin.register(TagType)
# class TagTypeAdmin(admin.ModelAdmin):
#     list_display = ('name',)
#     search_fields = ('name',)


# @admin.register(Tag)
# class TagAdmin(admin.ModelAdmin):
#     list_display = ('name', 'type')
#     list_filter = ('type',)
#     search_fields = ('name',)
#     autocomplete_fields = ('type',)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


# @admin.register(EquipmentType)
# class EquipmentTypeAdmin(admin.ModelAdmin):
#     list_display = ('name', 'active')
#     list_filter = ('active',)
#     search_fields = ('name',)


# @admin.register(AccreditationMaster)
# class AccreditationMasterAdmin(admin.ModelAdmin):
#     list_display = ('name', 'short_code', 'active')
#     list_filter = ('active',)
#     search_fields = ('name', 'short_code')


# @admin.register(EducationDegree)
# class EducationDegreeAdmin(admin.ModelAdmin):
#     list_display = ('name',)
#     search_fields = ('name',)


# @admin.register(Brand)
# class BrandAdmin(admin.ModelAdmin):
#     list_display = ('name', 'active')
#     list_filter = ('active',)
#     search_fields = ('name',)


# @admin.register(Unit)
# class UnitAdmin(admin.ModelAdmin):
#     list_display = ('name', 'active', 'created_at')
#     list_filter = ('active',)
#     search_fields = ('name', 'desc')
#     exclude = ('created_by', 'updated_by')  # set automatically via save_model, not hand-picked in UI
#     readonly_fields = ('created_at', 'updated_at')

#     def save_model(self, request, obj, form, change):
#         if not change:
#             obj.created_by = request.user
#         obj.updated_by = request.user
#         super().save_model(request, obj, form, change)


# @admin.register(GST)
# class GSTAdmin(admin.ModelAdmin):
#     list_display = ('name', 'country', 'tax_type', 'tax', 'active')
#     list_filter = ('tax_type', 'active', 'country')
#     search_fields = ('name',)
#     autocomplete_fields = ('country',)
#     exclude = ('created_by', 'updated_by')
#     readonly_fields = ('created_at', 'updated_at')

#     def save_model(self, request, obj, form, change):
#         if not change:
#             obj.created_by = request.user
#         obj.updated_by = request.user
#         super().save_model(request, obj, form, change)


@admin.register(Discipline)
class DisciplineAdmin(ImportExportMixin,admin.ModelAdmin):
    list_display = ('name','code','order','is_active','created_at', 'updated_at','created_by', 'updated_by')
    search_fields = ('name', 'code')
    exclude = ('created_by', 'updated_by') 
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Department)
class DepartmentAdmin(ImportExportMixin,admin.ModelAdmin):
    list_display = ('name', 'code', 'discipline', 'department_type', 'is_active', 'is_testing_type', 'order')
    list_filter = ('department_type', 'discipline', 'is_active', 'is_testing_type')
    search_fields = ('name', 'code')
    exclude = ('created_by', 'updated_by') 
    readonly_fields = ('created_at', 'updated_at')




@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'verified_by_admin', 'mobile', 'gender', 'order')
    list_filter = ('verified_by_admin', 'gender', 'temp_groups')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 'mobile')
    raw_id_fields = ('user',)
    filter_horizontal = ('temp_groups',)
    exclude = ('password_changed',)  # system-managed, not hand-edited from admin
