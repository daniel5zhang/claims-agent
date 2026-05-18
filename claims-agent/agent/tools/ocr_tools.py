"""Phase 1a/1b: OCR 分类 + 提取工具"""
import json
import base64
from pathlib import Path
from openai import OpenAI
from django.conf import settings


PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def _get_client(model: str = None) -> OpenAI:
    return OpenAI(
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.DASHSCOPE_BASE_URL,
    )


def _load_prompt(path: str) -> str:
    p = PROMPT_DIR / path
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


def ocr_classify(attachments: list[dict]) -> list[dict]:
    """Phase 1a: 影像件分类
    Input: [{"attachment_id":"...","base64":"..."}]
    Output: [{"attachment_id":"...","doc_type":"...","confidence":0.95}]
    """
    prompt = _load_prompt("ocr/ocr_classify/v1.txt")
    if not prompt:
        return [_fallback_classify(a) for a in attachments]

    client = _get_client(settings.PRIMARY_MODEL)
    results = []
    for att in attachments:
        try:
            resp = client.chat.completions.create(
                model=settings.PRIMARY_MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{att['base64']}"}},
                        {"type": "text", "text": "请分类此影像件，返回 JSON: {\"big_type\":\"\",\"small_type\":\"\",\"confidence\":0.0}"},
                    ]},
                ],
                temperature=0.1,
                max_tokens=256,
            )
            content = resp.choices[0].message.content
            parsed = _safe_json(content, {})
            big = parsed.get('big_type','')
            small = parsed.get('small_type','')
            # Map Chinese big_type to old system English type_code for eval comparison
            type_code_map = {'1':'Identification_materials','2':'Medical_diagnosis_and_treatment_materials',
                '3':'Prescription_drug_materials','4':'Medical_expense_materials',
                '21':'Supplementary_materials_for_claims','0':'Unknown'}
            results.append({
                "attachment_id": att["attachment_id"],
                "doc_type": f"{big}/{small}",
                "type_code": type_code_map.get(str(big), str(big)),
                "confidence": float(parsed.get("confidence", 0)),
            })
        except Exception as e:
            results.append({"attachment_id": att["attachment_id"], "doc_type": "error", "confidence": 0, "error": str(e)})
    return results


def ocr_extract(attachments: list[dict]) -> list[dict]:
    """Phase 1b: OCR内容提取
    Input: [{"attachment_id":"...","base64":"...","doc_type":"..."}]
    Output: [{"attachment_id":"...","raw_text":"...","fields":{}}]
    """
    prompt = _load_prompt("ocr/ocr_extract/v1.txt")
    if not prompt:
        return [{"attachment_id": a["attachment_id"], "raw_text": "", "fields": {}, "error": "no prompt"} for a in attachments]

    client = _get_client(settings.PRIMARY_MODEL)
    results = []
    for att in attachments:
        try:
            content_parts = [{"type": "text", "text": f"附件类型: {att.get('doc_type','')}\n请提取内容，返回 JSON"}]
            if att.get("base64"):
                content_parts.insert(0, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{att['base64']}"}})
            resp = client.chat.completions.create(
                model=settings.PRIMARY_MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": content_parts},
                ],
                temperature=0.1,
                max_tokens=4096,
            )
            content = resp.choices[0].message.content
            parsed = _safe_json(content, {})
            results.append({
                "attachment_id": att["attachment_id"],
                "doc_type": att.get("doc_type", ""),
                "raw_text": json.dumps(parsed, ensure_ascii=False),
                "fields": parsed,
            })
        except Exception as e:
            results.append({"attachment_id": att["attachment_id"], "error": str(e)})
    return results


def _fallback_classify(att: dict) -> dict:
    return {"attachment_id": att.get("attachment_id", ""), "doc_type": "unknown/unknown", "confidence": 0}


def _safe_json(text: str, default=None):
    try:
        # 提取第一个 JSON 对象
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return default or {}
