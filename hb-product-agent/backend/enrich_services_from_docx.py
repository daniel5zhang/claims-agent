"""
从原版 Word 手册提取服务详情（服务时间、服务时效、特别说明等），
更新 Service 素材库记录。

数据来源: doc/8.职工家庭防癌抗癌保障卡健康管理服务手册（个人尊享版）.docx

运行方式:
  cd backend && python enrich_services_from_docx.py
"""
import os
import sys
import re
import json
from docx import Document

os.environ["SEEKDB_DB"] = "product_agent"

from database import SessionLocal, Service, init_db
from sqlalchemy import text

# 确保表结构和迁移已执行
init_db()


# ─── 服务名匹配映射（Word 中的标题 → Service.name 关键词）───
# 由于 Word 中的服务名称与 DB 中可能不完全一致，需要建立映射
SERVICE_NAME_MAP = {
    "重疾门诊绿通": "重疾门诊绿通",
    "就医陪诊服务": "就医陪诊",  # DB 中为简称
    "重疾住院护理服务": "住院护理",  # 最接近的 DB 记录
    "住院护理服务": "住院护理",
    "肿瘤专家会诊优惠服务": "肿瘤MTB多学科会诊",
    "肿瘤专家会诊": "肿瘤MTB多学科会诊",
    "质子重离子就医直通车": "质子重离子医院直通车",
    "质子重离子": "质子重离子医院直通车",
    "心梗脑梗筛查权益": "心脑血管筛查",
    "心梗脑梗筛查": "心脑血管筛查",
    "阿尔兹海默筛查权益": "阿尔茨海默病APOE基因筛查",
    "阿尔兹海默筛查": "阿尔茨海默病APOE基因筛查",
    "癌症早筛服务": "癌症早筛服务",
    "癌症早筛": "癌症早筛服务",
    "齿科服务": "齿科服务（成人洁牙/3M树脂补牙）",
    "齿科": "齿科服务（成人洁牙/3M树脂补牙）",
    "中医线上问诊服务": "中医在线问诊",
    "中医线上问诊": "中医在线问诊",
    "健康科普中心": "健康科普中心",
    "健康评测": "健康评测",
    "在线药品商城": "在线药品商城",
    "恶性肿瘤用药基因检测费用权益": "癌症靶向药基因检测服务",
    "恶性肿瘤用药基因检测": "癌症靶向药基因检测服务",
    "MRD": "MRD（肿瘤术后复发监测）",
    "蛋白质分子体检优惠权益": "蛋白质分子体检",
    "蛋白质分子体检": "蛋白质分子体检",
    "中医理疗服务": "中医理疗",
    "中医理疗": "中医理疗",
}


