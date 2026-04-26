"""
Agent 对话逻辑核心
- 多轮对话收集需求
- 意图判断（由模型自主决策，不用 if-else 硬编码）
- 方案生成与调整
- 范围校验
- 定价引擎集成
"""
import json
import re
import uuid
import logging
from typing import Optional, Dict, Any, List
from decimal import Decimal

logger = logging.getLogger("agent_service")

from sqlalchemy.orm import Session

from database import (
    Conversation, GeneratedScheme, Service,
    PricingParams, PricingLogic, PricingRule,
    UserFeatureRequest,
)
from services.baiyan_client import get_baiyan_client
from services.pricing_engine import (
    PricingEngine, PricingParams as EnginePricingParams,
    ServicePricingInput,
)
from services.pricing_knowledge import PricingKnowledgeBase

# 从独立文件加载 prompt（便于维护和 diff）
import os as _os
_PROMPTS_DIR = _os.path.join(_os.path.dirname(__file__), "..", "prompts")


def _load_prompt(filename: str) -> str:
    path = _os.path.join(_PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


SYSTEM_PROMPT = _load_prompt("system_prompt.txt")
NEEDS_EXTRACTION_PROMPT = _load_prompt("needs_extraction_prompt.txt")
SCHEME_EXTRACTION_PROMPT = _load_prompt("scheme_extraction_prompt.txt")
INTENT_CLASSIFICATION_PROMPT = _load_prompt("intent_classification_prompt.txt")


def _make_safe_messages(messages):
    """安全序列化消息列表，处理不可序列化的对象"""
    safe = []
    for m in messages:
        if isinstance(m, dict):
            safe.append({k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v for k, v in m.items()})
        else:
            safe.append(str(m))
    return safe



class AgentService:
    """Agent 服务"""

    def __init__(self):
        self.baiyan = get_baiyan_client()
        self._out_of_scope_reply = (
            "我专注于帮您生成健康管理服务方案与报价。我可以：\n"
            "1. 根据您的需求（人群、预算、场景）生成多档位服务方案\n"
            "2. 方案确认后自动生成 Excel 报价单和 Word 服务手册\n"
            "3. 根据反馈随时调整方案内容\n\n"
            "如果您有其他需求，我会帮您记录下来反馈给产品团队。"
            "请问有什么方案需求我可以帮您处理？"
        )

    async def _detect_user_intent(self, messages: List[Dict[str, Any]], user_message: str) -> Dict[str, Any]:
        """使用 LLM 进行语义意图识别（失败时回退关键词规则）"""
        context_messages = messages[-6:] if messages else []
        context_text = "\n".join(
            [f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in context_messages]
        )
        user_text = (user_message or "").strip()

        llm_messages = [
            {"role": "system", "content": INTENT_CLASSIFICATION_PROMPT},
            {
                "role": "user",
                "content": (
                    f"用户最新输入：{user_text}\n\n"
                    f"最近对话上下文：\n{context_text}"
                ),
            },
        ]

        try:
            response = await self.baiyan.chat_completion(
                llm_messages,
                model="qwen-turbo",
                temperature=0.0,
                max_tokens=256,
            )
            text = self.baiyan.extract_content(response).strip()

            json_text = None
            if text.startswith("{") and text.endswith("}"):
                json_text = text
            else:
                json_text = self._find_first_balanced_json(text)

            if json_text:
                data = json.loads(json_text)
                intent = data.get("intent", "other")
                if intent in {
                    "confirm_scheme",
                    "adjust_scheme",
                    "cancel_or_retry",
                    "out_of_scope_request",
                    "other",
                }:
                    return {
                        "intent": intent,
                        "confidence": float(data.get("confidence", 0.0) or 0.0),
                        "reason": data.get("reason", ""),
                        "source": "llm",
                    }
        except Exception as e:
            logger.warning(f"[_detect_user_intent] LLM 识别失败，回退规则: {e}")

        # 兜底：仅用于 LLM 异常或返回不可解析时，保证可用性
        fallback_confirm = self._is_confirm_message(user_text)
        return {
            "intent": "confirm_scheme" if fallback_confirm else "other",
            "confidence": 0.3,
            "reason": "fallback_rule",
            "source": "fallback",
        }

    def _build_pricing_context_for_llm(
        self,
        db: Session,
        services: List[Dict],
        needs: Dict,
    ) -> str:
        """
        构建定价上下文 — 注入到 system prompt 中
        包含：规则引擎基准价、历史方案定价逻辑、行业约束
        """
        engine = PricingEngine(db)
        kbase = PricingKnowledgeBase(db)

        context_parts = ["\n\n## 定价基准参考（由精算引擎计算，仅供参考）\n"]

        # 1. 提取需求参数
        volume = 50000  # 默认
        scene = needs.get("scene", "")
        if "随车" in scene:
            volume = 50000
        elif "银行" in scene:
            volume = 30000

        # 自动选择发生率列
        usage_col = "large" if volume >= 50000 else "small"

        # 默认定价参数
        engine_params = EnginePricingParams(
            margin_rate=Decimal("0.15"),
            channel_coeff=Decimal("1.0"),
            package_discount=Decimal("0.90"),
            rounding_rule="round_yuan",
            volume=volume,
            usage_rate_column=usage_col,
        )

        # 2. 对方案中的服务逐项计算引擎基准价
        if services:
            context_parts.append("| 服务名称 | 成本价 | 预期发生率 | 预期成本 | 基准报价(15%利润) |")
            context_parts.append("|---------|--------|-----------|---------|-----------------|")

            for svc in services:
                name = svc.get("name", "")
                if not name:
                    continue
                pricing_input = engine.load_service_pricing_input(name, engine_params)
                if pricing_input:
                    try:
                        result = engine.calculate_single_service(pricing_input, engine_params)
                        context_parts.append(
                            f"| {name} | {result.cost_price} | "
                            f"{float(result.usage_rate)*100:.1f}% | "
                            f"{result.expected_cost:.2f} | {result.quoted_price:.2f} |"
                        )
                    except Exception:
                        context_parts.append(
                            f"| {name} | {pricing_input.cost_price} | "
                            f"{float(pricing_input.usage_rate)*100:.1f}% | - | - |"
                        )
                else:
                    context_parts.append(f"| {name} | 无成本数据 | - | - | - |")

            context_parts.append("")

        # 3. 查询相似历史方案的定价逻辑
        similar = kbase.find_similar_schemes(
            scene=needs.get("scene", ""),
            volume=volume,
            top_k=2,
        )

        if similar:
            context_parts.append("## 历史同类方案定价逻辑参考\n")
            for i, sim in enumerate(similar):
                context_parts.append(f"### {sim['scheme_name']}（{sim['pricing_method']}）")
                if sim.get("logic_description"):
                    context_parts.append(f"{sim['logic_description'][:300]}")
                if sim.get("extracted_rules"):
                    rules = sim["extracted_rules"]
                    if isinstance(rules, dict):
                        margin = rules.get("estimated_margin")
                        if margin:
                            context_parts.append(f"- 估算利润率: {margin.get('avg', 'N/A')}")
                        rounding = rules.get("detected_rounding")
                        if rounding:
                            context_parts.append(f"- 取整规则: {rounding}")
                        tier_info = rules.get("tier_analysis", {})
                        if tier_info.get("tier_count", 0) > 1:
                            context_parts.append(f"- 档位: {tier_info['tier_count']}档, "
                                               f"递增约{tier_info.get('multiplier_avg', 'N/A')}倍")
                context_parts.append("")

        # 4. 行业定价约束
        context_parts.append("## 行业定价约束")
        context_parts.append("- 健康管理成本不超过净保费20%（金发〔2025〕34号试点可突破）")
        context_parts.append("- 报价需可追溯至成本价+发生率+利润率的计算链路")
        context_parts.append("- 不同场景可使用不同利润率（随车15%、银行18%、职工福利12%）")
        context_parts.append(f"- 当前场景: {scene or '未指定'}, 建议基准利润率: 15%")
        context_parts.append("")

        return "\n".join(context_parts)

    async def process_message(
        self, db: Session, session_id: Optional[str], user_message: str, user_id: str = ""
    ) -> Dict[str, Any]:
        """处理用户消息，返回 Agent 回复"""
        logger.info(f"[process_message] 开始处理, user_message={user_message[:50]}...")

        # 获取或创建会话
        conversation = self._get_or_create_conversation(db, session_id, user_id=user_id)
        session_id = conversation.session_id

        # 加载历史消息
        messages = self._load_messages(conversation)
        messages.append({"role": "user", "content": user_message})

        # 构建完整 prompt（系统提示 + 定价上下文 + 历史消息）
        # 从历史中提取已收集的需求用于构建定价上下文
        pricing_context = ""
        try:
            prev_needs = json.loads(conversation.extracted_needs_json or "{}")
        except json.JSONDecodeError:
            prev_needs = {}
        if prev_needs.get("needs_complete"):
            pricing_context = self._build_pricing_context_for_llm(db, [], prev_needs)

        system_with_context = SYSTEM_PROMPT + pricing_context
        full_messages = [{"role": "system", "content": system_with_context}] + messages

        # 调用百炼获取回复
        logger.info(f"[process_message] 调用 LLM...")
        response = await self.baiyan.chat_completion(full_messages, max_tokens=8192)
        assistant_content = self.baiyan.extract_content(response)
        logger.info(f"[process_message] LLM 返回 {len(assistant_content)} 字符")

        # AI 调用返回空内容时的降级处理
        if not assistant_content or not assistant_content.strip():
            assistant_content = (
                "抱歉，当前服务暂时无法响应，请稍后重试。"
                "如问题持续出现，请联系客服400-xxx-xxxx获取帮助。"
            )

        # 检测并记录超范围需求
        self._detect_and_record_feature_request(
            db, conversation, user_message, assistant_content, user_id
        )

        # 在返回内容之前清理标记（用户不应该看到）
        assistant_content = re.sub(r'\[FEATURE_REQUEST:\s*[^\]]+\]', '', assistant_content).strip()

        # 过滤虚假能力声明
        assistant_content = self._filter_false_claims(assistant_content)

        # 将助手回复加入消息历史
        messages.append({"role": "assistant", "content": assistant_content})

        # LLM 语义意图识别（确认/调整/取消/其他）
        intent_info = await self._detect_user_intent(messages, user_message)
        user_intent = intent_info.get("intent", "other")
        is_confirm_msg = user_intent == "confirm_scheme"
        is_adjust_msg = user_intent == "adjust_scheme"
        is_cancel_or_retry_msg = user_intent == "cancel_or_retry"
        is_out_of_scope_msg = user_intent == "out_of_scope_request"
        logger.info(
            f"[process_message] user_intent={user_intent}, source={intent_info.get('source')}, "
            f"confidence={intent_info.get('confidence')}"
        )

        if is_out_of_scope_msg:
            # 流程外需求：固定回复 + 记录需求（兜底），不进入方案提取/状态流转链路
            assistant_content = self._out_of_scope_reply
            messages[-1]["content"] = assistant_content
            self._save_feature_request(
                db=db,
                conversation=conversation,
                user_message=user_message,
                summary=(user_message or "").strip()[:180],
                user_id=user_id,
            )

        # 调整/取消类意图：统一走状态机（必要时将 confirmed 回退为 draft）
        transitioned_scheme = self._handle_non_confirm_intent_state(
            db, conversation.id, user_intent
        )

        # 如果是确认意图且已有草稿方案，跳过方案提取（避免 LLM 回复中的
        # 部分方案数据覆盖已落库的完整多方案数据）
        existing_draft = None
        if is_confirm_msg:
            existing_draft = db.query(GeneratedScheme).filter(
                GeneratedScheme.conversation_id == conversation.id,
                GeneratedScheme.status == "draft",
            ).first()
            if existing_draft:
                logger.info(f"[process_message] 确认意图+已有草稿 gen_scheme.id={existing_draft.id}，跳过方案提取")

        # 检测是否包含方案 → 用小模型从 markdown 提取结构化数据
        scheme_data = None
        if existing_draft:
            logger.info("[process_message] 跳过方案提取（使用已有草稿）")
        elif is_out_of_scope_msg:
            logger.info("[process_message] 流程外需求意图，跳过方案提取")
        elif self._is_scheme_response(assistant_content):
            logger.info("[process_message] 检测到方案内容，调小模型提取...")
            scheme_data = await self._extract_scheme_via_llm(assistant_content)
        else:
            logger.info("[process_message] 未检测到方案内容，跳过提取")

        scheme_out = None
        logger.info(
            f"[process_message] scheme_data={scheme_data is not None}, "
            f"is_confirm_msg={is_confirm_msg}, "
            f"is_adjust_msg={is_adjust_msg}, "
            f"is_cancel_or_retry_msg={is_cancel_or_retry_msg}, "
            f"is_out_of_scope_msg={is_out_of_scope_msg}, "
            f"has_draft={existing_draft is not None}"
        )

        # 快速提取需求状态（无需额外 LLM 调用）
        needs = self._extract_needs_fast(assistant_content, user_message, prev_needs, scheme_data)
        needs_status = "complete" if needs.get("needs_complete") else "collecting"

        if existing_draft:
            # 确认已有草稿方案（保留完整的多方案数据）
            scheme_out = self._check_confirm_intent(
                db, conversation.id, user_message, assistant_content, is_confirm_intent=is_confirm_msg
            )
        elif scheme_data:
            # 范围校验
            validated_scheme, out_of_scope = self._validate_scheme(db, scheme_data)
            if out_of_scope:
                # 如果有超范围服务，追加提示
                warning = f"\n\n【范围提示】以下服务不在素材库中，已自动过滤：{', '.join(out_of_scope)}"
                assistant_content += warning
                messages[-1]["content"] = assistant_content
            scheme_out = validated_scheme
            # 保存生成的方案（传入 needs 用于引擎计算），并将数据库 ID 注入 scheme_out
            if validated_scheme and validated_scheme.get("services"):
                gen = self._save_generated_scheme(db, conversation.id, validated_scheme, needs=needs)
                scheme_out["id"] = gen.id
                scheme_out["status"] = gen.status

                # 用户发送确认消息时（LLM 可能重新输出 JSON），直接确认方案
                if is_confirm_msg:
                    logger.info(f"[process_message] 检测到确认意图，标记方案 {gen.id} 为 confirmed")
                    gen.status = "confirmed"
                    gen.final_total_cost = gen.engine_total_cost or gen.total_cost
                    gen.final_total_quote = gen.llm_total_quote or gen.total_quote
                    db.commit()
                    scheme_out["status"] = "confirmed"
                    # 保存定价逻辑
                    raw_data = json.loads(gen.service_list_json or "{}")
                    if isinstance(raw_data, dict):
                        pricing_logic_data = raw_data.get("pricing_logic") or raw_data.get("pricing_analysis")
                        if pricing_logic_data:
                            self._save_pricing_logic_from_confirmation(db, gen, pricing_logic_data)
        elif is_confirm_msg:
            # 没有新方案 JSON，纯确认消息
            scheme_out = self._check_confirm_intent(
                db, conversation.id, user_message, assistant_content, is_confirm_intent=is_confirm_msg
            )
        elif transitioned_scheme:
            # 调整/取消意图的状态流转结果（无新方案 JSON 时回传当前草稿方案）
            scheme_out = transitioned_scheme
        else:
            scheme_out = None

        # 更新对话记录
        # 首次对话时设置会话标题
        if not conversation.title and user_message:
            conversation.title = user_message[:30]
        try:
            messages_json = json.dumps(messages, ensure_ascii=False)
            # 安全截断：保留最近消息，确保不超 MEDIUMTEXT 上限（900KB）
            if len(messages_json.encode('utf-8')) > 900 * 1024:
                logger.warning(f"[agent] messages_json 过大({len(messages_json)} chars), 截断中...")
                while len(json.dumps(messages, ensure_ascii=False).encode('utf-8')) > 900 * 1024 and len(messages) > 4:
                    messages.pop(0)
                messages_json = json.dumps(messages, ensure_ascii=False)
                logger.info(f"[agent] 截断后 len={len(messages_json)}")
            logger.info(f"[agent] messages_json 序列化成功, len={len(messages_json)}")
        except Exception as e:
            logger.error(f"[agent] messages_json 序列化失败: {e}")
            messages_json = json.dumps(_make_safe_messages(messages), ensure_ascii=False)
        try:
            needs_json = json.dumps(needs, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[agent] needs_json 序列化失败: {e}")
            needs_json = "{}"
        conversation.messages_json = messages_json
        conversation.extracted_needs_json = needs_json
        db.commit()

        # 始终从消息文本中剥离 JSON 代码块，避免前端显示原始 JSON
        display_content = self._strip_json_block(assistant_content)
        if display_content.strip():
            assistant_content = display_content

        # 统一 scheme 输出格式（前端期望 service_list 而非 services）
        if scheme_out:
            scheme_out = dict(scheme_out)
            all_schemes = scheme_out.pop("_all_schemes", None)
            if "services" in scheme_out and "service_list" not in scheme_out:
                scheme_out["service_list"] = scheme_out.pop("services")
            if all_schemes:
                scheme_out["schemes"] = all_schemes

            # 如果剥离 JSON 后文字为空，生成简短摘要
            if not display_content.strip():
                svc_count = len(scheme_out.get("service_list", []))
                assistant_content = (
                    f"已为您生成方案：**{scheme_out.get('scheme_name', '未命名方案')}**，"
                    f"共 {svc_count} 项服务。请查看下方方案详情。"
                )

        result = {
            "session_id": session_id,
            "message": {"role": "assistant", "content": assistant_content},
            "scheme": scheme_out,
            "needs_status": needs_status,
        }
        logger.info(
            f"[process_message] 完成, session_id={session_id}, "
            f"has_scheme={scheme_out is not None}, "
            f"scheme_status={scheme_out.get('status') if scheme_out else 'N/A'}"
        )
        return result

    async def adjust_scheme(
        self, db: Session, scheme_id: int, adjustment_prompt: str
    ) -> Dict[str, Any]:
        """根据用户调整要求修改方案"""
        # 查找现有方案
        gen_scheme = db.query(GeneratedScheme).filter(GeneratedScheme.id == scheme_id).first()
        if not gen_scheme:
            return {"error": "方案不存在"}

        if gen_scheme.status == "confirmed":
            return {"error": "方案已确认，如需调整请先取消确认"}

        # 获取当前方案的服务列表
        current_services = json.loads(gen_scheme.service_list_json or "[]")
        services_text = "\n".join([
            f"- {s.get('name')}: {s.get('times')}, 报价{s.get('price')}元"
            for s in current_services
        ])

        # 构建调整 prompt
        adjust_prompt = f"""当前方案包含以下服务：
{services_text}

用户要求调整：{adjustment_prompt}

请重新生成调整后的方案，确保所有服务都在素材库范围内。
使用相同的 JSON 格式输出。"""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": adjust_prompt},
        ]

        response = await self.baiyan.chat_completion(messages)
        assistant_content = self.baiyan.extract_content(response)

        if not assistant_content or not assistant_content.strip():
            return {
                "error": "方案调整失败，AI 服务暂时无响应，请稍后重试",
                "message": {"role": "assistant", "content": "抱歉，方案调整暂时无法完成，请稍后重试。"},
            }

        scheme_data = self._parse_scheme_from_response(assistant_content)
        if scheme_data:
            validated_scheme, out_of_scope = self._validate_scheme(db, scheme_data)
            if out_of_scope:
                assistant_content += f"\n\n【范围提示】以下服务不在素材库中，已自动过滤：{', '.join(out_of_scope)}"
            # 更新方案
            gen_scheme.service_list_json = json.dumps(validated_scheme.get("services", []), ensure_ascii=False)
            gen_scheme.scheme_name = validated_scheme.get("scheme_name", gen_scheme.scheme_name)
            db.commit()
            validated_scheme["id"] = gen_scheme.id
            validated_scheme["status"] = gen_scheme.status
            return {
                "message": {"role": "assistant", "content": assistant_content},
                "scheme": validated_scheme,
            }

        return {"message": {"role": "assistant", "content": assistant_content}}

    def _get_or_create_conversation(
        self, db: Session, session_id: Optional[str], user_id: str = ""
    ) -> Conversation:
        if session_id:
            conv = db.query(Conversation).filter(
                Conversation.session_id == session_id,
                Conversation.user_id == user_id,
            ).first()
            if conv:
                return conv
        # 新建会话（使用 flush 避免 seekdb 中 commit 后对象过期导致 UPDATE 不匹配）
        conv = Conversation(
            session_id=str(uuid.uuid4()).replace("-", ""),
            user_id=user_id,
            messages_json="[]",
            extracted_needs_json="{}",
        )
        db.add(conv)
        db.flush()
        # seekdb 中 refresh 可能导致主键不一致，直接用 flush 后的对象
        return conv

    def _load_messages(self, conversation: Conversation) -> List[Dict[str, str]]:
        try:
            return json.loads(conversation.messages_json or "[]")
        except json.JSONDecodeError:
            return []

    def _extract_needs_fast(
        self, assistant_content: str, user_message: str,
        prev_needs: dict, scheme_data: dict = None,
    ) -> Dict[str, Any]:
        """从 LLM 主回复中快速提取需求状态（纯规则，0延迟，替代之前的二次 LLM 调用）

        策略：
        - 回复包含方案JSON → 需求完整，从方案数据补充
        - 回复包含追问 → 需求不完整，从用户消息中提取已知信息
        """
        needs = dict(prev_needs) if prev_needs else {}

        # 1. 检测方案JSON：需求已完整
        has_scheme = bool(scheme_data) or (
            '```json' in assistant_content and '"services"' in assistant_content
        )
        if has_scheme:
            needs["needs_complete"] = True
            # 从方案数据补充场景信息
            if scheme_data:
                for key in ('scene', 'target_group', 'channel', 'scale'):
                    if scheme_data.get(key) and not needs.get(key):
                        needs[key] = scheme_data[key]
            return needs

        # 2. 检测是否在追问（有问号 或 关键词）
        asking = bool(re.search(r'[？?]', assistant_content))
        asking |= any(kw in assistant_content for kw in [
            '请问', '请提供', '请确认', '请补充', '请告知', '还需要',
            '才能为您', '请先', '需要您', '告知',
        ])
        if asking:
            needs["needs_complete"] = False

        # 3. 从用户消息提取已知需求（累计到 prev_needs 中）
        # 提取场景
        scene_map = [
            (r'随车|车险|车主|驾车|随车健管', 'car_insurance'),
            (r'职工|企业|员工福利|团险|团体', 'employee_benefit'),
            (r'银行|城商行|小微|金融', 'banking'),
            (r'重疾|防癌|癌症|肿瘤', 'critical_illness'),
            (r'绿通|就医|挂号|门诊', 'green_channel'),
        ]
        for pattern, scene_id in scene_map:
            if re.search(pattern, user_message) and not needs.get("scene"):
                needs["scene"] = scene_id
                break

        # 提取预算（元/人 格式）
        budget_match = re.search(r'(\d+)\s*元\s*/\s*[人年]', user_message)
        if budget_match and not needs.get("budget_range"):
            needs["budget_range"] = f'{budget_match.group(1)}元/人/年'
            needs["budget_unit"] = 'per_person'

        # 提取规模（万单）
        scale_match = re.search(r'(\d+)\s*万\s*单', user_message)
        if scale_match and not needs.get("scale"):
            needs["scale"] = f'{scale_match.group(1)}万单'

        # 提取目标人群
        group_match = re.search(r'(车险车主|企业员工|银行客户|团险客户)', user_message)
        if group_match and not needs.get("target_group"):
            needs["target_group"] = group_match.group(1)

        # 4. 如果还不够明确，设为不完整
        if "needs_complete" not in needs:
            needs["needs_complete"] = False

        return needs

    @staticmethod
    def _strip_json_block(text: str) -> str:
        """从 LLM 回复中移除 JSON 代码块，保留纯文本部分"""
        import re as _re
        # 移除 ```json ... ``` 代码块
        text = _re.sub(r'```json\s*[\s\S]*?```', '', text)
        # 移除 ``` ... ``` 代码块
        text = _re.sub(r'```[\s\S]*?```', '', text)
        # 移除平衡括号的 JSON 对象（处理嵌套）
        text = AgentService._strip_balanced_json(text)
        return text.strip()

    @staticmethod
    def _strip_balanced_json(text: str) -> str:
        """移除文本中所有平衡括号的 JSON 对象 { ... }"""
        result = []
        i = 0
        while i < len(text):
            if text[i] == '{':
                depth = 1
                j = i + 1
                while j < len(text) and depth > 0:
                    if text[j] == '{':
                        depth += 1
                    elif text[j] == '}':
                        depth -= 1
                    j += 1
                if depth == 0:
                    # 找到了平衡的 JSON 对象，跳过它
                    i = j
                    continue
            result.append(text[i])
            i += 1
        return ''.join(result)

    async def _extract_needs(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """LLM 深度需求提取（仅用于复杂场景，作为 _extract_needs_fast 的后备）"""
        extraction_messages = [
            {"role": "system", "content": NEEDS_EXTRACTION_PROMPT},
            {"role": "user", "content": f"请从以下对话中提取客户需求信息：\n\n{json.dumps(messages, ensure_ascii=False)}"},
        ]
        try:
            response = await self.baiyan.chat_completion(extraction_messages, temperature=0.1, max_tokens=256)
            # 兼容百炼多种返回格式
            text = self.baiyan.extract_content(response)
            # 尝试从 JSON 代码块中提取
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            needs = json.loads(text)
            return needs
        except Exception:
            return {"needs_complete": False}


    async def _extract_scheme_via_llm(self, markdown_text: str) -> Optional[Dict[str, Any]]:
        """用 flash 小模型（qwen-turbo）从 markdown 提取结构化方案数据"""
        import time
        logger.info(
            f"[_extract_scheme_via_llm] 开始提取, markdown长度={len(markdown_text)}, "
            f"前200字={markdown_text[:200]}"
        )
        t0 = time.time()
        try:
            messages = [
                {"role": "system", "content": SCHEME_EXTRACTION_PROMPT},
                {"role": "user", "content": markdown_text},
            ]
            response = await self.baiyan.chat_completion(
                messages,
                model="qwen-turbo",
                temperature=0.0,
                max_tokens=8192,
            )
            text = self.baiyan.extract_content(response)
            elapsed = time.time() - t0
            logger.info(
                f"[_extract_scheme_via_llm] 小模型返回, 耗时={elapsed:.1f}s, "
                f"内容长度={len(text)}, 前200字={text[:200]}"
            )
            # 复用现有 JSON 解析器（支持代码块和无代码块两种格式）
            result = self._parse_scheme_from_response(text)
            if result:
                logger.info(
                    f"[_extract_scheme_via_llm] 解析成功, "
                    f"scheme_name={result.get('scheme_name', 'N/A')}, "
                    f"services={len(result.get('services', []))} 项"
                )
            else:
                logger.warning(f"[_extract_scheme_via_llm] 解析失败, 小模型返回无法解析: {text[:300]}")
            return result
        except Exception as e:
            elapsed = time.time() - t0
            logger.error(f"[_extract_scheme_via_llm] 异常, 耗时={elapsed:.1f}s, error={e}")
            return None

    @staticmethod
    def _find_json_in_text(text: str) -> Optional[str]:
        """从无代码块的文本中提取 JSON 对象（找包含 scheme 特征字段的平衡括号块）"""
        import re as _re
        # scheme 特征字段（JSON key 格式）
        scheme_keys = [
            '"services"', '"service_list"', '"type"', '"scheme_name"',
            '"total_quote"', '"total_cost"', '"schemes"',
            '"pricing_logic"', '"pricing_method"',
        ]
        # 找所有 { 的位置，尝试匹配平衡括号
        for match in _re.finditer(r'\{', text):
            start = match.start()
            depth = 1
            end = start + 1
            while end < len(text) and depth > 0:
                if text[end] == '{':
                    depth += 1
                elif text[end] == '}':
                    depth -= 1
                end += 1
            if depth == 0:
                candidate = text[start:end]
                # 检查是否包含任一 scheme 特征字段
                if any(k in candidate for k in scheme_keys):
                    logger.info(f"[_find_json_in_text] 找到候选 JSON, len={len(candidate)}, "
                                f"preview={candidate[:120]}...")
                    return candidate
        logger.info(f"[_find_json_in_text] 未找到 scheme JSON, text 前200字: {text[:200]}")
        return None

    @staticmethod
    def _find_first_balanced_json(text: str) -> Optional[str]:
        """提取文本中的第一个平衡 JSON 对象（通用）"""
        import re as _re
        for match in _re.finditer(r'\{', text):
            start = match.start()
            depth = 1
            end = start + 1
            while end < len(text) and depth > 0:
                if text[end] == '{':
                    depth += 1
                elif text[end] == '}':
                    depth -= 1
                end += 1
            if depth == 0:
                return text[start:end]
        return None

    def _parse_scheme_from_response(self, text: str) -> Optional[Dict[str, Any]]:
        """从模型回复中解析方案 JSON，支持 schemes 数组和单方案兼容"""
        try:
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0].strip()
                logger.info(f"[_parse_scheme] 找到 ```json 代码块, len={len(json_str)}")
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0].strip()
                logger.info(f"[_parse_scheme] 找到 ``` 代码块, len={len(json_str)}")
            else:
                # 无代码块：尝试从文本中找到平衡的 JSON 对象
                logger.info(f"[_parse_scheme] 无代码块, 尝试 _find_json_in_text")
                json_str = self._find_json_in_text(text)
                if not json_str:
                    return None
            data = json.loads(json_str)
            if data.get("type") == "scheme":
                # 兼容新旧格式：如果包含 schemes 数组，转换为单方案包装
                if "schemes" in data and isinstance(data["schemes"], list) and data["schemes"]:
                    import copy
                    schemes_copy = copy.deepcopy(data["schemes"])
                    # 直接引用第一个元素（同一对象），避免双深拷贝导致 validation 丢失
                    first = schemes_copy[0]
                    first["_all_schemes"] = schemes_copy
                    return first
                elif "services" in data:
                    return data
            elif "services" in data:
                return data
        except json.JSONDecodeError as e:
            logger.warning(f"[_parse_scheme] JSON 解析失败: {e}, json_str前200字={json_str[:200]}")
        except Exception as e:
            logger.warning(f"[_parse_scheme] 解析异常: {e}")
        return None

    def _validate_scheme(
        self, db: Session, scheme_data: Dict[str, Any]
    ) -> tuple[Optional[Dict[str, Any]], List[str]]:
        """校验方案中的服务是否都在素材库范围内（处理多方案 _all_schemes）"""
        # 获取素材库中所有服务名称
        db_services = db.query(Service.name).all()
        db_service_names = {s[0] for s in db_services}

        # 常见同义词映射：模型可能用的简称 -> 素材库中的标准名
        _alias_map = {
            "基因检测": "癌症靶向药基因检测服务",
            "专家会诊": "肿瘤MTB多学科会诊服务",
            "全球找药": "全球/海南先行区找药服务",
            "海南找药": "全球/海南先行区找药服务",
            "购药金": "购药金代金券",
            "视频问诊": "视频问诊",
            "图文问诊": "图文问诊",
        }

        def _validate_services(services):
            """校验单个方案的服务列表，返回 (valid_services, out_of_scope)"""
            valid_services = []
            out_of_scope = []
            for svc in services:
                svc_name = svc.get("name", "")
                if not svc_name:
                    continue
                # 1. 精确匹配
                if svc_name in db_service_names:
                    valid_services.append(svc)
                    continue
                # 2. 子串匹配
                matched = any(svc_name in db_name or db_name in svc_name for db_name in db_service_names)
                if matched:
                    valid_services.append(svc)
                    continue
                # 3. 同义词匹配
                alias_matched = False
                for alias, std_name in _alias_map.items():
                    if alias in svc_name or svc_name in alias:
                        svc["name"] = std_name
                        alias_matched = True
                        break
                if alias_matched:
                    valid_services.append(svc)
                    continue
                # 4. 核心关键词匹配（提取2字以上关键词）
                kw_matched = False
                for db_name in db_service_names:
                    core = db_name.replace("服务", "").replace("权益", "").replace("优惠", "")
                    if len(core) >= 2 and (core in svc_name or svc_name in core):
                        kw_matched = True
                        break
                if kw_matched or not db_service_names:
                    valid_services.append(svc)
                else:
                    out_of_scope.append(svc_name)
            return valid_services, out_of_scope

        all_out_of_scope = []

        # 校验所有方案的 services（_all_schemes 与 scheme_data 是同一对象引用）
        all_schemes = scheme_data.get("_all_schemes")
        if all_schemes:
            for i, sch in enumerate(all_schemes):
                if isinstance(sch, dict):
                    sch_services = sch.get("services", [])
                    if sch_services:
                        valid, oos = _validate_services(sch_services)
                        sch["services"] = valid
                        all_out_of_scope.extend(oos)
                        logger.info(
                            f"[_validate_scheme] 方案{i+1}: {len(sch_services)}→{len(valid)}, "
                            f"超范围={oos}"
                        )
            # 同步更新顶层 services（第一个方案）
            if all_schemes:
                scheme_data["services"] = all_schemes[0].get("services", [])
        else:
            # 单方案：直接校验顶层 services
            services = scheme_data.get("services", [])
            if services:
                valid, oos = _validate_services(services)
                scheme_data["services"] = valid
                all_out_of_scope = oos

        return scheme_data, all_out_of_scope

    @staticmethod
    def _is_scheme_response(text: str) -> bool:
        """检测 LLM 回复是否包含方案内容（表格 + 服务/价格特征）"""
        # 有 markdown 表格（|...|...| 模式）
        has_table = bool(re.search(r'\|.+\|.+\|', text))
        # 有价格特征（元/人、元/年 等）
        has_price = bool(re.search(r'\d+\s*元\s*/\s*[人年卡]', text))
        # 有服务关键词
        has_service = any(kw in text for kw in [
            '服务项目', '服务内容', '服务次数', '服务标准', '服务网络',
            '方案一', '方案二', '方案三', '方案四',
            '引流档', '基础档', '标准档', '高端档',
            '总报价', '总成本', '方案名称',
        ])
        result = has_table and (has_price or has_service)
        logger.info(
            f"[_is_scheme_response] has_table={has_table}, has_price={has_price}, "
            f"has_service={has_service} → {result}"
        )
        return result

    def _is_confirm_message(self, user_message: str) -> bool:
        """判断用户消息是否为确认意图（不含取消/调整意图）"""
        confirm_keywords = ["确认", "不调整，确认", "按此方案", "就这个", "不用调", "可以确认", "锁定方案"]
        cancel_keywords = ["取消", "再调", "修改", "调整", "换一个", "重新"]
        user_lower = user_message.strip()
        return any(k in user_lower for k in confirm_keywords) and not any(k in user_lower for k in cancel_keywords)

    def _check_confirm_intent(
        self,
        db: Session,
        conversation_id: int,
        user_message: str,
        assistant_content: str,
        is_confirm_intent: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """检测用户确认方案意图，自动将 draft 方案标记为 confirmed 并返回"""
        if not is_confirm_intent:
            return None

        # 查找当前会话的 draft 方案
        gen_scheme = db.query(GeneratedScheme).filter(
            GeneratedScheme.conversation_id == conversation_id,
            GeneratedScheme.status == "draft",
        ).first()
        if not gen_scheme:
            logger.info(f"[_check_confirm_intent] 未找到 draft 方案，conversation_id={conversation_id}")
            return None

        logger.info(f"[_check_confirm_intent] 确认方案 gen_scheme.id={gen_scheme.id}")
        # 标记为 confirmed
        gen_scheme.status = "confirmed"
        # 确认时，final = 当前选定的报价
        gen_scheme.final_total_cost = gen_scheme.engine_total_cost or gen_scheme.total_cost
        gen_scheme.final_total_quote = gen_scheme.llm_total_quote or gen_scheme.total_quote
        db.commit()

        # 确认时，自动保存定价逻辑（如果 LLM 在 JSON 中给出了 pricing_logic）
        raw_data = json.loads(gen_scheme.service_list_json or "{}")
        if isinstance(raw_data, dict):
            pricing_logic_data = raw_data.get("pricing_logic") or raw_data.get("pricing_analysis")
            if pricing_logic_data:
                self._save_pricing_logic_from_confirmation(
                    db, gen_scheme, pricing_logic_data
                )

        return self._build_scheme_out(gen_scheme, status_override="confirmed")

    def _build_scheme_out(
        self, gen_scheme: GeneratedScheme, status_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """从 GeneratedScheme 构建统一输出结构"""
        raw_data = json.loads(gen_scheme.service_list_json or "{}")
        if isinstance(raw_data, dict):
            services = raw_data.get("services", [])
            schemes = raw_data.get("schemes", [])
        else:
            services = raw_data
            schemes = []

        scheme_out = {
            "id": gen_scheme.id,
            "conversation_id": gen_scheme.conversation_id,
            "scheme_name": gen_scheme.scheme_name,
            "scene": gen_scheme.scene,
            "target_group": gen_scheme.target_group,
            "service_list": services,
            "total_cost": float(gen_scheme.total_cost) if gen_scheme.total_cost else 0,
            "total_quote": float(gen_scheme.total_quote) if gen_scheme.total_quote else 0,
            "status": status_override or gen_scheme.status,
        }
        if schemes:
            scheme_out["schemes"] = schemes

        return scheme_out

    def _handle_non_confirm_intent_state(
        self, db: Session, conversation_id: int, intent: str
    ) -> Optional[Dict[str, Any]]:
        """
        非确认意图统一状态机：
        - adjust_scheme: 优先保留 draft；若仅有 confirmed，则回退为 draft
        - cancel_or_retry: 将最新 confirmed 回退为 draft；若已是 draft 则保持
        """
        if intent not in {"adjust_scheme", "cancel_or_retry"}:
            return None

        latest_draft = (
            db.query(GeneratedScheme)
            .filter(
                GeneratedScheme.conversation_id == conversation_id,
                GeneratedScheme.status == "draft",
            )
            .order_by(GeneratedScheme.id.desc())
            .first()
        )

        if intent == "adjust_scheme" and latest_draft:
            logger.info(
                f"[_handle_non_confirm_intent_state] 调整意图，保持 draft 方案 id={latest_draft.id}"
            )
            return self._build_scheme_out(latest_draft)

        latest_confirmed = (
            db.query(GeneratedScheme)
            .filter(
                GeneratedScheme.conversation_id == conversation_id,
                GeneratedScheme.status == "confirmed",
            )
            .order_by(GeneratedScheme.id.desc())
            .first()
        )

        if latest_confirmed:
            latest_confirmed.status = "draft"
            db.commit()
            logger.info(
                f"[_handle_non_confirm_intent_state] intent={intent}, 回退 confirmed->draft, "
                f"scheme_id={latest_confirmed.id}"
            )
            return self._build_scheme_out(latest_confirmed)

        if latest_draft:
            logger.info(
                f"[_handle_non_confirm_intent_state] intent={intent}, 无 confirmed，返回现有 draft id={latest_draft.id}"
            )
            return self._build_scheme_out(latest_draft)

        logger.info(
            f"[_handle_non_confirm_intent_state] intent={intent}, 当前会话无可用方案"
        )
        return None

    def _save_pricing_logic_from_confirmation(
        self,
        db: Session,
        gen_scheme: GeneratedScheme,
        pricing_logic_data: Dict,
    ):
        """确认方案时，保存 LLM 输出的定价逻辑"""
        try:
            # 创建 PricingLogic
            logic = PricingLogic(
                scheme_id=gen_scheme.id,
                scheme_type="generated",
                pricing_method=pricing_logic_data.get("pricing_method") or gen_scheme.pricing_method,
                logic_description=pricing_logic_data.get("logic_description", ""),
                diff_vs_engine=pricing_logic_data.get("adjustments_from_benchmark") and json.dumps(
                    pricing_logic_data["adjustments_from_benchmark"], ensure_ascii=False
                ),
                confidence_score=0.8,
                extracted_by="llm",
            )
            db.add(logic)
            db.flush()

            # 关联到 generated_scheme
            gen_scheme.pricing_logic_id = logic.id

            # 保存定价规则
            rules = pricing_logic_data.get("pricing_rules", [])
            for r in rules:
                rule = PricingRule(
                    logic_id=logic.id,
                    rule_category=r.get("category", "markup"),
                    rule_name=r.get("rule_name", ""),
                    rule_expression=r.get("rule_expression", ""),
                    rule_params_json=json.dumps(r.get("params", {}), ensure_ascii=False),
                    priority=10,
                    is_active=1,
                )
                db.add(rule)

            db.commit()
        except Exception as e:
            import logging
            logging.getLogger("agent_service").warning(f"保存定价逻辑失败: {e}")

    def _save_generated_scheme(
        self, db: Session, conversation_id: int, scheme_data: Dict[str, Any],
        needs: Dict = None,
    ) -> GeneratedScheme:
        """保存生成的方案，支持 schemes 数组，同时计算引擎基准价"""
        # 提取多方案数据：优先用 _all_schemes（来自 _parse_scheme_from_response），兼容 schemes
        all_schemes = scheme_data.get("_all_schemes", []) or scheme_data.get("schemes", [])
        logger.info(
            f"[_save_generated_scheme] 入参: conversation_id={conversation_id}, "
            f"scheme_name={scheme_data.get('scheme_name', 'N/A')}, "
            f"services={len(scheme_data.get('services', []))} 项, "
            f"all_schemes={len(all_schemes)} 个, "
            f"has__all_schemes={'_all_schemes' in scheme_data}"
        )
        # 查找是否已有草稿方案
        existing = db.query(GeneratedScheme).filter(
            GeneratedScheme.conversation_id == conversation_id,
            GeneratedScheme.status == "draft",
        ).first()

        if all_schemes:
            services = all_schemes[0].get("services", [])
            scheme_name = all_schemes[0].get("scheme_name", "未命名方案")
            scene = all_schemes[0].get("scene")
            target_group = all_schemes[0].get("target_group")
        else:
            services = scheme_data.get("services", [])
            scheme_name = scheme_data.get("scheme_name", "未命名方案")
            scene = scheme_data.get("scene")
            target_group = scheme_data.get("target_group")

        def _get_num(svc, *keys):
            for k in keys:
                v = svc.get(k)
                if v is not None and v != "":
                    try:
                        return Decimal(str(v))
                    except Exception:
                        pass
            return Decimal(0)

        # LLM 给出的价格（保持原有逻辑）
        llm_cost = sum(_get_num(s, "cost_price", "cost") for s in services)
        llm_quote = sum(_get_num(s, "quote_price", "price", "quote") for s in services)

        # ─── 定价引擎计算 ─────────────────────────────────────
        engine = PricingEngine(db)
        needs = needs or {}
        volume = 50000
        if "随车" in (scene or ""):
            volume = 50000
        elif "银行" in (scene or ""):
            volume = 30000
        usage_col = "large" if volume >= 50000 else "small"

        engine_params = EnginePricingParams(
            margin_rate=Decimal("0.15"),
            volume=volume,
            usage_rate_column=usage_col,
        )

        engine_cost = Decimal("0")
        engine_quote = Decimal("0")
        pricing_method = scheme_data.get("pricing_method") or "llm_hybrid"

        for svc in services:
            name = svc.get("name", "")
            pricing_input = engine.load_service_pricing_input(name, engine_params)
            if pricing_input:
                try:
                    result = engine.calculate_single_service(pricing_input, engine_params)
                    engine_cost += result.expected_cost
                    engine_quote += result.quoted_price
                except Exception:
                    pass

        # 应用打包折扣
        engine_quote = engine_quote * Decimal("0.90")

        # 验证 LLM 价格偏差
        if llm_quote > 0:
            validation = engine.validate_deviation(engine_quote, llm_quote)
        else:
            validation = {"pass": True, "deviation": 0, "severity": "ok"}

        # 保存完整 scheme_data（包含 schemes 数组）
        save_data = dict(scheme_data)
        # 将 _all_schemes 转为 schemes 保存到数据库
        if all_schemes:
            # 确保 schemes[0] 有 services 数据
            first_scheme_services = all_schemes[0].get("services", []) or all_schemes[0].get("service_list", [])
            if not first_scheme_services and scheme_data.get("services"):
                first_scheme_services = scheme_data["services"]
            save_data["schemes"] = []
            for i, s in enumerate(all_schemes):
                if not isinstance(s, dict):
                    continue
                sch_copy = {k: v for k, v in s.items() if k != "_all_schemes"}
                # 补全第一个方案的 services
                if i == 0 and not sch_copy.get("services") and not sch_copy.get("service_list"):
                    if first_scheme_services:
                        sch_copy["services"] = first_scheme_services
                # 兼容：统一 service_list -> services
                if "service_list" in sch_copy and "services" not in sch_copy:
                    sch_copy["services"] = sch_copy.pop("service_list")
                save_data["schemes"].append(sch_copy)
            save_data["services"] = first_scheme_services
        # 移除内部字段，避免循环引用和序列化问题
        save_data.pop("_all_schemes", None)
        # 清理 schemes 中每个 scheme 可能携带的 _all_schemes
        if "schemes" in save_data and isinstance(save_data["schemes"], list):
            for s in save_data["schemes"]:
                if isinstance(s, dict):
                    s.pop("_all_schemes", None)

        # 安全序列化（处理 Decimal 等类型）
        from services.task_manager import _make_serializable
        save_data_clean = _make_serializable(save_data)

        if existing:
            existing.scheme_name = scheme_name or existing.scheme_name
            existing.scene = scene or existing.scene
            existing.target_group = target_group or existing.target_group
            existing.service_list_json = json.dumps(save_data_clean, ensure_ascii=False)
            existing.total_cost = llm_cost or existing.total_cost
            existing.total_quote = llm_quote or existing.total_quote
            existing.engine_total_cost = engine_cost
            existing.engine_total_quote = engine_quote
            existing.llm_total_cost = llm_cost
            existing.llm_total_quote = llm_quote
            existing.pricing_method = pricing_method
            db.commit()
            logger.info(
                f"[_save_generated_scheme] 更新已有方案 id={existing.id}, "
                f"llm_cost={llm_cost}, llm_quote={llm_quote}, "
                f"engine_cost={engine_cost}, engine_quote={engine_quote}"
            )
            return existing

        gen = GeneratedScheme(
            conversation_id=conversation_id,
            scheme_name=scheme_name,
            scene=scene,
            target_group=target_group,
            service_list_json=json.dumps(save_data_clean, ensure_ascii=False),
            total_cost=llm_cost,
            total_quote=llm_quote,
            engine_total_cost=engine_cost,
            engine_total_quote=engine_quote,
            llm_total_cost=llm_cost,
            llm_total_quote=llm_quote,
            pricing_method=pricing_method,
            status="draft",
        )
        db.add(gen)
        db.commit()
        db.refresh(gen)
        logger.info(
            f"[_save_generated_scheme] 新建方案 id={gen.id}, "
            f"llm_cost={llm_cost}, llm_quote={llm_quote}, "
            f"engine_cost={engine_cost}, engine_quote={engine_quote}"
        )
        return gen

    def _filter_false_claims(self, text: str) -> str:
        """过滤 LLM 回复中的虚假能力声明"""
        import re

        # 需要过滤的虚假能力关键词模式
        false_claim_patterns = [
            r'(?:高清)?PNG版?[《「]?[^》」\n]*[》」]?[（\(][^）\)]*[）\)]',  # PNG版《xxx》(xxx)
            r'PDF[汇报]*摘要[（\(]?[^）\)\n]*[）\)]?',  # PDF汇报摘要
            r'PPT[精简页汇报稿]*[（\(]?[^）\)\n]*[）\)]?',  # PPT精简页
            r'[员工HR]*培训[短视频脚本PPT]*[（\(]?[^）\)\n]*[）\)]?',
            r'[企业]*[微信钉钉]+通知模板[（\(]?[^）\)\n]*[）\)]?',
            r'[视频]*脚本[（\(]?[^）\)\n]*[）\)]?',
            r'发卡[清单SOP]*[（\(]?[^）\)\n]*[）\)]?',
            r'数据看板',
            r'成本占比说明函',
            r'监管[合规]*[依据标注文档]+',
        ]

        # 移除包含虚假能力的整行（以✅、◆、■、→、-等开头的列表项）
        for pattern in false_claim_patterns:
            # 匹配列表项行
            text = re.sub(
                rf'^[\s]*[✅◆■●→\-\*]+\s*.*{pattern}.*$',
                '',
                text,
                flags=re.MULTILINE
            )

        # 移除"马上要用"、"深化落地"、"扩展适配"等分类标题及其下方内容块
        section_patterns = [
            r'[◆◇★☆●■]+\s*【马上要用】.*?(?=\n[◆◇★☆●■]+\s*【|$)',
            r'[◆◇★☆●■]+\s*【深化落地】.*?(?=\n[◆◇★☆●■]+\s*【|$)',
            r'[◆◇★☆●■]+\s*【扩展适配】.*?(?=\n[◆◇★☆●■]+\s*【|$)',
        ]
        for pattern in section_patterns:
            text = re.sub(pattern, '', text, flags=re.DOTALL)

        # 移除"我即刻交付"、"全程在线不需等待"等过度承诺
        overcommit_patterns = [
            r'[我您]?即刻交付',
            r'全程在线[，,]?不需?等待',
            r'[您你]说需求[，,]?[我]即刻交付',
            r'不需切换系统',
            r'全部免费[、，]?实时[、，]?无需切换',
        ]
        for pattern in overcommit_patterns:
            text = re.sub(pattern, '', text)

        # 移除常见“越界能力清单”段落
        out_of_scope_block_patterns = [
            r'\n*\s*若您需要[:：][\s\S]*?(?=\n\s*\n|$)',
            r'\n*\s*需要我进一步协助[\s\S]*?(?=\n\s*\n|$)',
            r'\n*\s*用于汇报场景[\s\S]*?(?=\n\s*\n|$)',
            r'\n*\s*也欢迎[您你]提出新需求[\s\S]*?(?=\n\s*\n|$)',
        ]
        for pattern in out_of_scope_block_patterns:
            text = re.sub(pattern, "\n", text, flags=re.IGNORECASE)

        # 删除单行越界能力描述（即使模型没有按列表格式输出）
        line_patterns = [
            r'.*PPT.*',
            r'.*PDF.*',
            r'.*PNG.*',
            r'.*通知模板.*',
            r'.*视频脚本.*',
            r'.*发卡SOP.*',
            r'.*数据看板.*',
            r'.*合规文档.*',
            r'.*监管依据.*',
            r'.*成本占比说明函.*',
        ]
        for pattern in line_patterns:
            text = re.sub(rf'^\s*{pattern}\s*$', '', text, flags=re.MULTILINE | re.IGNORECASE)

        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    def _maybe_extract_oos_summary_from_user_message(self, user_message: str) -> Optional[str]:
        """从用户输入中检测超范围需求，返回摘要（无则返回 None）"""
        text = (user_message or "").strip()
        if not text:
            return None

        keywords = [
            r'PPT', r'PDF', r'PNG', r'海报', r'图片',
            r'视频脚本', r'通知模板', r'发卡SOP', r'数据看板',
            r'合规文档', r'监管依据', r'说明函',
        ]
        kw_re = "|".join(keywords)
        if not re.search(kw_re, text, flags=re.IGNORECASE):
            return None

        # “不要/不需要 X”不视为新增功能诉求
        if re.search(r'(不要|不需要|无需|别).{0,8}(' + kw_re + r')', text, flags=re.IGNORECASE):
            return None

        summary = re.sub(r'\s+', ' ', text)[:180]
        return summary

    def _save_feature_request(
        self,
        db: Session,
        conversation: Conversation,
        user_message: str,
        summary: str,
        user_id: str = "",
    ) -> None:
        summary = (summary or "").strip()
        if not summary:
            return
        try:
            # 去重：同会话同摘要不重复写入
            existed = (
                db.query(UserFeatureRequest)
                .filter(
                    UserFeatureRequest.conversation_id == conversation.id,
                    UserFeatureRequest.request_summary == summary,
                )
                .first()
            )
            if existed:
                return

            record = UserFeatureRequest(
                user_id=user_id or conversation.user_id,
                conversation_id=conversation.id,
                session_id=conversation.session_id,
                request_content=user_message,
                request_summary=summary,
                source="dingtalk" if (user_id or "").startswith("dingtalk_") else "web",
            )
            db.add(record)
            db.commit()
            logger.info(f"[需求记录] 已记录用户需求: {summary}")
        except Exception as e:
            logger.error(f"[需求记录] 保存失败: {e}")
            db.rollback()

    def _detect_and_record_feature_request(
        self, db, conversation, user_message: str, assistant_content: str, user_id: str = ""
    ):
        """记录超范围需求：优先用户原始诉求，其次 LLM 的 FEATURE_REQUEST 标记"""
        # 1) 用户原始输入兜底识别（避免依赖 LLM 标记）
        summary_from_user = self._maybe_extract_oos_summary_from_user_message(user_message)
        if summary_from_user:
            self._save_feature_request(
                db=db,
                conversation=conversation,
                user_message=user_message,
                summary=summary_from_user,
                user_id=user_id,
            )
            # 用户输入已识别为超范围需求时，不再重复消费 LLM 标记
            return

        # 2) 兼容 LLM 标记链路
        pattern = r'\[FEATURE_REQUEST:\s*(.+?)\]'
        matches = re.findall(pattern, assistant_content)

        if not matches:
            return

        for summary in matches:
            self._save_feature_request(
                db=db,
                conversation=conversation,
                user_message=user_message,
                summary=summary.strip(),
                user_id=user_id,
            )

    def get_conversation_history(self, db: Session, session_id: str, user_id: str = "") -> Optional[Dict[str, Any]]:
        query = db.query(Conversation).filter(Conversation.session_id == session_id)
        if user_id:
            query = query.filter(Conversation.user_id == user_id)
        conv = query.first()
        if not conv:
            return None

        result = {
            "session_id": conv.session_id,
            "messages": self._load_messages(conv),
            "extracted_needs": json.loads(conv.extracted_needs_json or "{}"),
        }

        # 加载该会话关联的最新方案
        gen_scheme = (
            db.query(GeneratedScheme)
            .filter(GeneratedScheme.conversation_id == conv.id)
            .order_by(GeneratedScheme.id.desc())
            .first()
        )
        if gen_scheme:
            raw_data = json.loads(gen_scheme.service_list_json or "{}")
            if isinstance(raw_data, dict):
                services = raw_data.get("services", [])
                schemes = raw_data.get("schemes", [])
            else:
                services = raw_data
                schemes = []

            scheme_out = {
                "id": gen_scheme.id,
                "conversation_id": gen_scheme.conversation_id,
                "scheme_name": gen_scheme.scheme_name,
                "scene": gen_scheme.scene,
                "target_group": gen_scheme.target_group,
                "service_list": services,
                "total_cost": float(gen_scheme.total_cost) if gen_scheme.total_cost else 0,
                "total_quote": float(gen_scheme.total_quote) if gen_scheme.total_quote else 0,
                "status": gen_scheme.status,
                # 定价引擎数据
                "pricing": {
                    "method": gen_scheme.pricing_method,
                    "engine_total_cost": float(gen_scheme.engine_total_cost) if gen_scheme.engine_total_cost else None,
                    "engine_total_quote": float(gen_scheme.engine_total_quote) if gen_scheme.engine_total_quote else None,
                    "llm_total_cost": float(gen_scheme.llm_total_cost) if gen_scheme.llm_total_cost else None,
                    "llm_total_quote": float(gen_scheme.llm_total_quote) if gen_scheme.llm_total_quote else None,
                    "final_total_cost": float(gen_scheme.final_total_cost) if gen_scheme.final_total_cost else None,
                    "final_total_quote": float(gen_scheme.final_total_quote) if gen_scheme.final_total_quote else None,
                },
            }
            if schemes:
                scheme_out["schemes"] = schemes

            # 查找关联的定价逻辑
            if gen_scheme.pricing_logic_id:
                logic = db.query(PricingLogic).filter(
                    PricingLogic.id == gen_scheme.pricing_logic_id
                ).first()
                if logic:
                    scheme_out["pricing"]["logic"] = {
                        "logic_id": logic.id,
                        "method": logic.pricing_method,
                        "description": logic.logic_description,
                        "confidence": float(logic.confidence_score) if logic.confidence_score else None,
                    }

            # 查找关联的 Excel 和手册 ID
            from database import GeneratedExcel, GeneratedManual
            gen_excel = (
                db.query(GeneratedExcel)
                .filter(GeneratedExcel.scheme_id == gen_scheme.id)
                .first()
            )
            if gen_excel:
                scheme_out["excelId"] = gen_excel.id
                scheme_out["excelVersion"] = gen_excel.version or 1
            gen_manual = (
                db.query(GeneratedManual)
                .filter(GeneratedManual.scheme_id == gen_scheme.id)
                .order_by(GeneratedManual.id.desc())
                .first()
            )
            if gen_manual:
                scheme_out["manualId"] = gen_manual.id
                scheme_out["manualVersion"] = gen_manual.version or 1

            result["scheme"] = scheme_out

        return result


# 全局服务实例
_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
