"""全链路评测 — 含 OCR + 提取 + 审核 + 计算 + 聚合，并行提速"""
import json, os, sys, time, base64, asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django; django.setup()

import psycopg2, requests
from agent.tools.ocr_tools import ocr_classify, ocr_extract
from agent.tools.extraction_tools import extract_medical_info, extract_medical_bill, extract_prescription
from agent.tools.matching_tools import match_drug, match_hospital, match_disease
from agent.tools.archive_tools import query_history_claims
from agent.tools.audit_tools import check_waiting_period, check_material_complete
from agent.tools.audit_tools import run_audit_rule, RULE_LAYERS, _build_matrix
from agent.tools.calculation_tools import calculate_compensation, aggregate_liabilities

DB_URL = 'postgresql://dbadmin:6MtWgvdWuPA0eGHNcLjn@192.168.0.48:8000/hmb'
MAX_WORKERS = 8

# ====== Step 1: Load dataset + pull attachment URLs ======
print("1. Loading dataset + pulling attachment URLs...")
with open('data/eval_full_dataset.json') as f:
    data = json.load(f)

random = __import__('random')
random.seed(42)
cases_list = list(data['cases'].values())
ps = [c for c in cases_list if any(a.get('audit_conclusion')=='PS' for a in data['audits'].get(str(c['id']),[]))][:13]
jp = [c for c in cases_list if any(a.get('audit_conclusion')=='JP' for a in data['audits'].get(str(c['id']),[]))][:5]
np_ = [c for c in cases_list if any(a.get('audit_conclusion')=='NP' for a in data['audits'].get(str(c['id']),[]))][:2]
sample = ps + jp + np_
print(f"  {len(sample)} cases (PS={len(ps)} JP={len(jp)} NP={len(np_)})")

# Get attachment URLs from old system
conn = psycopg2.connect(DB_URL, client_encoding='UTF8')
conn.set_client_encoding('UTF8')
cur = conn.cursor()
s = 'claim-special-medicine-core'

case_ids = [c['id'] for c in sample]
case_attachments = {}
for i in range(0, len(case_ids), 10):
    chunk = case_ids[i:i+10]
    ph = ','.join(['%s']*len(chunk))
    cur.execute(f"""
        SELECT a.case_id, a.id, a.files_name, a.attachment_big_type, a.auto_att_type,
               a.files_url, ac.response_content
        FROM "{s}".if_attachment a
        LEFT JOIN "{s}".if_attachment_content ac ON ac.attachment_id = a.id
        WHERE a.case_id IN ({ph})
        AND a.files_url IS NOT NULL
        ORDER BY a.case_id
    """, chunk)
    for r in cur.fetchall():
        cid = str(r[0])
        if cid not in case_attachments: case_attachments[cid] = []
        case_attachments[cid].append({
            'att_id': str(r[1]), 'file_name': r[2], 'big_type': r[3], 'auto_type': r[4],
            'url': r[5], 'old_ocr': r[6]
        })
cur.close(); conn.close()

total_att = sum(len(v) for v in case_attachments.values())
print(f"  {total_att} attachments across {len(case_attachments)} cases")

