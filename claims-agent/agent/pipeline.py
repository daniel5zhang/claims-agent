"""动态流水线构建 — 按险种责任组装 Phase"""
from dataclasses import dataclass, field

# 责任类型 → 匹配工具
LIABILITY_TOOL_MAP = {
    "特药责任": {"match_drug", "verify_drug_indication", "match_compared_drugs"},
    "住院责任": {"match_hospital"},
    "门诊责任": {"match_hospital"},
    "重疾责任": {"match_disease"},
    "手术责任": {"match_hospital", "match_disease"},
}

# 通用规则（所有险种）
UNIVERSAL_RULES = [
    "1.1_identity", "1.2_insurance_period", "2.1_material_complete", "3.1_preexisting_disease"
]

# 责任类型 → 审核规则
LIABILITY_RULE_MAP = {
    "特药责任": ["1.3.1_drug_match", "1.3.2_special_disease_whitelist", "drug_verify"],
    "住院责任": ["1.4_hospital_qualification", "2.2.3_medical_settlement", "2.2.4_hospital_bill"],
    "门诊责任": ["2.2.2_prescription_validity"],
    "重疾责任": ["match_disease"],
}


@dataclass
class PhaseConfig:
    name: str
    tools: set = field(default_factory=set)
    rules: list = field(default_factory=list)
    is_parallel: bool = True
    model: str = "qwen3.6-flash"


def build_policy_pipeline(liabilities: list[str]) -> list[PhaseConfig]:
    """按险种责任动态构建流水线"""
    matching_tools = {"verify_on_ins"}
    audit_rules = list(UNIVERSAL_RULES)

    for liab in liabilities:
        matching_tools.update(LIABILITY_TOOL_MAP.get(liab, set()))
        audit_rules.extend(LIABILITY_RULE_MAP.get(liab, []))

    return [
        PhaseConfig("phase_0_discovery", {"get_case_info", "discover_policies"}, [], model="qwen3.6-flash"),
        PhaseConfig("phase_3_matching", matching_tools, [], model="qwen3.6-flash"),
        PhaseConfig("phase_5_audit", set(), sorted(set(audit_rules)), model="qwen3.6-plus"),
        PhaseConfig("phase_6_calculation", {"calculate_compensation"}, [], model="qwen3.6-flash"),
    ]
