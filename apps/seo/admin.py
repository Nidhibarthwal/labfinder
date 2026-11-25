import csv
from django.contrib import admin
from django.http import HttpResponse

from .models import SEOTemplate, SEOLandingPage
from .services import update_bulk_seo_metadata


@admin.register(SEOTemplate)
class SEOTemplateAdmin(admin.ModelAdmin):
    list_display = ("page_type", "title_pattern", "h1_pattern", "is_active", "updated_at")
    list_filter = ("is_active", "page_type")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SEOLandingPage)
class SEOLandingPageAdmin(admin.ModelAdmin):
    list_display = (
        "slug",
        "category",
        "group_name",
        "city",
        "lab_count",
        "is_active",
        "is_customized",
        "updated_at",
    )
    list_filter = ("is_active", "is_customized", "page_type", "category", "group_name")
    search_fields = ("slug", "city", "group_name", "meta_title", "meta_description", "h1_heading")
    readonly_fields = ("created_at", "updated_at", "lab_count")
    actions = [
        "regenerate_metadata_from_template",
        "activate_pages",
        "deactivate_pages",
        "export_as_csv",
    ]

    @admin.action(description="Regenerate SEO metadata from active template for selected pages")
    def regenerate_metadata_from_template(self, request, queryset):
        count = update_bulk_seo_metadata(force=True)
        self.message_user(request, f"Successfully regenerated metadata for {count} pages.")

    @admin.action(description="Activate selected landing pages")
    def activate_pages(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Activated {updated} landing pages.")

    @admin.action(description="Deactivate selected landing pages (404/noindex)")
    def deactivate_pages(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} landing pages.")

    @admin.action(description="Export selected pages as CSV for SEO & Marketing teams")
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="seo_landing_pages.csv"'
        writer = csv.writer(response)
        writer.writerow(["slug", "city", "category", "lab_count", "meta_title", "meta_description", "h1_heading", "is_active"])
        for p in queryset:
            writer.writerow([
                p.slug,
                p.city,
                p.category.name if p.category else "",
                p.lab_count,
                p.meta_title,
                p.meta_description,
                p.h1_heading,
                p.is_active,
            ])
        return response
