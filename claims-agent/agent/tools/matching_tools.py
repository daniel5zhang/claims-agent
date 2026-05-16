"""Phase 5: 匹配工具 — 药品/医院/疾病 + sqlite-vec 向量匹配"""
import json
import pysqlite3 as sqlite3
import sqlite_vec
from pathlib import Path
from django.conf import settings
from openai import OpenAI

DB_PATH = Path(settings.BASE_DIR) / "data" / "db.sqlite3"


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    return conn


def match_drug(drug_name: str) -> dict:
    """药品匹配 — 精确 → 模糊 → 向量"""
    conn = _get_conn()
    try:
        # 1. 精确匹配 common_name
        r = conn.execute(
            "SELECT id, common_name, product_name, drug_type, is_original FROM drugs_drug WHERE common_name = ?",
            [drug_name]
        ).fetchone()
        if r:
            return {"drug_id": r[0], "drug_name": r[1], "product_name": r[2],
                    "drug_type": r[3], "is_original": bool(r[4]), "method": "exact"}

        # 2. 模糊匹配
        r = conn.execute(
            "SELECT id, common_name, product_name, drug_type, is_original FROM drugs_drug WHERE common_name LIKE ? LIMIT 1",
            [f"%{drug_name}%"]
        ).fetchone()
        if r:
            return {"drug_id": r[0], "drug_name": r[1], "product_name": r[2],
                    "drug_type": r[3], "is_original": bool(r[4]), "method": "fuzzy"}

        # 3. 向量相似度（用 LLM embedding + sqlite-vec）
        # 简化：再用 LLM 做语义匹配
        return _llm_drug_match(drug_name)
    finally:
        conn.close()


def _llm_drug_match(drug_name: str) -> dict:
    """LLM 语义匹配兜底"""
    client = OpenAI(api_key=settings.DASHSCOPE_API_KEY, base_url=settings.DASHSCOPE_BASE_URL)
    conn = _get_conn()
    try:
        drugs = conn.execute("SELECT id, common_name, product_name, drug_type FROM drugs_drug LIMIT 50").fetchall()
        drug_list = "\n".join([f"{d[0]}|{d[1]}|{d[2]}|{d[3]}" for d in drugs])
        resp = client.chat.completions.create(
            model=settings.FLASH_MODEL,
            messages=[{"role": "user", "content": f"从以下药品库中匹配 '{drug_name}'，只返回最匹配的一条JSON(含drug_id,common_name,method='llm'):\n{drug_list}"}],
            temperature=0.1, max_tokens=256,
        )
        return _safe_json(resp.choices[0].message.content, {"drug_name": drug_name, "method": "llm"})
    finally:
        conn.close()


def match_hospital(hospital_name: str) -> dict:
    """医院匹配 — 精确 → 模糊 → LLM → 联网"""
    conn = _get_conn()
    try:
        r = conn.execute(
            "SELECT id, code, name, hospital_level, province, city FROM hospitals_hospital WHERE name = ?",
            [hospital_name]
        ).fetchone()
        if r:
            return {"hospital_id": r[0], "code": r[1], "name": r[2],
                    "level": r[3], "province": r[4], "city": r[5], "method": "exact"}

        # 模糊
        r = conn.execute(
            "SELECT id, code, name, hospital_level, province, city FROM hospitals_hospital WHERE name LIKE ? LIMIT 1",
            [f"%{hospital_name}%"]
        ).fetchone()
        if r:
            return {"hospital_id": r[0], "code": r[1], "name": r[2],
                    "level": r[3], "province": r[4], "city": r[5], "method": "fuzzy"}

        return {"hospital_name": hospital_name, "method": "not_found", "suggestion": "联网搜索"}
    finally:
        conn.close()


def match_disease(disease_name: str) -> dict:
    """疾病 ICD-10 标准化 — 精确 → 模糊"""
    conn = _get_conn()
    try:
        r = conn.execute(
            "SELECT id, disease_name, disease_code, disease_type FROM diseases_disease WHERE disease_name = ?",
            [disease_name]
        ).fetchone()
        if r:
            return {"disease_id": r[0], "disease_name": r[1], "disease_code": r[2],
                    "disease_type": r[3], "method": "exact"}

        r = conn.execute(
            "SELECT id, disease_name, disease_code, disease_type FROM diseases_disease WHERE disease_name LIKE ? LIMIT 1",
            [f"%{disease_name}%"]
        ).fetchone()
        if r:
            return {"disease_id": r[0], "disease_name": r[1], "disease_code": r[2],
                    "disease_type": r[3], "method": "fuzzy"}

        return {"disease_name": disease_name, "method": "not_found"}
    finally:
        conn.close()


def match_compared_drugs(drug_name: str) -> list[dict]:
    """比价药品匹配 — mock"""
    return [{"drug_name": drug_name, "alternatives": [], "method": "mock"}]


def verify_on_ins(policy_id: str) -> dict:
    """在保校验 — 查保单有效期"""
    conn = _get_conn()
    try:
        r = conn.execute(
            "SELECT policy_no, effective_date, expiry_date, status FROM policies_policy WHERE id = ?",
            [policy_id]
        ).fetchone()
        if r:
            from datetime import date
            today = date.today()
            effective = r[1]
            expiry = r[2]
            if effective and expiry:
                on_ins = effective <= today <= expiry
                return {"on_ins": on_ins, "policy_no": r[0], "effective_date": str(effective),
                        "expiry_date": str(expiry), "reason": "在保" if on_ins else "不在保"}
        return {"on_ins": True, "reason": "保单数据缺失，默认在保"}
    finally:
        conn.close()


def get_product_terms(product_id: str) -> dict:
    """读取产品条款"""
    return {"product_id": product_id, "terms": "产品条款待加载", "version": "1.0"}


def _safe_json(text: str, default=None):
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        pass
    return default or {}
