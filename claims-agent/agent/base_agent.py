"""Phase 16: BaseClaimAgent 抽象 + 险种路由注册表"""
from abc import ABC, abstractmethod
from agent.pipeline import build_policy_pipeline, PhaseConfig, LIABILITY_TOOL_MAP, LIABILITY_RULE_MAP


class BaseClaimAgent(ABC):
    """险种 Agent 基类"""
    claim_type: str = ""
    claim_type_name: str = ""

    @abstractmethod
    def get_liability_rules(self, liability_type: str) -> list[str]: ...

    @abstractmethod
    def get_liability_tools(self, liability_type: str) -> set[str]: ...

    def build_pipeline(self, liabilities: list[str]) -> list[PhaseConfig]:
        return build_policy_pipeline(liabilities)


class SpecialDrugAgent(BaseClaimAgent):
    """特药险 Agent"""
    claim_type = "SP"
    claim_type_name = "特药险"

    def get_liability_rules(self, liability_type: str) -> list[str]:
        return LIABILITY_RULE_MAP.get(liability_type, [])

    def get_liability_tools(self, liability_type: str) -> set[str]:
        return LIABILITY_TOOL_MAP.get(liability_type, set())


class MedicalAgent(BaseClaimAgent):
    """医疗险 Agent (Phase 16 扩展)"""
    claim_type = "MED"
    claim_type_name = "医疗险"

    MEDICAL_RULES = {
        "住院责任": ["1.4_hospital_qualification", "2.2.3_medical_settlement", "2.2.4_hospital_bill"],
        "门诊责任": ["2.2.2_prescription_validity"],
    }
    MEDICAL_TOOLS = {
        "住院责任": {"match_hospital"},
        "门诊责任": {"match_hospital"},
    }

    def get_liability_rules(self, liability_type: str) -> list[str]:
        return self.MEDICAL_RULES.get(liability_type, [])

    def get_liability_tools(self, liability_type: str) -> set[str]:
        return self.MEDICAL_TOOLS.get(liability_type, set())


class AccidentAgent(BaseClaimAgent):
    """意外险 Agent (Phase 16 扩展)"""
    claim_type = "ACC"
    claim_type_name = "意外险"

    def get_liability_rules(self, liability_type: str) -> list[str]:
        return []

    def get_liability_tools(self, liability_type: str) -> set[str]:
        return set()


class CriticalIllnessAgent(BaseClaimAgent):
    """重疾险 Agent (Phase 16 扩展)"""
    claim_type = "CI"
    claim_type_name = "重疾险"

    CI_RULES = {"重疾责任": ["match_disease"]}
    CI_TOOLS = {"重疾责任": {"match_disease"}}

    def get_liability_rules(self, liability_type: str) -> list[str]:
        return self.CI_RULES.get(liability_type, [])

    def get_liability_tools(self, liability_type: str) -> set[str]:
        return self.CI_TOOLS.get(liability_type, set())


# 险种路由注册表
AGENT_REGISTRY: dict[str, BaseClaimAgent] = {
    "SP": SpecialDrugAgent(),
    "MED": MedicalAgent(),
    "ACC": AccidentAgent(),
    "CI": CriticalIllnessAgent(),
}


def get_agent(claim_type: str) -> BaseClaimAgent:
    agent = AGENT_REGISTRY.get(claim_type)
    if agent is None:
        return SpecialDrugAgent()  # 默认特药险
    return agent