def extract_services_from_docx(docx_path: str) -> list[dict]:
    """
    从 Word 文档中提取每个服务段落的结构化数据。

    返回列表，每个元素为:
    {
        "word_title": "1.重疾门诊绿通",
        "name_keyword": "重疾门诊绿通",
        "description": "...",
        "service_time": "工作日 9:00-18:00",
        "service_response_time": "1个工作日响应，提前7个工作日进行预约",
        "times": "保单有效期内1次",
        "condition": "...",
        "process": "...",
        "special_notes": "..."
    }
    """
    doc = Document(docx_path)
    services = []
    current_svc = None
    current_field = None  # 当前正在收集的字段名
    current_lines = []    # 当前字段的多行文本

    # 匹配服务标题: "1.重疾门诊绿通" 或 "8.癌症早筛服务"
    service_title_pattern = re.compile(r"^(\d+)\.(.+)$")

    # 字段标题（原版 Word 中的格式）
    field_patterns = [
        ("description", re.compile(r"^服务时间：(.+)$")),
        ("description", re.compile(r"^服务时效：(.+)$")),
        ("description", re.compile(r"^服务频次：(.+)$")),
        ("description", re.compile(r"^启动条件：(.+)$")),
        ("description", re.compile(r"^服务流程：$")),
        ("description", re.compile(r"^特别说明：$")),
        ("description", re.compile(r"^指定检测机构：(.+)$")),
        ("description", re.compile(r"^权益内容：$")),
        ("description", re.compile(r"^使用人：(.+)$")),
        ("description", re.compile(r"^快递运输：(.+)$")),
        ("description", re.compile(r"^商品退换：$")),
        ("description", re.compile(r"^特别约定：$")),
    ]

    def _flush_current():
        """保存当前字段到 current_svc"""
        nonlocal current_field, current_lines
        if current_svc and current_field and current_lines:
            text = "\n".join(current_lines).strip()
            if current_field == "process":
                current_svc["process"] = text
            elif current_field == "special_notes":
                current_svc["special_notes"] = text
            current_field = None
            current_lines = []

    def _save_service():
        """完成当前服务，加入列表"""
        _flush_current()
        if current_svc:
            services.append(current_svc)

    # ─── 简易状态机解析 ───
    F_SERVICE_TIME = "service_time"
    F_RESPONSE_TIME = "service_response_time"
    F_TIMES = "times"
    F_CONDITION = "condition"
    F_PROCESS = "process"
    F_SPECIAL_NOTES = "special_notes"
    F_NONE = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # 跳过封面、目录、附件
        if text in ["职工家庭防癌抗癌保障卡健康服务手册",
                     "（2026个人尊享版）", "目录",
                     "附件：28种重大疾病清单"]:
            continue
        if text.startswith("附件：") or text.startswith("（28种重大疾病"):
            _save_service()
            break

        # 匹配 `N.服务名` 作为新服务开始
        sm = service_title_pattern.match(text)
        if sm and len(text) < 80:
            # 排除附件列表 `1、恶性肿瘤`
            if "、" in sm.group(1):
                continue
            # 排除目录中的缩写
            if any(x in text for x in ["打开微信", "公众号"]):
                continue

            _save_service()
            order = int(sm.group(1))
            title = sm.group(2).strip()
            current_svc = {
                "word_title": text,
                "order": order,
                "name_keyword": title,
                "description": "",
                "service_time": "",
                "service_response_time": "",
                "times": "",
                "condition": "",
                "process": "",
                "special_notes": "",
            }
            current_field = F_NONE
            current_lines = []
            continue

        # 还没有服务标题 → 跳过（封面、目录等）
        if current_svc is None:
            continue

        # ── 字段检测 ──
        if text.startswith("服务时间："):
            _flush_current()
            current_field = F_SERVICE_TIME
            current_lines = [text[len("服务时间："):].strip()]
            continue
        if text.startswith("服务时效："):
            _flush_current()
            current_field = F_RESPONSE_TIME
            current_lines = [text[len("服务时效："):].strip()]
            continue
        if text.startswith("服务频次："):
            _flush_current()
            current_field = F_TIMES
            current_lines = [text[len("服务频次："):].strip()]
            continue
        if text.startswith("启动条件："):
            _flush_current()
            current_field = F_CONDITION
            current_lines = [text[len("启动条件："):].strip()]
            continue
        if text == "服务流程：":
            _flush_current()
            current_field = F_PROCESS
            current_lines = []
            continue
        if text.startswith("特别说明：") or text.startswith("特别约定："):
            _flush_current()
            current_field = F_SPECIAL_NOTES
            # "特别说明：" 后面可能没有内容（在下一行）
            rest = text[len("特别说明："):].strip() if text.startswith("特别说明：") else text[len("特别约定："):].strip()
            current_lines = [rest] if rest else []
            continue

        # ── 普通段落：视当前字段收集 ──
        # 如果没有当前字段，就把这段作为 description 的一部分
        if current_field in (F_SERVICE_TIME, F_RESPONSE_TIME, F_TIMES, F_CONDITION):
            # 单行字段，直接设置
            current_svc[current_field] = current_lines[0] if current_lines else text
            current_field = F_NONE
            current_lines = []
            continue

        if current_field in (F_PROCESS, F_SPECIAL_NOTES):
            current_lines.append(text)
        else:
            # 普通段落 → 服务描述
            if current_svc["description"]:
                current_svc["description"] += "\n" + text
            else:
                current_svc["description"] = text

    # 保存最后一个服务
    _save_service()

    # 后处理：找到第一个"真服务"（有服务时间/时效/频次/条件/流程/特别说明），
    # 丢弃之前误解析的温馨提示步骤
    first_real_idx = -1
    for i, svc in enumerate(services):
        has_fields = any([
            svc.get("service_time"),
            svc.get("service_response_time"),
            svc.get("times"),
            svc.get("condition"),
            svc.get("process"),
            svc.get("special_notes"),
        ])
        if has_fields:
            first_real_idx = i
            break

    if first_real_idx > 0:
        discarded = services[:first_real_idx]
        print(f"  丢弃前 {first_real_idx} 个非服务段落: {[d['word_title'] for d in discarded]}")
        services = services[first_real_idx:]

    return services


