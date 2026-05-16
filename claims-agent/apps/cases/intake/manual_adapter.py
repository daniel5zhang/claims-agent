"""手工录入适配器 — 页面填写 + 保单凭证OCR"""
from .base_adapter import CaseIntakeAdapter
from apps.cases.services.case_no import generate_case_no
from apps.cases.models import Case


class ManualAdapter(CaseIntakeAdapter):
    source = "MAN"

    def fetch_cases(self, **filters) -> list[dict]:
        return []  # 手工录入不走批量 fetch

    def normalize(self, raw: dict) -> dict:
        last = Case.objects.filter(source_system="MAN").order_by("-case_no").first()
        seq = int(last.case_no.split("-")[-1]) + 1 if last else 1
        return {
            "case_no": generate_case_no("MAN", raw.get("project_code", ""), raw.get("claim_type", "SP"), seq),
            "source_system": "MAN",
            "source_case_no": None,
            "project_id": raw.get("project_id"),
            "insured_id": raw.get("insured_id", ""),
            "insured_name": raw.get("insured_name", ""),
            "id_number": raw.get("id_number", ""),
            "phone": raw.get("phone", ""),
            "diagnosis": raw.get("diagnosis", ""),
            "hospital_name": raw.get("hospital_name"),
            "report_date": raw.get("report_date"),
            "risk_date": raw.get("risk_date"),
            "claim_mode": raw.get("claim_mode", "reimbursement"),
            "claim_type": raw.get("claim_type", "SP"),
            "status": "pending",
        }
