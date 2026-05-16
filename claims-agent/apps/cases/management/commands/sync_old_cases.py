"""手工同步旧系统案件"""
from django.core.management.base import BaseCommand
from apps.cases.intake.old_system_adapter import OldSystemAdapter


class Command(BaseCommand):
    help = "Sync cases from old system"

    def add_arguments(self, parser):
        parser.add_argument("--case-ids", nargs="+", help="Case IDs to sync")
        parser.add_argument("--project-id", help="Filter by project")

    def handle(self, **options):
        adapter = OldSystemAdapter()
        filters = {}
        if options["case_ids"]:
            filters["case_ids"] = options["case_ids"]
        if options["project_id"]:
            filters["project_id"] = options["project_id"]
        cases = adapter.ingest(**filters)
        self.stdout.write(self.style.SUCCESS(f"Synced {len(cases)} cases"))
