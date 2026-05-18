"""全链路评测 — 并行版本：OCR并行→Archive汇聚→审核并行→多保单并行"""
import json, sys, os, time, asyncio, base64
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django; django.setup()

import psycopg2, requests
from agent.tools.ocr_tools import ocr_classify, ocr_extract
from agent.tools.extraction_tools import extract_medical_bill, extract_medical_info, extract_prescription
from agent.tools.matching_tools import match_drug, match_hospital, match_disease
from agent.tools.archive_tools import generate_archive, query_history_claims
from agent.tools.audit_tools import run_audit_rule, run_indication_audit, _build_matrix, RULE_LAYERS
from agent.tools.calculation_tools import calculate_compensation, aggregate_liabilities
from asgiref.sync import sync_to_async

DB_URL = 'postgresql://dbadmin:6MtWgvdWuPA0eGHNcLjn@192.168.0.48:8000/hmb'
MAX_IMG = 3  # Max images per case

with open('data/eval_full_dataset.json') as f:
    data = json.load(f)

cases_list = list(data['cases'].values())[:5]  # 5 cases for quick test
print(f'评测: {len(cases_list)} cases\n')

api_call_count = [0]  # counter in list for mutability

# ====== Step 1: Pull attachment URLs ======
print("1. Pulling attachments...")
conn = psycopg2.connect(DB_URL, client_encoding='UTF8')
conn.set_client_encoding('UTF8')
cur = conn.cursor()
s = 'claim-special-medicine-core'

case_attachments = {}
for c in cases_list:
    cid = c['id']
    cur.execute(f"""
        SELECT a.id, a.attachment_big_type, a.files_url
        FROM "{s}".if_attachment a WHERE a.case_id = %s AND a.files_url IS NOT NULL LIMIT {MAX_IMG}
    """, [cid])
    case_attachments[str(cid)] = []
    for r in cur.fetchall():
        case_attachments[str(cid)].append({'att_id': str(r[0]), 'type': r[1], 'url': r[2]})
cur.close(); conn.close()
total = sum(len(v) for v in case_attachments.values())
print(f"  {total} attachments")


# ====== Step 2: Download + OCR — full parallel per attachment ======
print("2. Download + OCR (%d workers)..." % (MAX_IMG * len(cases_list)))

def download_and_ocr(att):
    """Download image + classify + extract — all in one function for ThreadPool"""
    try:
        r = requests.get(att['url'], timeout=15)
        if r.status_code != 200: return att
        b64 = base64.b64encode(r.content).decode()
        att['b64'] = b64
        c = ocr_classify([{'attachment_id': att['att_id'], 'base64': b64}])
        att['ocr_classify'] = c[0] if c else None
        doc_type = c[0].get('doc_type', '') if c else ''
        e = ocr_extract([{'attachment_id': att['att_id'], 'base64': b64, 'doc_type': doc_type}])
        att['ocr_extract'] = e[0] if e else None
        api_call_count[0] += 2  # classify + extract
    except Exception as e:
        att['error'] = str(e)
    return att

all_atts = []
for atts in case_attachments.values():
    all_atts.extend(atts)

t_ocr = time.time()
with ThreadPoolExecutor(max_workers=len(all_atts)) as pool:
    futures = [pool.submit(download_and_ocr, a) for a in all_atts]
    for f in as_completed(futures):
        f.result()
print(f"  OCR done: {api_call_count[0]} calls in {time.time()-t_ocr:.0f}s")


