from django.core.management.base import BaseCommand
from apps.seo.services import generate_bulk_seo_pages


class Command(BaseCommand):
    help = "Bulk generate programmatic SEO landing pages from Category and Branch locations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-labs",
            type=int,
            default=3,
            help="Minimum number of laboratories required to generate an SEO page (minimum enforced: 3; allowed tiers: 3, 5, 10, 20, 50)",
        )
        parser.add_argument(
            "--overwrite-customized",
            action="store_true",
            help="Force overwrite of manually customized SEO pages",
        )

    def handle(self, *args, **options):
        self.stdout.write("Generating bulk programmatic SEO landing pages from Category and Branch tables...")
        res = generate_bulk_seo_pages(
            min_labs_threshold=options["min_labs"],
            overwrite_customized=options["overwrite_customized"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Done! Created: {res['created']}, Updated: {res['updated']}, Deactivated: {res['deactivated']}"
            )
        )
