"""保单发现逻辑 — PolicySource 抽象层"""
from abc import ABC, abstractmethod
from datetime import date
from dataclasses import dataclass, field


@dataclass
class PolicyData:
    policy_id: str
    policy_no: str
    product_id: str
    insured_id: str
    coverage_amount: float = 0
    effective_date: date | None = None
    expiry_date: date | None = None
    is_renewal: bool = False
    liabilities: list = field(default_factory=list)


class PolicySource(ABC):
    @abstractmethod
    def discover(self, insured_id: str, claim_date: date) -> list[PolicyData]: ...


class ReadonlyDBPolicySource(PolicySource):
    """从只读库查询保单"""
    def __init__(self):
        import psycopg2
        self.db_url = __import__("django.conf", fromlist=["settings"]).settings.READONLY_DB_URL

    def discover(self, insured_id: str, claim_date: date) -> list[PolicyData]:
        if not self.db_url:
            return []
        import psycopg2
        conn = psycopg2.connect(self.db_url, client_encoding="UTF8")
        conn.set_client_encoding("UTF8")
        cur = conn.cursor()
        schema = "claim-special-medicine-core"
        # 按 policy_id 直接查（主流程：案件已关联保单）
        # 按 insured_id 查 → TODO 等完整数据字典后实现
        cur.execute(f"""
            SELECT p.id, p.policy_no, p.insurance_start_time, p.insurance_end_time,
                   COALESCE(pi.insurance_id, '') AS product_id
            FROM "{schema}".if_policy p
            LEFT JOIN "{schema}".if_policy_insurance pi ON pi.policy_id = p.id
            WHERE p.id = %s
              AND p.insurance_start_time <= %s
              AND p.insurance_end_time >= %s
        """, [insured_id, claim_date, claim_date])
        results = []
        for row in cur.fetchall():
            results.append(PolicyData(
                policy_id=str(row[0]), policy_no=row[1] or "", insured_id=insured_id,
                effective_date=row[2],
                expiry_date=row[3],
                product_id=str(row[4]) if row[4] else "",
            ))
        cur.close()
        conn.close()
        return results


def discover_policies(insured_id: str, claim_date: date, sources: list[PolicySource] | None = None) -> list[PolicyData]:
    if sources is None:
        sources = [ReadonlyDBPolicySource()]
    seen = set()
    results = []
    for source in sources:
        for p in source.discover(insured_id, claim_date):
            if p.policy_id not in seen:
                seen.add(p.policy_id)
                results.append(p)
    return results