def enrich_db(services: list[dict]):
    """将提取的服务数据更新到素材库"""
    db = SessionLocal()
    try:
        all_db = {s.name: s for s in db.query(Service).all()}
        updated = 0
        skipped = []

        for svc in services:
            kw = svc["name_keyword"]
            db_name = SERVICE_NAME_MAP.get(kw)

            # 精确匹配失败 → 尝试模糊匹配（处理括号变体，如"重疾住院护理服务（5天4晚）"）
            if not db_name:
                # 去掉括号后缀再匹配
                kw_no_paren = re.sub(r"[（(][^)）]*[)）]", "", kw).strip()
                if kw_no_paren and kw_no_paren != kw:
                    db_name = SERVICE_NAME_MAP.get(kw_no_paren)
                # 遍历 map，子串匹配
                if not db_name:
                    for map_key, map_val in SERVICE_NAME_MAP.items():
                        if not map_val:
                            continue
                        if map_key in kw or kw in map_key:
                            db_name = map_val
                            break
                # 去掉括号后再试子串
                if not db_name and kw_no_paren:
                    for map_key, map_val in SERVICE_NAME_MAP.items():
                        if not map_val:
                            continue
                        if map_key in kw_no_paren or kw_no_paren in map_key:
                            db_name = map_val
                            break

            if not db_name:
                skipped.append(f"{svc['word_title']} → 无映射")
                continue

            db_svc = None
            # 精确匹配
            if db_name in all_db:
                db_svc = all_db[db_name]
            else:
                # 子串匹配
                for name, s in all_db.items():
                    if db_name in name or name in db_name:
                        db_svc = s
                        break

            if not db_svc:
                # 创建新服务记录
                db_svc = Service(
                    name=db_name,
                    description=(svc.get("description") or "")[:500],
                    service_time=svc.get("service_time") or "",
                    service_response_time=svc.get("service_response_time") or "",
                    special_notes=svc.get("special_notes") or "",
                    condition=svc.get("condition") or "",
                    times=svc.get("times") or "",
                    process=svc.get("process") or "",
                )
                db.add(db_svc)
                db.flush()
                all_db[db_name] = db_svc
                print(f"  + {svc['word_title']} → 新建 DB '{db_name}'")
                updated += 1
                continue

            # 更新字段（不覆盖已有数据）
            if svc.get("service_time") and not db_svc.service_time:
                db_svc.service_time = svc["service_time"]
            if svc.get("service_response_time") and not db_svc.service_response_time:
                db_svc.service_response_time = svc["service_response_time"]
            if svc.get("special_notes") and not db_svc.special_notes:
                db_svc.special_notes = svc["special_notes"]
            if svc.get("condition") and not db_svc.condition:
                db_svc.condition = svc["condition"]
            if svc.get("times") and not db_svc.times:
                db_svc.times = svc["times"]
            if svc.get("process") and not db_svc.process:
                db_svc.process = svc["process"]
            if svc.get("description") and not db_svc.description:
                db_svc.description = svc["description"][:500]

            updated += 1
            print(f"  ✓ {svc['word_title']} → DB '{db_svc.name}'")

        db.commit()
        print(f"\n更新了 {updated} 条服务记录")
        if skipped:
            print(f"跳过了 {len(skipped)} 项:")
            for s in skipped:
                print(f"  - {s}")

    except Exception as e:
        db.rollback()
        print(f"错误: {e}")
        raise
    finally:
        db.close()


def main():
    # 查找 Word 文件
    docx_paths = [
        os.path.join(os.path.dirname(__file__), "..", "doc",
                     "8.职工家庭防癌抗癌保障卡健康管理服务手册（个人尊享版）.docx"),
        os.path.join(os.path.dirname(__file__), "doc",
                     "8.职工家庭防癌抗癌保障卡健康管理服务手册（个人尊享版）.docx"),
        os.path.join(os.path.dirname(__file__), "..", "..", "doc",
                     "8.职工家庭防癌抗癌保障卡健康管理服务手册（个人尊享版）.docx"),
    ]
    docx_path = None
    for p in docx_paths:
        if os.path.exists(p):
            docx_path = p
            break

    if not docx_path:
        print("错误: 找不到 Word 模板文件")
        sys.exit(1)

    print(f"解析文件: {docx_path}")
    services = extract_services_from_docx(docx_path)
    print(f"提取到 {len(services)} 个服务段落\n")

    for svc in services:
        print(f"  [{svc['order']}] {svc['name_keyword']}")
        if svc["service_time"]:
            print(f"      服务时间: {svc['service_time'][:60]}")
        if svc["service_response_time"]:
            print(f"      服务时效: {svc['service_response_time'][:60]}")
        if svc["special_notes"]:
            print(f"      特别说明: {svc['special_notes'][:60]}...")

    print(f"\n开始更新素材库...")
    enrich_db(services)


if __name__ == "__main__":
    main()
