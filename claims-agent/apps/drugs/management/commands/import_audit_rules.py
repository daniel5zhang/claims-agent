"""导入 450 条药品适应症审核要点"""
import json, uuid
from django.core.management.base import BaseCommand
from apps.drugs.models import Drug, DrugAuditPoint

class Command(BaseCommand):
    help = "Import drug-specific audit rules from audit_rules_extracted.json"

    def handle(self, **options):
        with open('data/audit_rules_extracted.json', encoding='utf-8') as f:
            data = json.load(f)

        DrugAuditPoint.objects.all().delete()
        created = 0
        skipped = 0

        drug_rules = data['drug_rules']
        for generic_name, indications in drug_rules.items():
            # Match drug by common_name
            drug = Drug.objects.filter(common_name=generic_name).first()
            if not drug:
                drug = Drug.objects.filter(common_name__icontains=generic_name[:4]).first()
            if not drug:
                skipped += len(indications)
                continue

            for indication, points in indications.items():
                for idx, p in enumerate(points, 1):
                    content = p['point'] if isinstance(p, dict) else str(p)
                    detail = p.get('detail','') if isinstance(p, dict) else ''
                    DrugAuditPoint.objects.create(
                        id=uuid.uuid4().hex,
                        drug=drug,
                        indication=indication[:256],
                        point_index=idx,
                        point_content=content[:2000],
                        point_detail=detail[:500] if detail else None,
                    )
                    created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Imported {created} audit points for {drug_rules.keys().__len__()} drugs ({skipped} skipped)'
        ))
