"""Phase 4+6: 档案整理 + 历史案件查询"""
import json
from pathlib import Path
from openai import OpenAI
from django.conf import settings
import pysqlite3 as sqlite3

PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"
DB_PATH = Path(settings.BASE_DIR) / "data" / "db.sqlite3"


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


def generate_archive(ocr_results: list[dict], case_info: dict) -> dict:
    """Phase 4: 档案整理 — 结构化治疗档案（6大板块）"""
    prompt = _load_prompt("archive/file_archive/v1.txt")
    if not prompt:
        return _fallback_archive(ocr_results, case_info)

    client = _get_client()
    try:
        context = f"""<理赔客户报案材料>
OCR提取汇总: {json.dumps(ocr_results, ensure_ascii=False)}
案件信息: {json.dumps(case_info, ensure_ascii=False)}
</理赔客户报案材料>"""
        resp = client.chat.completions.create(
            model=settings.PRIMARY_MODEL,
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": context}],
            temperature=0.1, max_tokens=8192,
        )
        return _safe_json(resp.choices[0].message.content, _fallback_archive(ocr_results, case_info))
    except Exception as e:
        return {"error": str(e), **(_fallback_archive(ocr_results, case_info))}


def _fallback_archive(ocr_results: list[dict], case_info: dict) -> dict:
    return {
        "patient_info": {"name": case_info.get("insured_name", ""), "diagnosis": case_info.get("diagnosis", "")},
        "diagnosis_info": {"disease": case_info.get("diagnosis", ""), "confirmed_date": ""},
        "treatment_path": [],
        "past_treatment": [],
        "current_visit": {},
        "drug_info": [],
        "surgery_exam": {},
        "preexisting_risk_flag": False,
    }


def query_history_claims(insured_id: str) -> dict:
    """查询出险人历史案件"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        # 从自有数据库查
        own = conn.execute(
            "SELECT case_no, insured_name, diagnosis, status, created_at FROM cases_case WHERE insured_id = ? ORDER BY created_at DESC LIMIT 10",
            [insured_id]
        ).fetchall()
        own_cases = [{"case_no": r[0], "name": r[1], "diagnosis": r[2], "status": r[3], "date": str(r[4])} for r in own]

        # 从只读库查历史（如果有的话）
        readonly_cases = []
        if settings.READONLY_DB_URL:
            try:
                import psycopg2
                pg = psycopg2.connect(settings.READONLY_DB_URL, client_encoding="UTF8")
                pg.set_client_encoding("UTF8")
                cur = pg.cursor()
                cur.execute(f"""
                    SELECT inner_case_no, claim_status, preexisting_disease, preexisting_disease_desc
                    FROM "claim-special-medicine-core".if_case
                    WHERE insured_id = %s AND claim_status IN ('JA','TPZG')
                    ORDER BY report_date DESC LIMIT 10
                """, [insured_id])
                for r in cur.fetchall():
                    readonly_cases.append({
                        "case_no": r[0], "status": r[1],
                        "preexisting": str(r[2]) if r[2] else None,
                        "preexisting_desc": r[3],
                    })
                cur.close(); pg.close()
            except Exception:
                pass

        # 标记既往症风险
        preexisting_risk = False
        preexisting_reason = ""
        for rc in readonly_cases:
            pe = rc.get("preexisting", "")
            # 只当值为 Y/YES/1 时才是真的既往症；N/NO/0/null 都不是
            if pe and str(pe).strip().upper() in ("Y", "YES", "1", "TRUE"):
                preexisting_risk = True
                preexisting_reason = rc.get("preexisting_desc", "历史案件标记既往症")
                break

        return {
            "own_cases": own_cases,
            "readonly_cases": readonly_cases,
            "total_history": len(own_cases) + len(readonly_cases),
            "preexisting_risk": preexisting_risk,
            "preexisting_reason": preexisting_reason,
        }
    finally:
        conn.close()


def generate_archive_json(archive: dict) -> dict:
    """结构化 JSON 输出（Phase 6 用）"""
    return {
        "customerInfo": archive.get("patient_info", {}),
        "treatmentRecords": archive.get("treatment_path", []),
        "pastRecords": archive.get("past_treatment", []),
        "drugRecords": archive.get("drug_info", []),
    }
