from django.contrib import admin
from .models import Website, AnalysisJob, Page, PageLink, PageAnalysis, Evidence, Fact, AnalysisResult

@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    list_display = ('domain', 'root_url', 'created_at', 'updated_at')
    search_fields = ('domain', 'root_url')
    ordering = ('-created_at',)

class AnalysisResultInline(admin.StackedInline):
    model = AnalysisResult
    extra = 0
    readonly_fields = ('created_at', 'updated_at')

@admin.register(AnalysisJob)
class AnalysisJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'website', 'objective', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'objective', 'created_at')
    search_fields = ('id', 'website__domain', 'error_code')
    ordering = ('-created_at',)
    inlines = [AnalysisResultInline]

@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ('id', 'website', 'page_type', 'url', 'quality_score', 'fetch_method', 'created_at')
    list_filter = ('page_type', 'fetch_method', 'created_at')
    search_fields = ('url', 'title', 'website__domain')
    ordering = ('-created_at',)

@admin.register(PageLink)
class PageLinkAdmin(admin.ModelAdmin):
    list_display = ('id', 'source_page', 'target_url', 'is_internal', 'created_at')
    list_filter = ('is_internal',)
    search_fields = ('target_url', 'anchor_text')

@admin.register(PageAnalysis)
class PageAnalysisAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'page', 'model_used', 'created_at')
    search_fields = ('job__id', 'page__url', 'model_used')

@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'page', 'char_start', 'char_end', 'verified', 'created_at')
    list_filter = ('verified',)

@admin.register(Fact)
class FactAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'category', 'field', 'value_short', 'confidence', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('category', 'field', 'value')

    def value_short(self, obj):
        return obj.value[:50] + '...' if len(obj.value) > 50 else obj.value
    value_short.short_description = 'Value'

@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'created_at', 'updated_at')
    search_fields = ('job__id', 'job__website__domain')