# ====== Step 3: Per-case evaluation (parallel across cases) ======
async def eval_case(case):
    cid = str(case['id'])
    atts = case_attachments.get(cid, [])
    diag = data['diagnostics'].get(cid, {})
    drugs = data['case_drugs'].get(cid, [])
    audits = data['audits'].get(cid, [])
    pi = data['policy_insurances'].get(str(case.get('policy_id', '')), {})
    product = data['products'].get(str(case.get('project_id', '')), {})

    drug_name = drugs[0].get('common_name', '') or drugs[0].get('drug_name', '') if drugs else ''
    hosp_name = diag.get('hospital_name', '') or ''
    disease = diag.get('disease', '') or diag.get('be_ill_disease_species', '') or ''

    # Parallel Layer: Extraction (3 way)
    ocr_texts = [a.get('ocr_extract', {}).get('raw_text', '') for a in atts if a.get('ocr_extract')]
    combined_text = ' '.join(ocr_texts)[:5000]
    extract_tasks = []
    if combined_text:
        extract_tasks = [
            asyncio.to_thread(extract_medical_info, combined_text),
            asyncio.to_thread(extract_medical_bill, combined_text, ''),
            asyncio.to_thread(extract_prescription, combined_text, ''),
        ]
        med_info, bill_info, presc_info = await asyncio.gather(*extract_tasks)
    else:
        med_info = {'disease_name': disease}; bill_info = {}; presc_info = []

    api_call_count[0] += 3

    # Parallel Layer: Matching (4 way)
    match_tasks = [
        asyncio.to_thread(match_drug, drug_name) if drug_name else asyncio.sleep(0, result={'method': 'no_data'}),
        asyncio.to_thread(match_hospital, hosp_name) if hosp_name else asyncio.sleep(0, result={'method': 'no_data'}),
        asyncio.to_thread(match_disease, disease) if disease else asyncio.sleep(0, result={}),
        asyncio.to_thread(lambda: query_history_claims(str(case.get('insured_id', ''))))(),
    ]
    drug, hosp, dis, history = await asyncio.gather(*[
        asyncio.to_thread(match_drug, drug_name) if drug_name else asyncio.ensure_future(asyncio.sleep(0, result={'method': 'no_data'})),
        asyncio.to_thread(match_hospital, hosp_name) if hosp_name else asyncio.ensure_future(asyncio.sleep(0, result={'method': 'no_data'})),
        asyncio.to_thread(lambda: query_history_claims(str(case.get('insured_id', ''))))(),
    ])

    # Gate: Archive (serial — cross-validation)
    archive = await asyncio.to_thread(generate_archive,
        [{'attachment_id': a['att_id'], 'doc_type': a.get('type', ''), 'raw_text': a.get('ocr_extract', {}).get('raw_text', ''), 'fields': {}} for a in atts if a.get('ocr_extract')],
        {'insured_name': case.get('report_person_name', '') or '', 'diagnosis': disease})
    api_call_count[0] += 1

    # Parallel Layer: Audit rules (all rules parallel)
    matched = {'drug': drug, 'hospital': hosp}
    c_info = {'diagnosis': disease, 'hospital_name': hosp_name}

    audit_tasks = []
    for rc in ['1.2_insurance_period', '1.3.1_drug_match', '1.4_hospital_qualification', '3.1_preexisting_disease']:
        audit_tasks.append(asyncio.to_thread(run_audit_rule, rc, archive, history, matched, c_info))
    if drug_name:
        audit_tasks.append(asyncio.to_thread(run_indication_audit, drug_name, archive, c_info))

    rule_results = await asyncio.gather(*audit_tasks)
    api_call_count[0] += len(audit_tasks)

    for layer in [1, 2, 3, 4]:
        for rc in RULE_LAYERS.get(layer, []):
            if rc not in [x['rule_code'] for x in rule_results if isinstance(x, dict)]:
                rule_results.append({'rule_code': rc, 'result': 'pass', 'reason': 'skipped'})

    matrix = _build_matrix(rule_results)
    our_decision = matrix['final_decision']

    # Phase 6: Calculation
    payout_ratio = float(product.get('not_pre_existing_disease_ratio', 90) or 90) / 100.0
    coverage = float(pi.get('remain_lines', 0) or pi.get('insurance_amount', 0) or 50000)
    drug_price = float(drugs[0].get('price', 0)) if drugs else 0
    drug_qty = float(drugs[0].get('amount', 0)) if drugs else 1
    calc = calculate_compensation('tdyp_001', {'drug_unit_price': drug_price, 'quantity': drug_qty},
                                   {'remaining_coverage': coverage, 'payout_ratio': payout_ratio})

    CONCLUSION_MAP = {'PS':'pass','ZCPF':'pass','JP':'reject','NP':'reject','TRPF':'transferToManual','BFPF':'supplement'}
    old_conclusion = audits[0]['audit_conclusion'] if audits else '?'
    old_mapped = CONCLUSION_MAP.get(old_conclusion, old_conclusion)
    match_status = our_decision == old_mapped
    m = '✅' if match_status else '❌'
    print(f'  {m} {case.get("inner_case_no","?")[:20]} | old={old_conclusion} our={our_decision} | {matrix["pass_count"]}p/{matrix["reject_count"]}r/{matrix["supplement_count"]}s')

    return {'case_no': case.get('inner_case_no', '')[:20], 'old': old_conclusion,
            'our': our_decision, 'match': match_status,
            'pay_our': calc['pay_amount'], 'pay_old': case.get('pay_total', 0),
            'rules': f'{matrix["pass_count"]}p/{matrix["reject_count"]}r'}


async def main():
    t0 = time.time()
    # All cases in parallel!
    results = await asyncio.gather(*[eval_case(c) for c in cases_list])
    elapsed = time.time() - t0
    correct = sum(1 for r in results if r['match'])
    print(f'\n{"="*55}')
    print(f'  并行评测: {len(cases_list)} cases, {api_call_count[0]} API, {elapsed:.0f}s ({elapsed/len(cases_list):.0f}s/case)')
    print(f'  决策一致率: {correct}/{len(cases_list)}')
    print(f'{"="*55}')


print("\n3. Running evaluation (parallel)...")
asyncio.run(main())
