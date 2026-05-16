"""外部API推送适配器 — 占位，接口规范待定"""
from .base_adapter import CaseIntakeAdapter
from apps.cases.services.case_no import generate_case_no


class ApiPushAdapter(CaseIntakeAdapter):
    source = "API"

    def fetch_cases(self, **filters) -> list[dict]:
        return []  # 待对接外部系统

    def normalize(self, raw: dict) -> dict:
        return {
            "case_no": raw.get("case_no", ""),
            "source_system": "API",
            "source_case_no": raw.get("external_id"),
            "project_id": None,
            "insured_id": raw.get("insured_id", ""),
            "insured_name": raw.get("name", ""),
            "id_number": raw.get("id_number", ""),
            "phone": raw.get("phone", ""),
            "report_date": raw.get("report_date"),
            "claim_type": "SP",
            "status": "pending",
        }
