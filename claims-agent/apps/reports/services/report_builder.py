"""案件报告生成 + 对外文档输出"""
import json
from apps.reports.models import AuditReport


def build_audit_report(case, phases: dict, rule_results: dict,
                       interventions: list, calculation: dict,
                       final_decision: str) -> AuditReport:
    """生成全量审核报告"""
    obj, _ = AuditReport.objects.update_or_create(
        case=case,
        defaults=dict(
            phases=phases,
            rule_results=rule_results,
            interventions=interventions,
            calculation_detail=calculation,
            final_decision=final_decision,
        ),
    )
    return obj


def build_html_report(case, report: AuditReport) -> str:
    """HTML 内联渲染 — 9 节完整报告"""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>审核报告 - {case.case_no}</title></head>
<body>
<h1>案件审核报告</h1>
<h2>一、案件基础信息</h2>
<p>案件号: {case.case_no} | 出险人: {case.insured_name} | 诊断: {case.diagnosis}</p>
<p>理赔模式: {case.claim_mode} | 优先级: {case.priority} | 状态: {case.status}</p>
<h2>二、保单列表</h2>
<h2>三、附件清单</h2>
<h2>四、Agent 执行过程</h2>
<pre>{json.dumps(report.phases, ensure_ascii=False, indent=2)}</pre>
<h2>五、适应症审核要点</h2>
<h2>六、理算明细</h2>
<pre>{json.dumps(report.calculation_detail, ensure_ascii=False, indent=2)}</pre>
<h2>七、人工介入记录</h2>
<pre>{json.dumps(report.interventions, ensure_ascii=False, indent=2)}</pre>
<h2>八、时效信息</h2>
<h2>九、最终决策</h2>
<p>结论: {report.final_decision}</p>
<p>生成时间: {report.created_at}</p>
</body></html>"""


def generate_document(case, template_type: str, recipient: str) -> str:
    """对外输出文档 — 理赔决定书/审核报告/直赔授权单"""
    templates = {
        "理赔决定书": f"理赔决定书\n案件号: {case.case_no}\n被保险人: {case.insured_name}\n结论: {case.status}",
        "审核报告": f"审核报告\n{case.case_no}\n诊断: {case.diagnosis}",
        "直赔授权单": f"直赔授权单\n{case.case_no}\n理赔模式: 直赔",
    }
    return templates.get(template_type, f"文档: {case.case_no}")