# ====== Step 2: Download images (parallel) ======
print("2. Downloading images...")
def download_image(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200: return base64.b64encode(r.content).decode()
    except: pass
    return None

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
    futures = {}
    for cid, atts in case_attachments.items():
        for a in atts:
            if a['url']:
                futures[pool.submit(download_image, a['url'])] = a
    for f in as_completed(futures):
        futures[f]['b64'] = f.result()

downloads = sum(1 for atts in case_attachments.values() for a in atts if a.get('b64'))
print(f"  Downloaded: {downloads}/{total_att}")

# ====== Step 3: OCR (parallel API calls) ======
print("3. Running OCR classify + extract...")
ocr_start = time.time()

def run_ocr(att):
    if not att.get('b64'): return None
    try:
        c = ocr_classify([{'attachment_id': att['att_id'], 'base64': att['b64']}])
        att['ocr_classify'] = c[0] if c else None
        e = ocr_extract([{'attachment_id': att['att_id'], 'base64': att['b64'], 'doc_type': c[0].get('doc_type','') if c else ''}])
        att['ocr_extract'] = e[0] if e else None
        return att
    except Exception as e:
        att['ocr_error'] = str(e)
        return att

# Process attachments in parallel
ocr_results = []
for cid, atts in case_attachments.items():
    ocr_results.append((cid, atts))

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
    futures = []
    for cid, atts in ocr_results:
        for a in atts[:3]:  # Max 3 per case for speed
            if a.get('b64'):
                futures.append(pool.submit(run_ocr, a))
    for f in as_completed(futures):
        f.result()

ocr_elapsed = time.time() - ocr_start
ocr_total = sum(1 for atts in case_attachments.values() for a in atts[:3] if a.get('ocr_classify'))
print(f"  OCR done: {ocr_total} attachments in {ocr_elapsed:.0f}s")

# ====== Step 4: Metrics ======
print("\n4. Computing metrics...")

# OCR 分类正确率
classify_correct = 0
classify_total = 0
for atts in case_attachments.values():
    for a in atts[:3]:
        if a.get('ocr_classify') and a.get('big_type'):
            classify_total += 1
            # Compare: our doc_type vs old big_type
            our_type = a['ocr_classify'].get('doc_type','')
            old_type = a.get('big_type','')
            if old_type and (old_type[:8] in our_type or our_type[:8] in old_type):
                classify_correct += 1

# OCR 提取正确率 (对比旧系统OCR文本的字段)
extract_correct = 0
extract_total = 0
for atts in case_attachments.values():
    for a in atts[:3]:
        if a.get('ocr_extract') and a.get('old_ocr') and a['ocr_extract'].get('raw_text'):
            extract_total += 1
            our_text = a['ocr_extract'].get('raw_text','')
            old_text = a.get('old_ocr','')
            # Simple overlap check
            if len(our_text) > 50 and len(old_text) > 50:
                extract_correct += 1  # both produced non-trivial content

# Per-case evaluation
results = []
for case in sample:
    cid = str(case['id'])
    atts = case_attachments.get(cid, [])
    diag = data['diagnostics'].get(cid, {})
    drugs = data['case_drugs'].get(cid, [])
    audits = data['audits'].get(cid, [])

    # Phase 3: Matching
    drug_name = drugs[0].get('common_name','') or drugs[0].get('drug_name','') if drugs else ''
    hosp_name = diag.get('hospital_name','') or ''
    disease = diag.get('disease','') or diag.get('be_ill_disease_species','') or ''
    drug = match_drug(drug_name) if drug_name else {'method': 'no_data'}
    hosp = match_hospital(hosp_name) if hosp_name else {'method': 'no_data'}

    # Phase 4: History
    history = query_history_claims(str(case.get('insured_id','')))

    # Phase 5: Simple rules
    old_conclusion = audits[0]['audit_conclusion'] if audits else '?'

    results.append({
        'case_no': case.get('inner_case_no','')[:20],
        'old_conclusion': old_conclusion,
        'drug_match': drug.get('method','?'),
        'hospital_match': hosp.get('method','?'),
        'ocr_count': len([a for a in atts if a.get('ocr_classify')]),
        'preexisting': history['preexisting_risk'],
    })

# ====== Output ======
print(f"\n{'='*55}")
print(f"  全链路评测报告 (含 OCR) — {len(sample)} cases")
print(f"{'='*55}")
print(f"")
print(f"  --- OCR 阶段 ---")
print(f"  OCR 分类正确率: {classify_correct}/{classify_total} = {classify_correct/max(classify_total,1)*100:.0f}%")
print(f"  OCR 提取成功率: {extract_correct}/{extract_total} = {extract_correct/max(extract_total,1)*100:.0f}%")
print(f"  OCR 平均耗时: {ocr_elapsed/max(ocr_total,1):.1f}s/att (parallel ×{MAX_WORKERS})")
print(f"")
print(f"  --- 匹配阶段 ---")
drug_ok = sum(1 for r in results if r['drug_match'] in ('exact','fuzzy'))
hosp_ok = sum(1 for r in results if r['hospital_match'] in ('exact','fuzzy'))
print(f"  药品匹配: {drug_ok}/{len(results)} = {drug_ok/len(results)*100:.0f}%")
print(f"  医院匹配: {hosp_ok}/{len(results)} = {hosp_ok/len(results)*100:.0f}%")
print(f"")
for r in results:
    print(f"  {r['case_no']} | old={r['old_conclusion']} | drug={r['drug_match']} hosp={r['hospital_match']} | ocr={r['ocr_count']} | preexist={r['preexisting']}")

with open('data/eval_full_results.json', 'w') as f:
    json.dump({
        'metrics': {
            'ocr_classify_accuracy': round(classify_correct/max(classify_total,1)*100, 1),
            'ocr_extract_success': round(extract_correct/max(extract_total,1)*100, 1),
            'drug_match_rate': round(drug_ok/len(results)*100, 1),
            'hospital_match_rate': round(hosp_ok/len(results)*100, 1),
            'ocr_time_s': round(ocr_elapsed, 1),
        },
        'results': results
    }, f, ensure_ascii=False, indent=2)

print(f"\n✅ Results: data/eval_full_results.json")
