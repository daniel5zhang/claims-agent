"""
输出文件命名工具

规则：
1) 优先使用“总体方案名称”
2) 若无法识别总体方案名称，则根据会话需求生成业务名称
3) 最终文件名格式：<名称>_v<版本>_<时间戳>.<ext>
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Optional

from services.scheme_payload_resolver import parse_payload


_TIER_PREFIX_RE = re.compile(r"^\s*方案[一二三四五六七八九十0-9]+\s*[-_:：、.．]?\s*")
_INVALID_FILENAME_CHARS_RE = re.compile(r'[\\/:*?"<>|]+')


def _strip_tier_prefix(name: str) -> str:
    return _TIER_PREFIX_RE.sub("", (name or "").strip())


def _is_meaningful_name(name: str) -> bool:
    if not name:
        return False
    pure = re.sub(r"\s+", "", name)
    if len(pure) < 2:
        return False
    # 至少包含中文或英文字母，避免仅价格/符号
    if not re.search(r"[A-Za-z\u4e00-\u9fff]", pure):
        return False
    # 纯价格描述不作为“总体方案名”
    if re.fullmatch(r"[0-9元/人年月.（）()\-_]+", pure):
        return False
    return True


def _common_prefix_name(scheme: Any) -> str:
    try:
        payload = parse_payload(scheme.service_list_json)
        names = []
        for sch in payload.get("schemes", []):
            cleaned = _strip_tier_prefix(str(sch.get("scheme_name", "")))
            if _is_meaningful_name(cleaned):
                names.append(cleaned)
        if len(names) < 2:
            return ""
        prefix = os.path.commonprefix(names).strip(" -_:：，,（(【[")
        return prefix if _is_meaningful_name(prefix) else ""
    except Exception:
        return ""


def _build_name_from_needs(scheme: Any, conversation: Optional[Any]) -> str:
    needs = {}
    if conversation and conversation.extracted_needs_json:
        try:
            needs = json.loads(conversation.extracted_needs_json)
        except Exception:
            needs = {}

    title = (conversation.title or "").strip() if conversation else ""
    title = _strip_tier_prefix(title)
    if _is_meaningful_name(title):
        return title

    target_group = str(needs.get("target_group") or scheme.target_group or "").strip()
    scene = str(needs.get("scene") or scheme.scene or "").strip()
    scale = str(needs.get("scale") or "").strip()
    budget = str(needs.get("budget_range") or "").strip()

    parts = [p for p in [target_group, scene, scale, budget] if p]
    if parts:
        return f"{'·'.join(parts[:2])}健康服务方案"
    return "健康服务方案"


def build_output_base_name(
    scheme: Any,
    conversation: Optional[Any],
) -> str:
    # 1) 先取当前方案名（去掉“方案一/二”前缀）
    direct = _strip_tier_prefix(scheme.scheme_name or "")
    if _is_meaningful_name(direct):
        return direct

    # 2) 尝试从多档方案名提取公共前缀（总体名）
    prefix = _common_prefix_name(scheme)
    if _is_meaningful_name(prefix):
        return prefix

    # 3) 兜底：根据会话需求生成
    return _build_name_from_needs(scheme, conversation)


def make_output_filename(base_name: str, version: int, ext: str) -> str:
    safe_name = _INVALID_FILENAME_CHARS_RE.sub("_", (base_name or "").strip())
    safe_name = re.sub(r"\s+", "_", safe_name).strip("._")
    if not safe_name:
        safe_name = "健康服务方案"
    safe_name = safe_name[:60]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = (ext or "").lstrip(".")
    return f"{safe_name}_v{version}_{timestamp}.{ext}"
