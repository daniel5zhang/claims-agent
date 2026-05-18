"""导入评测数据集 JSON → SQLite"""
import json
from decimal import Decimal
from datetime import datetime
from django.core.management.base import BaseCommand
from apps.evaluation.models import EvalAnnotation, EvalCase, EvalPolicy, EvalProduct, EvalAudit, EvalDrugRel, EvalCaseDrugPoint, EvalAuditPointDetail

def parse_dt(v):
    if not v: return None
    try: return datetime.fromisoformat(str(v).replace('Z',''))
    except: return None

def parse_dec(v):
    if v is None: return None
    try: return Decimal(str(v))
    except: return None

class Command(BaseCommand):
    help = "Import eval_full_dataset.json into SQLite"

    def handle(self, **options):
        path = 'data/eval_full_dataset.json'
        self.stdout.write(f'Loading {path}...')
        with open(path, encoding='utf-8') as f:
            data = json.load(f)

        # Annotations
        self.stdout.write('Importing annotations...')
        EvalAnnotation.objects.all().delete()
        batch = []
        for d in data['annotations']:
            ar = d.get('analyse_result')
            if isinstance(ar, dict):
                analyse = ar
            elif isinstance(ar, str) and ar.strip():
                try: analyse = json.loads(ar)
                except: analyse = None
            else:
                analyse = None
            batch.append(EvalAnnotation(
                annotation_id=str(d['id']), case_id=str(d.get('case_id','')),
                brand_name=d.get('brand_name'), generic_name=d.get('generic_name'),
                audit_point=d.get('audit_point'), audit_result=str(d.get('audit_result','')),
                point_result=str(d.get('point_result','')), manual_review=str(d.get('manual_review','')),
                analyse_result=analyse,
                audit_point_detail=d.get('audit_point_detail'), indication=d.get('indication'),
                modify_desc=d.get('modify_desc'),
            ))
            if len(batch) >= 500:
                EvalAnnotation.objects.bulk_create(batch); batch = []
        if batch: EvalAnnotation.objects.bulk_create(batch)
        self.stdout.write(f'  {EvalAnnotation.objects.count()} annotations')

        # Cases
        self.stdout.write('Importing cases...')
        EvalCase.objects.all().delete()
        batch = []
        for cid, d in data['cases'].items():
            batch.append(EvalCase(
                case_id=cid, inner_case_no=d.get('inner_case_no'), insured_id=str(d.get('insured_id','')),
                project_id=str(d.get('project_id','')), claim_status=d.get('claim_status'),
                report_date=parse_dt(d.get('report_date')),
                pay_total=parse_dec(d.get('pay_total')), claim_total=parse_dec(d.get('claim_total')),
                preexisting_disease=d.get('preexisting_disease'), raw_data=d,
            ))
            if len(batch) >= 500:
                EvalCase.objects.bulk_create(batch); batch = []
        if batch: EvalCase.objects.bulk_create(batch)
        self.stdout.write(f'  {EvalCase.objects.count()} cases')

        # Policies
        self.stdout.write('Importing policies...')
        EvalPolicy.objects.all().delete()
        batch = []
        for pid, d in data['policies'].items():
            batch.append(EvalPolicy(
                policy_id=pid, policy_no=d.get('policy_no'), project_id=str(d.get('project_id','')),
                insurance_start_time=parse_dt(d.get('insurance_start_time')),
                insurance_end_time=parse_dt(d.get('insurance_end_time')), raw_data=d,
            ))
            if len(batch) >= 500:
                EvalPolicy.objects.bulk_create(batch); batch = []
        if batch: EvalPolicy.objects.bulk_create(batch)
        self.stdout.write(f'  {EvalPolicy.objects.count()} policies')

        # Products
        self.stdout.write('Importing products...')
        EvalProduct.objects.all().delete()
        batch = []
        for pid, d in data['products'].items():
            batch.append(EvalProduct(
                product_id=pid, project_id=str(d.get('project_id','')),
                insurance_liability=d.get('insurance_liability'),
                pre_existing_disease_ratio=parse_dec(d.get('pre_existing_disease_ratio')),
                not_pre_existing_disease_ratio=parse_dec(d.get('not_pre_existing_disease_ratio')),
                deductible_excess=parse_dec(d.get('deductible_excess')),
                waiting_period=d.get('waiting_period'), algorithm_id=d.get('algorithm_id'),
                raw_data=d,
            ))
            if len(batch) >= 500:
                EvalProduct.objects.bulk_create(batch); batch = []
        if batch: EvalProduct.objects.bulk_create(batch)
        self.stdout.write(f'  {EvalProduct.objects.count()} products')

        # Audits
        self.stdout.write('Importing audits...')
        EvalAudit.objects.all().delete()
        batch = []
        for cid, audits in data['audits'].items():
            for d in audits:
                batch.append(EvalAudit(
                    case_id=cid, audit_type=d.get('audit_type'),
                    audit_conclusion=d.get('audit_conclusion'),
                    audit_opinion=d.get('audit_opinion'), auditor=d.get('auditor'),
                    audit_time=parse_dt(d.get('audit_time')), raw_data=d,
                ))
                if len(batch) >= 500:
                    EvalAudit.objects.bulk_create(batch); batch = []
        if batch: EvalAudit.objects.bulk_create(batch)
        self.stdout.write(f'  {EvalAudit.objects.count()} audit records')

        # DrugRel
        self.stdout.write('Importing drug_rel...')
        EvalDrugRel.objects.all().delete()
        batch = []
        for d in data.get('drug_rel', []):
            batch.append(EvalDrugRel(
                product_id=str(d.get('product_id','')), drug_id=str(d.get('drug_id','')),
                third_drug_common_name=d.get('third_drug_common_name'),
                third_drug_name=d.get('third_drug_name'),
                third_spec=d.get('third_spec'), reimbursement_type=d.get('reimbursement_type'),
                raw_data=d,
            ))
            if len(batch) >= 500: EvalDrugRel.objects.bulk_create(batch); batch = []
        if batch: EvalDrugRel.objects.bulk_create(batch)
        self.stdout.write(f'  {EvalDrugRel.objects.count()} drug rels')

        # CaseDrugPoints
        self.stdout.write('Importing case drug points...')
        EvalCaseDrugPoint.objects.all().delete()
        batch = []
        for cid, points in data.get('case_drug_points', {}).items():
            for d in points:
                batch.append(EvalCaseDrugPoint(
                    case_id=cid, product_drug_list_option_id=str(d.get('product_drug_list_option_id','')),
                    drug_id=str(d.get('drug_id','')), auditor=d.get('auditor'),
                    audit_point_conclusion=str(d.get('audit_point_conclusion','')),
                    type_of_audit_np=d.get('type_of_audit_np'), audit_detail=d.get('audit_detail'),
                    raw_data=d,
                ))
                if len(batch) >= 500: EvalCaseDrugPoint.objects.bulk_create(batch); batch = []
        if batch: EvalCaseDrugPoint.objects.bulk_create(batch)
        self.stdout.write(f'  {EvalCaseDrugPoint.objects.count()} case drug points')

        # AuditPointDetails
        self.stdout.write('Importing audit point details...')
        EvalAuditPointDetail.objects.all().delete()
        batch = []
        for d in data.get('audit_point_details', []):
            batch.append(EvalAuditPointDetail(
                attachment_audit_detail_id=str(d.get('attachment_audit_detail_id','')),
                sku_id=str(d.get('sku_id','')), audit_point=d.get('audit_point'),
                audit_detail=d.get('audit_detail'), audit_result=str(d.get('audit_result','')),
                manual_review=str(d.get('manual_review','')), not_pass_type=d.get('not_pass_type'),
                review_detail=d.get('review_detail'), raw_data=d,
            ))
            if len(batch) >= 500: EvalAuditPointDetail.objects.bulk_create(batch); batch = []
        if batch: EvalAuditPointDetail.objects.bulk_create(batch)
        self.stdout.write(f'  {EvalAuditPointDetail.objects.count()} audit point details')

        self.stdout.write(self.style.SUCCESS('Import complete'))
