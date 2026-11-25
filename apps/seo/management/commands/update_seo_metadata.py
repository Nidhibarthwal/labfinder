from django.core.management.base import BaseCommand
from apps.seo.services import update_bulk_seo_metadata


class Command(BaseCommand):
    help = "Bulk update SEO titles, descriptions, and headings across existing landing pages"

    def add_arguments(self, parser):
        parser.add_argument(
            "--page-type",
            type=str,
            default="category_city",
            help="Page type to update (default: category_city)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force update even for customized pages",
        )

    def handle(self, *args, **options):
        self.stdout.write(f"Bulk updating SEO metadata for page_type={options['page_type']}...")
        count = update_bulk_seo_metadata(
            page_type=options["page_type"],
            force=options["force"],
        )
        self.stdout.write(self.style.SUCCESS(f"Successfully updated metadata for {count} pages."))
