"""案件入口适配器 — 基类"""
from abc import ABC, abstractmethod
from apps.cases.models import Case


class CaseIntakeAdapter(ABC):
    """统一入口适配器基类"""

    @abstractmethod
    def fetch_cases(self, **filters) -> list[dict]: ...

    @abstractmethod
    def normalize(self, raw_case: dict) -> dict: ...

    def ingest(self, **filters) -> list[Case]:
        results = []
        for raw in self.fetch_cases(**filters):
            data = self.normalize(raw)
            case, _ = Case.objects.update_or_create(
                case_no=data["case_no"],
                defaults=data,
            )
            results.append(case)
        return results
