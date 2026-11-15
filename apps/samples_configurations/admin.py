from django.contrib import admin
from import_export.admin import ImportExportMixin,ImportExportModelAdmin
from apps.samples_configurations.models import *

# Register your models here.


# @admin.register(TestingType)
# class TestingTypeAdmin(ImportExportModelAdmin):
#     list_display = ['id','name']


@admin.register(TRConfiguration)
class TrConfigurationAdmin(ImportExportModelAdmin):
    list_display = ['is_payment_applicable', 'is_verification_required', 'is_review_required']



# for parametat used 



@admin.register(ParameterRangeValue)
class ParameterRangeValueAdmin(admin.ModelAdmin):
    list_display = ['id', 'text', 'value_type', 'range_min', 'range_max', 'range_val']


@admin.register(TermsCondition)
class TermsConditionAdmin(ImportExportModelAdmin):
    list_display = ['terms_n_condition', 'active', 'order']






@admin.register(ServiceCategory)
class ServiceCategoryAdmin(ImportExportModelAdmin):
    list_display = ['id', 'name', 'order', 'description', 'active']
    search_fields = ('name',)


@admin.register(Category)
class CategoryAdmin(ImportExportModelAdmin):
    list_display = ['id', 'name', 'order', 'active']
    search_fields = ('name',)


@admin.register(SubCategory)
class SubCategoryAdmin(ImportExportModelAdmin):
    list_display = ['id', 'name', 'category', 'order', 'active']
    search_fields = ('name',)
    list_filter = ('category', 'active')


@admin.register(SampleClauseCategory)
class SampleClauseCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'order', 'active']
    search_fields = ('name',)


@admin.register(SampleClauseSubCategory)
class SampleClauseSubCategoryAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'category', 'order', 'active']
    search_fields = ('name',)


@admin.register(TestMethod)
class TestMethodAdmin(ImportExportModelAdmin):
    list_display = ['id', 'name', 'ref_no', 'created_at', 'updated_at','updated_by']
    search_fields = ('name', 'ref_no',)
    exclude = ('created_by','updated_by')


