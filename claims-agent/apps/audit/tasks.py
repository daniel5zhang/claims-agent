"""Huey 任务 — Agent 审核异步执行"""
import asyncio
from huey.contrib.djhuey import task
from apps.cases.models import Case


@task()
def run_audit_task(case_id: str, policy_ids: list[str]):
    """异步执行 Agent 审核"""
    from agent.orchestrator import run_agent

    case = Case.objects.get(id=case_id)
    try:
        result = asyncio.run(run_agent(case_id, policy_ids))
        case.status = "completed"
        case.save()
        return result
    except Exception as e:
        case.status = "error"
        case.save()
        raise
