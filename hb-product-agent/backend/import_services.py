"""
导入真实服务素材和历史方案到数据库

数据来源:
  - 服务素材库: doc/产品精算中心健管服务明细一览表.xlsx
    3个Sheet: 产品部（30行，含成本价+发生率）、交付部（24行）、其他（3行）
  - 历史方案: doc/海峡随车健康管理服务四个方案报价-4.7（内部分项报价）.xlsx
  - 历史方案: doc/国任财险-河北城商行渠道健康管理服务20260316.xls
"""
import os
import sys
import json
import re
import pandas as pd

os.environ["SEEKDB_DB"] = "product_agent"

from database import SessionLocal, Service, Scheme, SchemeItem, init_db, engine
from sqlalchemy import text


def _parse_price(val) -> float | None:
    """解析价格字段，支持字符串和数字"""
    if val is None:
        return None
    try:
        v = float(val)
        if pd.isna(v):
            return None
        return v
    except (ValueError, TypeError):
        return None


def _clean_str(val, max_len=None) -> str:
    """安全转字符串并 strip"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if s.lower() == "nan":
        return ""
    if max_len:
        s = s[:max_len]
    return s


def _parse_usage_rate(val) -> float | None:
    """解析发生率（可能是小数 0.01 或百分比字符串 '1%'）"""
    if val is None:
        return None
    try:
        if isinstance(val, str):
            val = val.strip().replace("%", "")
            v = float(val)
            # 如果 > 1，可能是百分比格式（如 1 表示 1%）
            if v > 1:
                v = v / 100
            return v
        v = float(val)
        if pd.isna(v):
            return None
        # 如果 > 1，可能是百分比格式
        if v > 1:
            v = v / 100
        return v
    except (ValueError, TypeError):
        return None


# ─── 定价类别推断 ───────────────────────────────────────────────

# 按服务名称关键词推断定价类别
_PRICING_CATEGORY_RULES = [
    ("discount", ["代金券", "购药金", "折扣", "商城", "优惠"]),
    ("per_event", ["住院", "手术", "护工", "护理", "陪诊", "陪护", "照护",
                   "门诊陪诊", "就医陪诊", "二次诊断", "二次诊疗", "会诊",
                   "绿通", "直通车", "点诊", "安排", "检查协助",
                   "洁牙", "补牙", "涂氟", "窝沟封闭", "SPA", "理疗"]),
    ("per_year", ["图文问诊", "视频问诊", "电话医生", "家庭医生", "在线问诊",
                  "中医在线", "心理咨询", "心理健康", "健康测评", "健康科普",
                  "体检报告", "药品商城", "找药"]),
    ("per_use", ["筛查", "检测", "基因", "体检服务", "眼科检查", "癌症早筛",
                 "阿尔茨海默", "心脑血管"]),
]


def _infer_pricing_category(name: str) -> str:
    """根据服务名称推断定价类别"""
    for cat, keywords in _PRICING_CATEGORY_RULES:
        for kw in keywords:
            if kw in name:
                return cat
    return "per_use"


def import_services(doc_dir: str) -> int:
    """
    从产品精算中心健管服务明细一览表导入服务素材（3个Sheet）
    返回导入的服务数
    """
    f1 = os.path.join(doc_dir, "产品精算中心健管服务明细一览表.xlsx")
    if not os.path.exists(f1):
        print(f"错误: 找不到素材库文件 {f1}")
        return 0

    xls = pd.ExcelFile(f1)
    print(f"素材库 Sheet 列表: {xls.sheet_names}")

    # 清空旧数据
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM services"))
        db.commit()
        print("已清空 services 表")
    finally:
        db.close()

    all_services = []
    seen_names = set()

    for sheet_name in xls.sheet_names:
        df = pd.read_excel(f1, sheet_name=sheet_name)
        print(f"\n--- Sheet '{sheet_name}': {len(df)} 行, 列: {list(df.columns)} ---")

        for _, row in df.iterrows():
            name = _clean_str(row.get("服务项目", ""))
            if not name or name == "服务项目":
                continue

            # 按名称去重（不同 Sheet 可能同名）
            if name in seen_names:
                # 同名服务，补充缺失字段
                for existing in all_services:
                    if existing["name"] == name:
                        # 如果产品部已有成本价，此 Sheet 无成本价 → 保留产品部数据
                        if (not existing["cost_price"] and
                                _parse_price(row.get("实发成本价"))):
                            existing["cost_price"] = _parse_price(row.get("实发成本价"))
                            existing["usage_rate_small"] = _parse_price(
                                row.get("跟单发生率\\使用率（5万单以下）"))
                            existing["usage_rate_large"] = _parse_price(
                                row.get("跟单发生率\\使用率（5-10万）"))
                            existing["is_priced"] = 1
                            existing["sheet_source"] += f",{sheet_name}"
                continue
            seen_names.add(name)

            cat = _clean_str(row.get("服务类别", "")) or "健管服务"
            cost_price = _parse_price(row.get("实发成本价"))
            usage_small = _parse_price(row.get("跟单发生率\\使用率（5万单以下）"))
            usage_large = _parse_price(row.get("跟单发生率\\使用率（5-10万）"))
            is_priced = 1 if cost_price is not None else 0

            svc = {
                "category": cat,
                "name": name,
                "description": _clean_str(row.get("服务说明"), 500) or None,
                "process": _clean_str(row.get("服务流程"), 500) or None,
                "condition": _clean_str(row.get("启动条件"), 200) or None,
                "times": _clean_str(row.get("服务次数"), 100) or None,
                "cost_price": cost_price,
                "usage_rate_small": usage_small,
                "usage_rate_large": usage_large,
                "source_file": "产品精算中心健管服务明细一览表.xlsx",
                "sheet_source": sheet_name,
                "is_priced": is_priced,
                "pricing_category": _infer_pricing_category(name),
            }
            all_services.append(svc)

    print(f"\n去重后共 {len(all_services)} 条唯一服务素材")
    priced_count = sum(1 for s in all_services if s["is_priced"])
    print(f"  其中含成本价: {priced_count} 条")
    print(f"  不含成本价: {len(all_services) - priced_count} 条")

    # 按 Sheet 统计
    for sn in xls.sheet_names:
        cnt = sum(1 for s in all_services if sn in (s["sheet_source"] or ""))
        print(f"  Sheet '{sn}': {cnt} 条")

    # 写入数据库
    db = SessionLocal()
    try:
        for s in all_services:
            svc = Service(**s)
            db.add(svc)
        db.commit()
        print(f"\n成功导入 {len(all_services)} 条服务素材")
    except Exception as e:
        db.rollback()
        print(f"导入服务失败: {e}")
        raise
    finally:
        db.close()

    return len(all_services)


def import_historical_schemes(doc_dir: str):
    """导入历史方案（海峡随车、国任财险），含多档位定价数据"""
    db = SessionLocal()
    try:
        # 清空旧历史方案
        db.execute(text("DELETE FROM scheme_items"))
        db.execute(text("DELETE FROM schemes"))
        db.commit()
        print("已清空 schemes / scheme_items 表")

        # ---- 方案1: 海峡随车健康管理服务 ----
        _import_haixia_scheme_full(db, doc_dir)

        # ---- 方案2: 国任财险河北城商行渠道 ----
        _import_guoren_scheme_full(db, doc_dir)

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"导入历史方案失败: {e}")
        raise
    finally:
        db.close()


def _import_haixia_scheme_full(db, doc_dir: str):
    """导入海峡随车健康管理服务方案（含多档位定价数据）"""
    f = os.path.join(doc_dir, "海峡随车健康管理服务四个方案报价-4.7（内部分项报价）.xlsx")
    if not os.path.exists(f):
        print(f"警告: 找不到海峡随车方案文件 {f}")
        return

    # ── Sheet 1: 健康管理服务（服务详情） ──
    df1 = pd.read_excel(f, sheet_name="健康管理服务", header=1)
    print(f"读取海峡随车方案 - 健康管理服务: {len(df1)} 行")

    scheme = Scheme(
        scheme_name="海峡随车健康管理服务方案",
        customer_name="海峡保险",
        version="内部报价 v4.7",
        source_file="海峡随车健康管理服务四个方案报价-4.7（内部分项报价）.xlsx",
    )
    db.add(scheme)
    db.flush()

    items = []
    for _, row in df1.iterrows():
        name = _clean_str(row.iloc[1])
        if not name or name == "服务项目":
            continue

        content = _clean_str(row.iloc[2], 500) if len(row) > 2 else ""
        times = _clean_str(row.iloc[3], 100) if len(row) > 3 else ""
        condition = _clean_str(row.iloc[4], 200) if len(row) > 4 else ""
        standard = _clean_str(row.iloc[5], 500) if len(row) > 5 else ""
        network = _clean_str(row.iloc[6], 200) if len(row) > 6 else ""
        price = _parse_price(row.iloc[7]) if len(row) > 7 else None

        item = SchemeItem(
            scheme_id=scheme.id,
            service_name=name,
            times=times or None,
            condition=condition or None,
            price=price,
            remark=json.dumps({
                "content": content,
                "standard": standard,
                "network": network,
            }, ensure_ascii=False),
        )
        items.append(item)

    db.add_all(items)
    print(f"  导入海峡随车方案服务详情: {len(items)} 项")

    # ── Sheet 2: 方案（多档位定价表） ──
    try:
        df2 = pd.read_excel(f, sheet_name="方案", header=None)
        print(f"读取海峡随车方案 - 方案定价表: {df2.shape}")

        # 解析规模信息（第1行）
        volume_text = _clean_str(df2.iloc[1, 0]) if len(df2) > 1 else ""
        volume_match = re.search(r'(\d+)万单', volume_text) if volume_text else None
        volume = int(volume_match.group(1)) * 10000 if volume_match else 50000

        # 解析成本列（第0列）
        cost_services = {}
        for idx in range(3, len(df2)):
            row = df2.iloc[idx]
            svc_name = _clean_str(row.iloc[0])
            if not svc_name or svc_name == "合计":
                continue
            try:
                svc_name = int(svc_name)
                # 第1列是服务名，第2列是次数，第3列是成本价
                real_name = _clean_str(row.iloc[1])
                if real_name:
                    freq = _clean_str(row.iloc[2], 50)
                    cost = _parse_price(row.iloc[3])
                    if cost is not None:
                        cost_services[real_name] = {"frequency": freq, "cost_price": cost}
            except (ValueError, TypeError):
                continue

        # 解析档位列（每4列一个方案: 服务名, 次数, 价格, 空）
        tiers_data = {}
        col = 1
        while col < len(df2.columns):
            tier_label = _clean_str(df2.iloc[2, col]) if col < len(df2.columns) else ""

            if not tier_label:
                col += 4
                continue

            # 从档位标签中提取价格（如 "方案一：10元" → 10, "引流方案" → None）
            price_match = re.search(r'(\d+\.?\d*)\s*元', tier_label) if tier_label else None
            tier_price = float(price_match.group(1)) if price_match else None
            tier_name = tier_label

            tier_services = []
            for idx in range(3, len(df2)):
                row_data = df2.iloc[idx]
                if col < len(row_data):
                    svc = _clean_str(row_data.iloc[col])
                    freq_val = _clean_str(row_data.iloc[col + 1], 50) if col + 1 < len(row_data) else ""
                    price_val = _parse_price(row_data.iloc[col + 2]) if col + 2 < len(row_data) else None
                    if svc and svc != "合计":
                        tier_services.append({
                            "name": svc,
                            "frequency": freq_val,
                            "unit_price": price_val,
                            "cost_price": cost_services.get(svc, {}).get("cost_price"),
                        })

            if tier_services:
                tiers_data[tier_name] = {
                    "target_price": tier_price,
                    "services": tier_services,
                }

            col += 4

        # 解析合计行（每4列一个档位，合计在 col+2 位置）
        total_row_idx = len(df2) - 1
        total_values = {}
        col = 1
        for tier_key in list(tiers_data.keys()):
            if col < len(df2.columns):
                total_from_excel = _parse_price(df2.iloc[total_row_idx, col + 2])
            else:
                total_from_excel = None
            # 优先用 Excel 合计值，其次用标签中提取的价格
            tier_target = tiers_data[tier_key].get("target_price")
            total_values[tier_key] = total_from_excel or tier_target
            col += 4

        # 存储 pricing_data 到 scheme 的 service_list_json（追加多档位数据）
        pricing_data = {
            "volume": volume,
            "pricing_model": "成本加成法（圆心跟单成本价）",
            "source_sheet": "方案",
            "tiers": {},
        }
        for tname, tdata in tiers_data.items():
            tier_total = total_values.get(tname, tdata["target_price"])
            pricing_data["tiers"][tname] = {
                "target_price": tdata["target_price"],
                "actual_total": tier_total,
                "service_count": len(tdata["services"]),
                "services": tdata["services"],
            }

        # 合并到 service_list_json
        original_list = json.loads(scheme.service_list_json) if scheme.service_list_json else []
        scheme.service_list_json = json.dumps({
            "service_items": original_list,
            "pricing_data": pricing_data,
        }, ensure_ascii=False)

        # 更新总价（用方案一的价格）
        first_tier_total = list(total_values.values())[0] if total_values else None
        if first_tier_total:
            scheme.total_price = first_tier_total

        tier_names = list(tiers_data.keys())
        print(f"  导入海峡随车方案定价表: {len(tier_names)} 档 ({', '.join(tier_names)}), 规模 {volume}单")
    except Exception as e:
        print(f"  警告: 海峡随车方案定价表解析失败: {e}")


def _import_guoren_scheme_full(db, doc_dir: str):
    """导入国任财险河北城商行渠道方案（含多档位定价数据）"""
    f = os.path.join(doc_dir, "国任财险-河北城商行渠道健康管理服务20260316.xls")
    if not os.path.exists(f):
        print(f"警告: 找不到国任财险方案文件 {f}")
        return

    # ── Sheet 1: 详情（服务详情） ──
    df_detail = pd.read_excel(f, sheet_name="详情", header=3)
    print(f"读取国任财险方案 - 详情: {len(df_detail)} 行")

    scheme = Scheme(
        scheme_name="河北城商行渠道健康管理服务方案",
        customer_name="国任财险",
        version="20260316",
        source_file="国任财险-河北城商行渠道健康管理服务20260316.xls",
    )
    db.add(scheme)
    db.flush()

    items = []
    for _, row in df_detail.iterrows():
        if len(row) < 5:
            continue
        name = _clean_str(row.iloc[1])
        if not name or name == "服务项目":
            continue

        desc = _clean_str(row.iloc[2], 500)
        condition = _clean_str(row.iloc[3], 200)
        times = _clean_str(row.iloc[4], 100)
        price = _parse_price(row.iloc[5]) if len(row) > 5 else None

        item = SchemeItem(
            scheme_id=scheme.id,
            service_name=name,
            times=times or None,
            condition=condition or None,
            price=price,
            remark=desc or None,
        )
        items.append(item)

    db.add_all(items)
    print(f"  导入国任财险方案服务详情: {len(items)} 项")

    # ── Sheet 2: 汇总表（五档定价） ──
    try:
        df_summary = pd.read_excel(f, sheet_name="汇总表", header=None)
        print(f"读取国任财险方案 - 汇总表: {df_summary.shape}")

        # 解析规模
        volume_text = _clean_str(df_summary.iloc[0, 1]) if df_summary.shape[1] > 1 else ""
        volume_match = re.search(r'(\d+)[-~](\d+)万单', volume_text) if volume_text else None
        volume_min = int(volume_match.group(1)) * 10000 if volume_match else 10000
        volume_max = int(volume_match.group(2)) * 10000 if volume_match else 50000

        # 解析档位头（第1行，每3列一个档位）
        tier_names = []
        tier_prices = []
        col = 1
        while col < df_summary.shape[1]:
            header = _clean_str(df_summary.iloc[1, col])
            price_text = header if header else ""
            # 提取价格区间（兼容 "25-30元" / "50-60" / "500左右" 等格式）
            price_match = re.search(r'(\d+)\s*[-~]\s*(\d+)\s*元?', price_text)
            if price_match:
                price_min = int(price_match.group(1))
                price_max = int(price_match.group(2))
                tier_prices.append((price_min, price_max))
            else:
                single_match = re.search(r'(\d+)(?:\s*元|\s*左右)?', price_text)
                if single_match:
                    p = int(single_match.group(1))
                    tier_prices.append((p, p))
                else:
                    tier_prices.append((0, 0))

            # 提取档位名
            name_match = re.match(r'([^：:]+)', header) if header else None
            tier_names.append(name_match.group(1).strip() if name_match else f"档位{len(tier_names)+1}")

            col += 3

        # 解析每个档位的服务列表
        tiers_services = {tname: [] for tname in tier_names}
        for idx in range(2, df_summary.shape[0]):
            row = df_summary.iloc[idx]
            for ti, tname in enumerate(tier_names):
                col_offset = 1 + ti * 3
                if col_offset < len(row):
                    svc = _clean_str(row.iloc[col_offset])
                    if svc and svc != "合计":
                        tiers_services[tname].append(svc)

        # 构建 pricing_data
        pricing_data = {
            "volume_min": volume_min,
            "volume_max": volume_max,
            "pricing_model": "市场对标法 + 服务累加法",
            "source_sheet": "汇总表",
            "tiers": {},
        }
        for ti, tname in enumerate(tier_names):
            pricing_data["tiers"][tname] = {
                "target_price_range": list(tier_prices[ti]) if ti < len(tier_prices) else [0, 0],
                "service_count": len(tiers_services[tname]),
                "services": tiers_services[tname],
            }

        # 合并到 service_list_json
        original_list = json.loads(scheme.service_list_json) if scheme.service_list_json else []
        scheme.service_list_json = json.dumps({
            "service_items": original_list,
            "pricing_data": pricing_data,
        }, ensure_ascii=False)

        # 更新总价字段（用基础版价格区间中值）
        if tier_prices:
            first_min, first_max = tier_prices[0]
            scheme.total_price = float((first_min + first_max) / 2)

        print(f"  导入国任财险方案定价表: {len(tier_names)} 档 ({', '.join(tier_names)}), 规模 {volume_min}-{volume_max}单")
    except Exception as e:
        print(f"  警告: 国任财险方案定价表解析失败: {e}")


if __name__ == "__main__":
    doc_dir = os.path.join(os.path.dirname(__file__), "..", "..", "doc")

    print("=" * 50)
    print("步骤 1: 导入服务素材库（3个Sheet）")
    print("=" * 50)
    n = import_services(doc_dir)

    print()
    print("=" * 50)
    print("步骤 2: 导入历史方案（含多档位定价数据）")
    print("=" * 50)
    import_historical_schemes(doc_dir)

    print()
    print("全部导入完成!")
