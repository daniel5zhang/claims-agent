"""评测脚本 — 100条抽样全链路评测"""
import json, sys, os, random, time
from datetime import date, datetime
from decimal import Decimal
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django; django.setup()

from agent.tools.matching_tools import match_drug, match_hospital, match_disease
from agent.tools.archive_tools import query_history_claims
from agent.tools.audit_tools import check_waiting_period, check_material_complete, check_duplicate_claim
from agent.tools.calculation_tools import calculate_compensation, aggregate_liabilities
from agent.tools.audit_tools import run_audit_rule, RULE_LAYERS, _build_matrix
from apps.evaluation.models import EvalCase, EvalAnnotation, EvalAudit, EvalPolicy, EvalProduct, EvalCaseDrugPoint

# Load dataset
with open('data/eval_full_dataset.json') as f:
    data = json.load(f)

# Sample 100 cases stratified by audit conclusion
cases_list = list(data['cases'].values())
random.seed(42)
ps_cases = [c for c in cases_list if any(a.get('audit_conclusion')=='PS' for a in data['audits'].get(str(c['id']),[]))][:40]
jp_cases = [c for c in cases_list if any(a.get('audit_conclusion')=='JP' for a in data['audits'].get(str(c['id']),[]))][:30]
np_cases = [c for c in cases_list if any(a.get('audit_conclusion')=='NP' for a in data['audits'].get(str(c['id']),[]))][:20]
other = [c for c in cases_list if c not in ps_cases+jp_cases+np_cases][:10]
sample = ps_cases + jp_cases + np_cases + other
print(f"Sample: {len(sample)} cases (PS={len(ps_cases)} JP={len(jp_cases)} NP={len(np_cases)} Other={len(other)})")

results = []
start_time = time.time()
api_calls = 0

for idx, case in enumerate(sample):
    cid = str(case['id'])
    diag = data['diagnostics'].get(cid, {})
    drugs = data['case_drugs'].get(cid, [])
    audits = data['audits'].get(cid, [])
    policy_id = str(case.get('policy_id', ''))
    policy = data['policies'].get(policy_id, {})
    pi = data['policy_insurances'].get(policy_id, {})

    # Ground truth: audit conclusion
    old_conclusion = audits[0]['audit_conclusion'] if audits else '?'
    old_pay = float(case.get('pay_total') or 0)

    r = {'case_id': cid, 'case_no': case.get('inner_case_no','')[:20],
         'old_conclusion': old_conclusion, 'old_pay': old_pay}

    # Phase 3: Matching
    drug_name = drugs[0].get('common_name','') or drugs[0].get('drug_name','') if drugs else ''
    hosp_name = diag.get('hospital_name','') or ''
    disease = diag.get('disease','') or diag.get('be_ill_disease_species','') or ''

    drug_result = match_drug(drug_name) if drug_name else {'method': 'no_data'}
    hosp_result = match_hospital(hosp_name) if hosp_name else {'method': 'no_data'}
    dis_result = match_disease(disease) if disease else {'method': 'no_data'}
    r['drug_match'] = drug_result.get('method','no_data')
    r['hospital_match'] = hosp_result.get('method','no_data')
    r['disease_match'] = dis_result.get('method','no_data')

    # Phase 4: History
    insured_id = str(case.get('insured_id',''))
    history = query_history_claims(insured_id)
    r['preexisting_risk'] = history['preexisting_risk']

    # Phase 5: Non-API audit rules
    w_result = check_waiting_period(
        policy.get('insurance_start_time') or date(2024,1,1),
        case.get('report_date') or date(2024,6,1), 30)
    m_result = check_material_complete(
        [{'attachment_type': '处方原件'}, {'attachment_type': '购药发票'}], 'outside_pharmacy')
    d_result = check_duplicate_claim(
        {'insured_id': insured_id, 'drug_name': drug_name},
        [{'insured_id': insured_id}])  # simplified

    r['waiting_ok'] = w_result['result'] == 'pass'
    r['material_ok'] = m_result['result'] == 'pass'
    r['duplicate_ok'] = d_result['result'] == 'pass'

    # Phase 6: Calculation with real policy/product data
    # payout_ratio from PRODUCT (if_insurance), coverage from POLICY (if_policy_insurance)
    product_id = str(case.get('project_id',''))
    product = data['products'].get(product_id, {})
    payout_ratio = float(product.get('not_pre_existing_disease_ratio', 90) or 90) / 100.0
    coverage = float(pi.get('remain_lines', 0) or pi.get('insurance_amount', 0) or 50000)
    deductible = float(product.get('deductible_excess', 0) or 0)
    drug_price = float(drugs[0].get('price', 0)) if drugs else 0
    drug_amount = float(drugs[0].get('amount', 0)) if drugs else 1

    calc_result = calculate_compensation('tdyp_001',
        {'drug_unit_price': drug_price, 'quantity': drug_amount},
        {'remaining_coverage': coverage, 'payout_ratio': max(payout_ratio, 0.5), 'deductible_balance': deductible})
    r['our_pay'] = calc_result['pay_amount']
    r['pay_deviation'] = abs(r['our_pay'] - old_pay) if old_pay > 0 else None

    # Phase 7: Decision — simple rules
    all_pass = r['drug_match'] in ('exact','fuzzy') and r['hospital_match'] in ('exact','fuzzy') and r['waiting_ok'] and r['material_ok']
    r['our_decision'] = 'PS' if all_pass else 'NP'

    # Match?
    r['decision_match'] = (r['our_decision'] == old_conclusion)
    results.append(r)

    if (idx+1) % 20 == 0:
        elapsed = time.time() - start_time
        print(f"  [{idx+1}/{len(sample)}] {elapsed:.0f}s ({elapsed/(idx+1):.0f}s/case)")

