"""Import 8 data types from readonly PostgreSQL to local SQLite"""
import psycopg2
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.drugs.models import Drug, DrugIndication
from apps.hospitals.models import Hospital
from apps.diseases.models import Disease
from apps.policies.models import Project, InsuranceProduct, CalculationAlgorithm
from apps.rules.models import PromptTemplate


import decimal

SCHEMA = "claim-special-medicine-core"


def safe_decimal(val):
    """Convert to Decimal, return None if invalid"""
    if val is None:
        return None
    try:
        return decimal.Decimal(str(val))
    except (decimal.InvalidOperation, ValueError):
        return None


class Command(BaseCommand):
    help = "Import reference data from readonly PostgreSQL DB"

    def handle(self, **options):
        db_url = settings.READONLY_DB_URL
        if not db_url:
            self.stderr.write("READONLY_DB_URL not configured")
            return

        conn = psycopg2.connect(db_url, client_encoding="UTF8")
        conn.set_client_encoding("UTF8")
        cur = conn.cursor()

        self._import_drugs(cur)
        self._import_drug_indications(cur)
        self._import_hospitals(cur)
        self._import_diseases(cur)
        self._import_projects(cur)
        self._import_insurance_products(cur)
        self._import_algorithms(cur)
        self._import_prompts(cur)

        cur.close()
        conn.close()
        self.stdout.write(self.style.SUCCESS("Import complete"))

    def _import_drugs(self, cur):
        cur.execute(f'SELECT * FROM "{SCHEMA}".if_drug_info')
        cols = [d[0] for d in cur.description]
        created = 0
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            Drug.objects.update_or_create(
                id=str(d["id"]),
                defaults={
                    "drug_code": d.get("drug_code"),
                    "common_name": d.get("common_name") or "",
                    "product_name": d.get("product_name"),
                    "drug_type": d.get("drug_type"),
                    "drug_category": d.get("drug_category"),
                    "is_original": bool(d.get("is_original")),
                    "is_first_drug": bool(d.get("is_first_drug")),
                    "is_overseas_medicine": bool(d.get("is_overseas_medicine")),
                    "target": d.get("target"),
                    "production_factory": d.get("production_factory"),
                },
            )
            created += 1
        self.stdout.write(f"  Drugs: {created}")

    def _import_drug_indications(self, cur):
        cur.execute(f'SELECT * FROM "{SCHEMA}".if_drug_diseases')
        cols = [d[0] for d in cur.description]
        created = 0
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            try:
                drug = Drug.objects.get(id=str(d["drug_id"]))
            except Drug.DoesNotExist:
                continue
            DrugIndication.objects.update_or_create(
                id=str(d["id"]),
                defaults={
                    "drug": drug,
                    "disease_name": d.get("cover_diseases") or "",
                    "specification_indication": d.get("specification_indication"),
                    "month_drug_cost": safe_decimal(d.get("month_drug_cost")),
                    "is_charity": bool(d.get("is_charity")),
                },
            )
            created += 1
        self.stdout.write(f"  DrugIndications: {created}")

    def _import_hospitals(self, cur):
        cur.execute(f'SELECT * FROM "{SCHEMA}".sys_hospital')
        cols = [d[0] for d in cur.description]
        created = 0
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            Hospital.objects.update_or_create(
                id=str(d["id"]),
                defaults={
                    "code": str(d.get("code") or d["id"]),
                    "name": d.get("name") or "",
                    "hospital_level": d.get("hospital_level"),
                    "hospital_nature": d.get("hospital_nature"),
                    "specialty_nature": d.get("specialty_nature"),
                    "province": d.get("province"),
                    "city": d.get("city"),
                    "district": d.get("district"),
                },
            )
            created += 1
        self.stdout.write(f"  Hospitals: {created}")

    def _import_diseases(self, cur):
        # ⚠️ column names have typos: dseases_name, dseases_code, diseases_type
        cur.execute(f'SELECT * FROM "{SCHEMA}".if_diseases_database')
        cols = [d[0] for d in cur.description]
        created = 0
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            Disease.objects.update_or_create(
                id=str(d["id"]),
                defaults={
                    "disease_name": d.get("dseases_name") or "",
                    "disease_code": d.get("dseases_code"),
                    "disease_type": d.get("diseases_type"),
                },
            )
            created += 1
        self.stdout.write(f"  Diseases: {created}")

    def _import_projects(self, cur):
        cur.execute(f'SELECT * FROM "{SCHEMA}".if_project_details')
        cols = [d[0] for d in cur.description]
        created = 0
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            Project.objects.update_or_create(
                id=str(d["id"]),
                defaults={
                    "project_code": d.get("project_code") or "",
                    "project_name": d.get("project_name") or "",
                    "company_name": d.get("company_name"),
                    "project_type": d.get("project_type"),
                    "claim_type": d.get("claim_type"),
                    "start_date": d.get("start_date"),
                    "end_date": d.get("end_date"),
                    "project_status": d.get("project_status") or "0",
                    "product_name": d.get("product_name"),
                },
            )
            created += 1
        self.stdout.write(f"  Projects: {created}")

    def _import_insurance_products(self, cur):
        cur.execute(f'SELECT * FROM "{SCHEMA}".if_insurance')
        cols = [d[0] for d in cur.description]
        created = 0
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            try:
                project = Project.objects.get(id=str(d["project_id"]))
            except Project.DoesNotExist:
                project = None
            InsuranceProduct.objects.update_or_create(
                id=str(d["id"]),
                defaults={
                    "project": project,
                    "insurance_code": d.get("insurance_code") or "",
                    "insurance_liability": d.get("insurance_liability"),
                    "duty_type": d.get("duty_type"),
                    "security_lines": safe_decimal(d.get("security_lines")),
                    "deductible_excess": safe_decimal(d.get("deductible_excess")),
                    "waiting_period": d.get("waiting_period"),
                    "algorithm_id": d.get("algorithm_id"),
                    "pre_existing_disease_ratio": safe_decimal(d.get("pre_existing_disease_ratio")),
                    "not_pre_existing_disease_ratio": safe_decimal(d.get("not_pre_existing_disease_ratio")),
                },
            )
            created += 1
        self.stdout.write(f"  InsuranceProducts: {created}")

    def _import_algorithms(self, cur):
        cur.execute(f'SELECT * FROM "{SCHEMA}".if_duty_algorithm')
        cols = [d[0] for d in cur.description]
        created = 0
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            CalculationAlgorithm.objects.update_or_create(
                id=str(d["id"]),
                defaults={
                    "algorithm_id": d.get("algorithm_id") or "",
                    "algorithm_logic": d.get("algorithm_logic"),
                    "algorithm_describe": d.get("algorithm_describe"),
                },
            )
            created += 1
        self.stdout.write(f"  Algorithms: {created}")

    def _import_prompts(self, cur):
        cur.execute(f'SELECT * FROM "{SCHEMA}".if_prompt_config')
        cols = [d[0] for d in cur.description]
        created = 0
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            PromptTemplate.objects.update_or_create(
                id=str(d["id"]),
                defaults={
                    "interface_code": d.get("interface_code") or "",
                    "interface_type": d.get("interface_type"),
                    "interface_name": d.get("interface_name"),
                    "prompt_content": d.get("prompt_content") or "",
                    "primary_model": d.get("primary_model"),
                    "backup_model": d.get("backup_model"),
                    "versions": str(d.get("versions") or "1"),
                    "effective": bool(int(d.get("effective") or 0)),
                },
            )
            created += 1
        self.stdout.write(f"  Prompts: {created}")
