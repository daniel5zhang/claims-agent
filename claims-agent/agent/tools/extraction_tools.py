"""Phase 2: 3路结构化提取工具"""
import json
from pathlib import Path
from openai import OpenAI
from django.conf import settings

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def _get_client():
    return OpenAI(api_key=settings.DASHSCOPE_API_KEY, base_url=settings.DASHSCOPE_BASE_URL)


def _load_prompt(path: str) -> str:
    p = PROMPT_DIR / path
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _safe_json(text: str, default=None):
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return default or {}


def extract_medical_bill(raw_text: str, attachment_id: str = "") -> dict:
    """提取医疗账单 24 字段"""
    prompt = _load_prompt("extraction/medical_bill/v1.txt")
    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=settings.PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": prompt or "提取医疗账单信息"},
                {"role": "user", "content": f"<OCR提取文本>\n{raw_text}\n</OCR提取文本>"},
            ],
            temperature=0.1,
            max_tokens=2048,
        )
        result = _safe_json(resp.choices[0].message.content, {})
        result["attachment_id"] = attachment_id
        return result
    except Exception as e:
        return {"attachment_id": attachment_id, "error": str(e)}


def extract_medical_info(raw_text: str, attachment_id: str = "") -> dict:
    """提取就诊诊断信息"""
    prompt = _load_prompt("extraction/medical_info/v1.txt")
    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=settings.PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": prompt or "提取诊断信息"},
                {"role": "user", "content": f"<OCR提取文本>\n{raw_text}\n</OCR提取文本>"},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        result = _safe_json(resp.choices[0].message.content, {})
        result["attachment_id"] = attachment_id
        return result
    except Exception as e:
        return {"attachment_id": attachment_id, "error": str(e)}


def extract_prescription(raw_text: str, attachment_id: str = "") -> list[dict]:
    """提取处方用药 27 字段"""
    prompt = _load_prompt("extraction/prescription/v1.txt")
    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=settings.PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": prompt or "提取处方用药信息"},
                {"role": "user", "content": f"<OCR提取文本>\n{raw_text}\n</OCR提取文本>"},
            ],
            temperature=0.1,
            max_tokens=4096,
        )
        result = _safe_json(resp.choices[0].message.content, [])
        if isinstance(result, dict):
            result = [result]
        for r in result:
            r["attachment_id"] = attachment_id
        return result
    except Exception as e:
        return [{"attachment_id": attachment_id, "error": str(e)}]
