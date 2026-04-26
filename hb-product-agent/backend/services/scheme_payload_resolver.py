"""
统一方案取值对象解析器

目标：
1. Excel / Word 使用同一套 service_list_json 解析逻辑
2. 支持按方案名或方案序号选择单一方案生成
3. 保持多方案与单方案两种模式兼容
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def _as_list_dict(value: Any) -> List[Dict[str, Any]]:
    """将输入标准化为 dict 列表"""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, dict)]


def parse_payload(service_list_json: Optional[str]) -> Dict[str, Any]:
    """
    解析 GeneratedScheme.service_list_json，返回标准结构：
    - top_services: 顶层 services
    - schemes: 多方案列表（每项含 services）
    """
    parsed: Any = {}
    if service_list_json:
        try:
            parsed = json.loads(service_list_json)
        except (json.JSONDecodeError, TypeError):
            parsed = {}

    if isinstance(parsed, list):
        return {"top_services": _as_list_dict(parsed), "schemes": []}

    if not isinstance(parsed, dict):
        return {"top_services": [], "schemes": []}

    top_services = _as_list_dict(parsed.get("services", []))
    raw_schemes = _as_list_dict(parsed.get("schemes", []))
    schemes: List[Dict[str, Any]] = []
    for sch in raw_schemes:
        services = _as_list_dict(sch.get("services", []))
        if not services and "service_list" in sch:
            services = _as_list_dict(sch.get("service_list", []))
        sch_copy = dict(sch)
        sch_copy["services"] = services
        schemes.append(sch_copy)

    # 与 Excel 逻辑保持一致：首方案为空时，用顶层 services 回填
    if schemes and not schemes[0].get("services") and top_services:
        schemes[0]["services"] = list(top_services)

    return {"top_services": top_services, "schemes": schemes}


def resolve_generation_scope(
    service_list_json: Optional[str],
    selected_scheme_name: Optional[str] = None,
    selected_scheme_index: Optional[int] = None,
) -> Dict[str, Any]:
    """
    统一生成范围：
    - selected_schemes: 选中的方案列表（为空表示单方案/顶层 services）
    - services_with_scheme: 展平后的服务列表（包含 _scheme_group）
    - has_multi: 是否多方案
    """
    payload = parse_payload(service_list_json)
    top_services: List[Dict[str, Any]] = payload["top_services"]
    schemes: List[Dict[str, Any]] = payload["schemes"]

    chosen_schemes: List[Dict[str, Any]]
    if not schemes:
        chosen_schemes = []
    else:
        chosen_schemes = list(schemes)
        if selected_scheme_index is not None:
            if selected_scheme_index < 1 or selected_scheme_index > len(schemes):
                raise ValueError(f"所选方案序号无效: {selected_scheme_index}")
            chosen_schemes = [schemes[selected_scheme_index - 1]]
        elif selected_scheme_name:
            target = selected_scheme_name.strip().lower()
            matched = None
            for sch in schemes:
                name = str(sch.get("scheme_name", "")).strip()
                if name.lower() == target:
                    matched = sch
                    break
            if not matched:
                for sch in schemes:
                    name = str(sch.get("scheme_name", "")).strip().lower()
                    if target and (target in name or name in target):
                        matched = sch
                        break
            if not matched:
                raise ValueError(f"未找到指定方案: {selected_scheme_name}")
            chosen_schemes = [matched]

    services_with_scheme: List[Dict[str, Any]] = []
    if chosen_schemes:
        for sch in chosen_schemes:
            sch_name = str(sch.get("scheme_name", "")).strip()
            for svc in _as_list_dict(sch.get("services", [])):
                item = dict(svc)
                item["_scheme_group"] = sch_name
                services_with_scheme.append(item)
    else:
        for svc in top_services:
            item = dict(svc)
            item["_scheme_group"] = ""
            services_with_scheme.append(item)

    return {
        "top_services": top_services,
        "all_schemes": schemes,
        "selected_schemes": chosen_schemes,
        "services_with_scheme": services_with_scheme,
        "has_multi": len(chosen_schemes) > 1,
    }

