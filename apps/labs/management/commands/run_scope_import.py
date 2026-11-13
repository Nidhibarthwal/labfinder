from django.core.management.base import BaseCommand
from django.db import transaction

from apps.nabl.models import NablLaboratoryScopes
from apps.services.product_scope_import import import_bis_scope, import_nabl_scope
# Import models and your functions here


# python manage.py run_scope_import --source=nabl --batch-size=1000


class Command(BaseCommand):
    help = "Processes NABL and BIS scope imports in chunked batches."

    def add_arguments(self, parser):
        parser.add_argument("--source", type=str, default="all", help="all, nabl, or bis")
        parser.add_argument("--batch-size", type=int, default=500, help="Records per chunk")

    def handle(self, *args, **options):
        source = options["source"].lower()
        batch_size = options["batch_size"]

        if source in ("all", "nabl"):
            self.import_nabl(batch_size)

        if source in ("all", "bis"):
            self.import_bis(batch_size)

    def import_nabl(self, batch_size):
        self.stdout.write("Starting NABL Batch Import...")
        total = NablLaboratoryScopes.objects.using("nabl").count()
        offset = 0

        while offset < total:
            scopes = NablLaboratoryScopes.objects.using("nabl").all().order_by("id")[offset : offset + batch_size]
            self.stdout.write(f"Processing NABL records {offset} to {offset + len(scopes)}...")
            print("scopes_count-------",scopes.count())
            counter = 0
            for scope in scopes:
                try:
                    # with transaction.atomic():
                    result = import_nabl_scope(scope)
                    if result['status'] == 'skipped':
                        print(f"=================={result['reason']}====================")
                        pass
                    else:
                        counter += 1
                except Exception as e:
                    self.stderr.write(f"Error on NABL Scope {scope.id}: {e}")
            print("counter-----------",counter)
            offset += batch_size

        self.stdout.write(self.style.SUCCESS("NABL Import completed successfully."))

    def import_bis(self, batch_size):
        from apps.bis.models import Laboratory

        self.stdout.write("Starting BIS Batch Import...")
        total = Laboratory.objects.count()
        offset = 0

        while offset < total:
            labs = Laboratory.objects.all().order_by("id")[offset : offset + batch_size]
            self.stdout.write(f"Processing BIS records {offset} to {offset + len(labs)}...")
            print("scopes_count-------",labs.count())
            counter = 0

            for lab in labs:
                try:
                    # with transaction.atomic():
                    result = import_bis_scope(lab)
                    if result['status'] == 'skipped':
                        print(f"=================={result['reason']}====================")
                        pass
                    else:
                        counter += 1
                except Exception as e:
                    self.stderr.write(f"Error on BIS Lab {lab.id}: {e}")

            print("counter-----------",counter)
            offset += batch_size

        self.stdout.write(self.style.SUCCESS("BIS Import completed successfully."))