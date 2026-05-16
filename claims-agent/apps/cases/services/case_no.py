"""案件号生成器 — {三方系统代号}-{项目代码}-{案件类型}-{YYYYMMDD}-{6位序号}"""
from datetime import date


SOURCE_CODES = {"OLD": "OLD", "MAN": "MAN", "API": "API"}


def generate_case_no(source_system: str, project_code: str, claim_type: str, seq: int) -> str:
    src = SOURCE_CODES.get(source_system, source_system[:3].upper())
    proj = (project_code or "UNKNOWN")[:20]
    ct = claim_type or "SP"
    today = date.today().strftime("%Y%m%d")
    return f"{src}-{proj}-{ct}-{today}-{seq:06d}"
