"""构建完整评测数据集：规则级标注 + 案件 + 保单 + 产品 + 药单 + 理算 + 审核"""
import json, datetime
from django.core.management.base import BaseCommand
from django.conf import settings

SCHEMA = "claim-special-medicine-core"

def clean(obj):
    if obj is None: return None
    if isinstance(obj, (datetime.datetime, datetime.date)): return str(obj)
    if isinstance(obj, (int, float, str, bool)): return obj
    if isinstance(obj, dict): return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list): return [clean(v) for v in obj]
    return str(obj)

class Command(BaseCommand):
    help = "Build complete evaluation dataset from old system"

    def handle(self, **options):
        import psycopg2
        conn = psycopg2.connect(settings.READONLY_DB_URL, client_encoding='UTF8')
        conn.set_client_encoding('UTF8')
        cur = conn.cursor()

        # 1. Pull rule-level annotations
        self.stdout.write("1/8 Pulling rule-level annotations...")
        cur.execute(f"""
            SELECT ad.id, ad.case_id, ad.brand_name, ad.generic_name,
                   ad.audit_point, ad.audit_result, ad.point_result,
                   ad.manual_review, ad.analyse_result, ad.audit_point_detail,
                   ad.indication, ad.modify_desc
            FROM "{SCHEMA}".if_attachment_audit_detail ad
            WHERE ad.manual_review IS NOT NULL
        """)
        annots = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        case_ids = list(set(a['case_id'] for a in annots))
        self.stdout.write(f"   {len(annots)} annotations, {len(case_ids)} cases")

        # 2. Pull case data in batches
        self.stdout.write("2/8 Pulling case data...")
        cases = {}
        for i in range(0, len(case_ids), 500):
            chunk = case_ids[i:i+500]
            ph = ','.join(['%s']*len(chunk))
            cur.execute(f"SELECT * FROM \"{SCHEMA}\".if_case WHERE id IN ({ph})", chunk)
            for r in cur.fetchall():
                d = dict(zip([c[0] for c in cur.description], r))
                cases[str(d['id'])] = d
        self.stdout.write(f"   {len(cases)} cases")

        # 3. Pull policy data
        self.stdout.write("3/8 Pulling policy data...")
        policy_ids = list(set(c.get('policy_id') for c in cases.values() if c.get('policy_id')))
        policies = {}
        for i in range(0, len(policy_ids), 500):
            chunk = policy_ids[i:i+500]
            ph = ','.join(['%s']*len(chunk))
            cur.execute(f"SELECT * FROM \"{SCHEMA}\".if_policy WHERE id IN ({ph})", chunk)
            for r in cur.fetchall():
                d = dict(zip([c[0] for c in cur.description], r))
                policies[str(d['id'])] = d
        self.stdout.write(f"   {len(policies)} policies")

        # 4. Pull policy insurance data (coverage, deductible)
        self.stdout.write("4/8 Pulling policy insurance data...")
        policy_insurances = {}
        for i in range(0, len(policy_ids), 500):
            chunk = policy_ids[i:i+500]
            ph = ','.join(['%s']*len(chunk))
            cur.execute(f"SELECT * FROM \"{SCHEMA}\".if_policy_insurance WHERE policy_id IN ({ph})", chunk)
            for r in cur.fetchall():
                d = dict(zip([c[0] for c in cur.description], r))
                policy_insurances[str(d['policy_id'])] = d
        self.stdout.write(f"   {len(policy_insurances)} policy insurances")

        # 5. Pull insurance product data (赔付比例等)
        self.stdout.write("5/8 Pulling product liability data...")
        project_ids = list(set(c.get('project_id') for c in cases.values() if c.get('project_id')))
        products = {}
        for i in range(0, len(project_ids), 50):
            chunk = project_ids[i:i+50]
            ph = ','.join(['%s']*len(chunk))
            cur.execute(f"SELECT * FROM \"{SCHEMA}\".if_insurance WHERE project_id IN ({ph})", chunk)
            for r in cur.fetchall():
                d = dict(zip([c[0] for c in cur.description], r))
                products[str(d['id'])] = d
        self.stdout.write(f"   {len(products)} products")

        # Pull project details
        projects = {}
        for i in range(0, len(project_ids), 50):
            chunk = project_ids[i:i+50]
            ph = ','.join(['%s']*len(chunk))
            cur.execute(f"SELECT * FROM \"{SCHEMA}\".if_project_details WHERE id IN ({ph})", chunk)
            for r in cur.fetchall():
                d = dict(zip([c[0] for c in cur.description], r))
                projects[str(d['id'])] = d
        self.stdout.write(f"   {len(projects)} projects")

        # 6. Pull product→drug mapping (药单) — filter by project_code
        self.stdout.write("6/11 Pulling product drug list (if_drug_rel)...")
        project_codes = list(set(p.get('project_code','') for p in projects.values() if p.get('project_code')))
        drug_rel = []
        for i in range(0, len(project_codes), 200):
            chunk = project_codes[i:i+200]
            ph = ','.join(['%s']*len(chunk))
            cur.execute(f"SELECT * FROM \"{SCHEMA}\".if_drug_rel WHERE product_id IN ({ph})", chunk)
            for r in cur.fetchall():
                drug_rel.append(dict(zip([c[0] for c in cur.description], r)))
        self.stdout.write(f"   {len(drug_rel)} drug rel records (for {len(project_codes)} project codes)")

        # 7. Pull case drug audit points (案件药品审核要点)
        self.stdout.write("7/11 Pulling case drug audit points...")
        cur.execute(f"""
            SELECT * FROM \"{SCHEMA}\".if_case_drug_point
            WHERE case_id IN ({','.join(['%s']*len(case_ids))})
        """, case_ids)
        case_drug_points = {}
        for r in cur.fetchall():
            d = dict(zip([c[0] for c in cur.description], r))
            cid = str(d['case_id'])
            if cid not in case_drug_points: case_drug_points[cid] = []
            case_drug_points[cid].append(d)
        self.stdout.write(f"   {len(case_drug_points)} cases with drug audit points")

        # 8. Pull per-audit-point detail (审核要点明细)
        self.stdout.write("8/11 Pulling audit point details...")
        cur.execute(f"""
            SELECT * FROM \"{SCHEMA}\".if_attachment_audit_point_detail
            WHERE attachment_audit_detail_id IN (
                SELECT id FROM \"{SCHEMA}\".if_attachment_audit_detail
                WHERE case_id IN ({','.join(['%s']*len(case_ids))})
            )
        """, case_ids)
        audit_point_details = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
        self.stdout.write(f"   {len(audit_point_details)} audit point details")

        # 9. Pull case drugs + diagnosis
        self.stdout.write("9/11 Pulling case drugs + diagnosis...")
        case_drugs = {}
        for i in range(0, len(case_ids), 500):
            chunk = case_ids[i:i+500]
            ph = ','.join(['%s']*len(chunk))
            cur.execute(f"SELECT * FROM \"{SCHEMA}\".if_case_drug WHERE case_id IN ({ph})", chunk)
            for r in cur.fetchall():
                d = dict(zip([c[0] for c in cur.description], r))
                cid = str(d['case_id'])
                if cid not in case_drugs: case_drugs[cid] = []
                case_drugs[cid].append(d)

        diagnostics = {}
        for i in range(0, len(case_ids), 500):
            chunk = case_ids[i:i+500]
            ph = ','.join(['%s']*len(chunk))
            cur.execute(f"SELECT * FROM \"{SCHEMA}\".if_diagnostic_info WHERE case_id IN ({ph})", chunk)
            for r in cur.fetchall():
                d = dict(zip([c[0] for c in cur.description], r))
                diagnostics[str(d['case_id'])] = d
        self.stdout.write(f"   {len(case_drugs)} cases with drugs, {len(diagnostics)} with diagnosis")

        # 7. Pull audit trail
        self.stdout.write("10/11 Pulling audit trail...")
        audits = {}
        for i in range(0, len(case_ids), 500):
            chunk = case_ids[i:i+500]
            ph = ','.join(['%s']*len(chunk))
            cur.execute(f"SELECT * FROM \"{SCHEMA}\".if_case_audit WHERE case_id IN ({ph}) ORDER BY audit_time", chunk)
            for r in cur.fetchall():
                d = dict(zip([c[0] for c in cur.description], r))
                cid = str(d['case_id'])
                if cid not in audits: audits[cid] = []
                audits[cid].append(d)
        self.stdout.write(f"   {len(audits)} cases with audit trail")

        # 8. Pull drug indications + algorithms
        self.stdout.write("11/11 Pulling drug indications + algorithms...")
        cur.execute(f"SELECT * FROM \"{SCHEMA}\".if_drug_diseases")
        drug_indications = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]

        cur.execute(f"SELECT * FROM \"{SCHEMA}\".if_duty_algorithm")
        algorithms = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]

        cur.execute(f"SELECT * FROM \"{SCHEMA}\".if_drug_info")
        drug_catalog = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]

        self.stdout.write(f"   {len(drug_indications)} indications, {len(algorithms)} algorithms, {len(drug_catalog)} drugs")

        # Assemble final dataset
        self.stdout.write("\nAssembling dataset...")
        dataset = {
            'metadata': {
                'total_annotations': len(annots),
                'total_cases': len(cases),
                'total_policies': len(policies),
                'total_products': len(products),
                'total_projects': len(projects),
                'annotated_cases': len(case_ids),
                'extraction_date': str(datetime.date.today()),
            },
            'annotations': clean(annots),
            'cases': clean(cases),
            'policies': clean(policies),
            'policy_insurances': clean(policy_insurances),
            'products': clean(products),
            'projects': clean(projects),
            'case_drugs': clean(case_drugs),
            'diagnostics': clean(diagnostics),
            'audits': clean(audits),
            'drug_rel': clean(drug_rel),
            'case_drug_points': clean(case_drug_points),
            'audit_point_details': clean(audit_point_details),
            'drug_indications': clean(drug_indications),
            'algorithms': clean(algorithms),
            'drug_catalog': clean(drug_catalog),
        }

        # Save
        import os
        out_path = os.path.join(settings.BASE_DIR, 'data', 'eval_full_dataset.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, ensure_ascii=False)

        file_size = os.path.getsize(out_path) / 1024 / 1024
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Saved: {out_path} ({file_size:.1f} MB)\n"
            f"   {len(annots)} annotations × {len(case_ids)} cases\n"
            f"   + {len(policies)} policies + {len(products)} products\n"
            f"   + {len(case_drugs)} case_drugs + {len(audits)} audit_trails\n"
            f"   + {len(drug_indications)} indications + {len(algorithms)} algorithms"
        ))

        cur.close()
        conn.close()
