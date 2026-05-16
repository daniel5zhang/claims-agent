"""旧系统同步适配器 — 手工筛选同步，可重复"""
import psycopg2
from django.conf import settings
from django.utils import timezone
from .base_adapter import CaseIntakeAdapter
from apps.cases.services.case_no import generate_case_no
from apps.cases.models import Case


SCHEMA = "claim-special-medicine-core"


def _make_aware(dt):
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


class OldSystemAdapter(CaseIntakeAdapter):
    source = "OLD"

    def __init__(self):
        self.db_url = settings.READONLY_DB_URL

    def fetch_cases(self, **filters) -> list[dict]:
        if not self.db_url:
            return []
        conn = psycopg2.connect(self.db_url, client_encoding="UTF8")
        conn.set_client_encoding("UTF8")
        cur = conn.cursor()
        where = ["1=1"]
        params = []
        if filters.get("case_ids"):
            where.append(f"c.id IN ({','.join(['%s']*len(filters['case_ids']))})")
            params.extend(filters["case_ids"])
        if filters.get("project_id"):
            where.append("c.project_id = %s")
            params.append(filters["project_id"])
        cur.execute(f"""
            SELECT c.id, c.inner_case_no, c.insured_id, c.project_id,
                   c.claim_status, c.report_date, c.risk_date,
                   c.claim_type, c.pay_total, c.claim_total,
                   c.report_person_name, c.report_person_phone,
                   c.id_no, c.preexisting_disease
            FROM "{SCHEMA}".if_case c
            WHERE {' AND '.join(where)}
        """, params)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows

    def normalize(self, raw: dict) -> dict:
        project_id = str(raw["project_id"]) if raw.get("project_id") else None
        project_code = ""
        if project_id:
            try:
                from apps.policies.models import Project
                project_code = Project.objects.get(id=project_id).project_code
            except Exception:
                pass
        # 找最大序号
        from apps.cases.services.case_no import SOURCE_CODES
        last = Case.objects.filter(source_system="OLD").order_by("-case_no").first()
        seq = int(last.case_no.split("-")[-1]) + 1 if last else 1
        return {
            "case_no": generate_case_no("OLD", project_code, raw.get("claim_type") or "SP", seq),
            "source_system": "OLD",
            "source_case_no": raw.get("inner_case_no") or str(raw.get("id", "")),
            "project_id": project_id,
            "insured_id": str(raw.get("insured_id") or ""),
            "insured_name": raw.get("report_person_name") or "",
            "id_number": raw.get("id_no") or "",
            "phone": raw.get("report_person_phone") or "",
            "report_date": _make_aware(raw.get("report_date")),
            "risk_date": _make_aware(raw.get("risk_date")),
            "claim_type": raw.get("claim_type") or "SP",
            "status": "pending",
        }