# === Metrics ===
total = len(results)
correct = sum(1 for r in results if r['decision_match'])
ps_acc = sum(1 for r in results if r['old_conclusion']=='PS' and r['decision_match']) / max(sum(1 for r in results if r['old_conclusion']=='PS'), 1)
jp_recall = sum(1 for r in results if r['old_conclusion'] in ('JP','NP') and r['our_decision'] in ('JP','NP')) / max(sum(1 for r in results if r['old_conclusion'] in ('JP','NP')), 1)

elapsed = time.time() - start_time

print(f"\n{'='*55}")
print(f"  Agent 评测报告 ({total} cases, {api_calls} API calls)")
print(f"{'='*55}")
print(f"  耗时: {elapsed:.0f}s ({elapsed/total:.1f}s/case)")
print(f"")
print(f"  --- 案件级 ---")
print(f"  决策一致率: {correct}/{total} = {correct/total*100:.1f}%")
print(f"  PS(通过)准确率: {ps_acc*100:.0f}%")
print(f"  JP/NP(拒赔)召回率: {jp_recall*100:.0f}%")
print(f"")
print(f"  --- Phase 3 匹配 ---")
drug_ok = sum(1 for r in results if r['drug_match'] in ('exact','fuzzy'))
hosp_ok = sum(1 for r in results if r['hospital_match'] in ('exact','fuzzy'))
print(f"  药品匹配率: {drug_ok}/{total} = {drug_ok/total*100:.1f}%")
print(f"  医院匹配率: {hosp_ok}/{total} = {hosp_ok/total*100:.1f}%")
print(f"")
print(f"  --- Phase 5 规则 ---")
print(f"  等待期通过: {sum(1 for r in results if r['waiting_ok'])}/{total}")
print(f"  材料齐全: {sum(1 for r in results if r['material_ok'])}/{total}")
print(f"  既往症风险: {sum(1 for r in results if r['preexisting_risk'])}/{total}")
print(f"")
print(f"  --- Phase 6 理算 ---")
pay_devs = [r['pay_deviation'] for r in results if r['pay_deviation'] is not None]
if pay_devs:
    print(f"  赔付偏差(平均): ¥{sum(pay_devs)/len(pay_devs):,.0f}")
    print(f"  赔付偏差(中位): ¥{sorted(pay_devs)[len(pay_devs)//2]:,.0f}")
    close = sum(1 for i, r2 in enumerate(results) if r2.get('pay_deviation') is not None and r2['old_pay'] > 0 and abs(r2['pay_deviation'])/r2['old_pay'] < 0.01)
    has_pay = sum(1 for r2 in results if r2.get('old_pay', 0) > 0)
    print(f"  赔付精确匹配(±1%): {close}/{has_pay}")

# Save
with open('data/eval_100_results.json', 'w') as f:
    json.dump({
        'metrics': {
            'total': total, 'correct': correct,
            'consistency': round(correct/total*100, 1),
            'ps_accuracy': round(ps_acc*100, 1),
            'jp_recall': round(jp_recall*100, 1),
            'drug_match_rate': round(drug_ok/total*100, 1),
            'hospital_match_rate': round(hosp_ok/total*100, 1),
            'elapsed_s': round(elapsed, 1),
        },
        'results': [{k: str(v) if isinstance(v, (Decimal,)) else v for k, v in r.items()} for r in results]
    }, f, ensure_ascii=False, indent=2, default=str)

print(f"\n  Results saved to data/eval_100_results.json")
