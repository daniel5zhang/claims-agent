"""
钉钉渠道业务编排层
- 用户/会话映射与管理
- 消息处理与回复
- 方案确认后自动触发 Excel/Word 生成并发送到钉钉
"""
import logging
import os
import re
from typing import Dict, List, Optional

import httpx

from config import APP_BASE_URL, DINGTALK_CLIENT_ID, DINGTALK_CLIENT_SECRET
from database import SessionLocal
from models.dingtalk_schemas import DingtalkFileInfo, DingtalkMessage
from services.agent_service import get_agent_service
from services.excel_generator import ExcelGenerator
from services.manual_generator import ManualGenerator

logger = logging.getLogger("dingtalk_service")

# 钉钉 Markdown 单条消息长度上限（官方建议不超过 20000 字符）
_DINGTALK_MSG_MAX_LEN = 20000


class DingtalkService:
    """钉钉业务服务"""

    def __init__(self):
        # user_id -> session_id（内存会话映射，进程重启后会话丢失，需重新创建）
        self._user_sessions: Dict[str, str] = {}
        self.agent = get_agent_service()
        self.excel_generator = ExcelGenerator()
        self.manual_generator = ManualGenerator()

    # ========== 用户/会话映射 ==========

    def _build_user_id(self, msg: DingtalkMessage) -> str:
        """构建系统内部 user_id"""
        if msg.conversation_type == "1":
            return f"dingtalk_{msg.sender_staff_id}"
        return f"dingtalk_group_{msg.conversation_id}_{msg.sender_staff_id}"

    async def _get_session_id(self, user_id: str) -> Optional[str]:
        """获取用户当前活跃会话 ID（内存优先，DB 兜底）"""
        # 1. 内存缓存
        if user_id in self._user_sessions:
            return self._user_sessions[user_id]

        # 2. 从 DB 查询最近活跃会话
        db = SessionLocal()
        try:
            from database import Conversation

            conversation = (
                db.query(Conversation)
                .filter(
                    Conversation.user_id == user_id,
                    Conversation.status == "active",
                )
                .order_by(Conversation.update_time.desc())
                .first()
            )

            if conversation:
                self._user_sessions[user_id] = conversation.session_id
                logger.info(
                    f"[会话恢复] 从 DB 恢复用户 {user_id} 的会话: "
                    f"{conversation.session_id}"
                )
                return conversation.session_id
        except Exception as e:
            logger.error(f"[会话恢复] 查询失败: {e}")
        finally:
            db.close()

        return None

    def _set_session_id(self, user_id: str, session_id: str):
        """设置用户活跃会话 ID"""
        self._user_sessions[user_id] = session_id

    # ========== 消息处理主入口 ==========

    async def handle_message(self, msg: DingtalkMessage):
        """处理钉钉消息的主入口"""
        user_id = self._build_user_id(msg)
        session_id = await self._get_session_id(user_id)

        db = SessionLocal()
        try:
            result = await self.agent.process_message(
                db, session_id, msg.text_content, user_id=user_id
            )

            # 保存会话 ID（新用户会自动创建）
            new_session_id = result.get("session_id")
            if new_session_id:
                self._set_session_id(user_id, new_session_id)

            # 发送文本回复（Markdown 格式）
            message_data = result.get("message", {})
            reply_text = ""
            if isinstance(message_data, dict):
                reply_text = message_data.get("content", "") or ""
            elif isinstance(message_data, str):
                reply_text = message_data

            if reply_text:
                await self._send_markdown_reply(msg.session_webhook, reply_text)

            # 检查方案是否已确认，自动触发文件生成与发送
            scheme = result.get("scheme")
            if scheme and isinstance(scheme, dict) and scheme.get("status") == "confirmed":
                await self._handle_confirmed_scheme(db, msg, scheme)

        except Exception as e:
            logger.error(f"[DingtalkService] 处理消息异常: {e}", exc_info=True)
            await self._send_markdown_reply(
                msg.session_webhook,
                "抱歉，服务暂时出现异常，请稍后重试。如问题持续，请联系技术支持。",
            )
        finally:
            db.close()

    # ========== 消息发送 ==========

    async def _send_markdown_reply(self, session_webhook: str, text: str):
        """发送 Markdown 回复（支持超长消息分段）"""
        if not session_webhook:
            logger.warning("[_send_markdown_reply] session_webhook 为空，无法回复")
            return

        # 转换 Markdown 表格为 HTML table 格式
        text = self._convert_markdown_tables_to_html(text)

        # 过滤虚假能力声明
        text = self._filter_false_claims(text)

        # 将 PC 端操作提示替换为钉钉端描述
        text = self._adapt_reply_for_dingtalk(text)

        chunks = self._split_text(text, _DINGTALK_MSG_MAX_LEN)
        total = len(chunks)

        for idx, chunk in enumerate(chunks):
            title = "方案助手"
            if total > 1:
                title = f"方案助手 ({idx + 1}/{total})"

            payload = {
                "msgtype": "markdown",
                "markdown": {"title": title, "text": chunk},
            }

            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(session_webhook, json=payload)
                    resp_data = resp.json()
                    errcode = resp_data.get("errcode", 0)
                    if errcode != 0:
                        errmsg = resp_data.get("errmsg", "")
                        if errcode in (400002, 400003, 41001):
                            # access_token / sessionWebhook 过期或无效
                            logger.warning(
                                f"[_send_markdown_reply] sessionWebhook 已过期: "
                                f"errcode={errcode}, errmsg={errmsg}"
                            )
                        else:
                            logger.warning(
                                f"[_send_markdown_reply] 钉钉返回错误: "
                                f"errcode={errcode}, errmsg={errmsg}"
                            )
                    else:
                        logger.info(
                            f"[_send_markdown_reply] 消息发送成功 ({idx + 1}/{total})"
                        )
            except httpx.ReadTimeout:
                logger.warning(
                    "[_send_markdown_reply] 发送超时（sessionWebhook 可能已过期）"
                )
            except Exception as e:
                logger.error(f"[_send_markdown_reply] 发送异常: {e}")

    @staticmethod
    def _split_text(text: str, max_len: int) -> List[str]:
        """按行分割文本，尽量不在表格/代码块中间截断"""
        if len(text) <= max_len:
            return [text]

        chunks: List[str] = []
        current = ""
        for line in text.split("\n"):
            if len(current) + len(line) + 1 > max_len:
                if current:
                    chunks.append(current.rstrip("\n"))
                current = line + "\n"
            else:
                current += line + "\n"
        if current:
            chunks.append(current.rstrip("\n"))
        return chunks

    @staticmethod
    def _convert_markdown_tables_to_html(text: str) -> str:
        """将 Markdown 表格转换为 HTML table 格式"""
        if not text or "|" not in text:
            return text

        lines = text.split("\n")
        result = []
        i = 0

        while i < len(lines):
            line = lines[i]
            # 检测表格起始行：以 | 开头（允许前导空格）
            if line.strip().startswith("|"):
                # 收集连续以 | 开头的行
                table_lines = []
                j = i
                while j < len(lines) and lines[j].strip().startswith("|"):
                    table_lines.append(lines[j])
                    j += 1

                # 检查是否包含分隔行（包含 ---）
                has_separator = any("---" in l for l in table_lines)
                # 有效表格至少需要表头 + 分隔 + 1 行数据
                if has_separator and len(table_lines) >= 3:
                    try:
                        converted = DingtalkService._parse_table_to_html(
                            table_lines
                        )
                        result.append(converted)
                    except Exception:
                        # 解析失败，保留原文
                        result.extend(table_lines)
                    i = j
                    continue
                else:
                    # 不是标准表格，保留原行
                    result.extend(table_lines)
                    i = j
                    continue

            result.append(line)
            i += 1

        return "\n".join(result)

    @staticmethod
    def _parse_table_to_html(table_lines: List[str]) -> str:
        """解析 Markdown 表格行并转换为 HTML table"""
        rows = []
        for line in table_lines:
            # 按 | 分割，strip 每个单元格
            cells = [c.strip() for c in line.split("|")]
            # 只去掉首尾的空字符串（由行首和行尾的 | 产生）
            # 保留中间的空单元格，避免列错位
            while cells and cells[0] == "":
                cells.pop(0)
            while cells and cells[-1] == "":
                cells.pop()
            if cells:
                rows.append(cells)

        if len(rows) < 3:
            return "\n".join(table_lines)

        # 第一行是表头
        headers = rows[0]
        # 找分隔行索引（包含 --- 的行）
        sep_index = -1
        for idx in range(1, len(rows)):
            row = rows[idx]
            # 分隔行特征：所有非空单元格都包含 ---
            non_empty = [c for c in row if c]
            if non_empty and all("---" in c for c in non_empty):
                sep_index = idx
                break

        if sep_index == -1:
            return "\n".join(table_lines)

        data_rows = rows[sep_index + 1 :]
        if not data_rows:
            return "\n".join(table_lines)

        # 构建 HTML table
        parts = [
            '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">'
        ]
        # 表头
        header_html = (
            '<tr style="background-color:#f2f2f2">'
            + "".join(f"<th>{h}</th>" for h in headers)
            + "</tr>"
        )
        parts.append(header_html)

        # 数据行
        for row in data_rows:
            if not row or all(not c for c in row):
                continue
            # 补齐或截断到 headers 长度
            row_cells = row + [""] * (len(headers) - len(row))
            row_cells = row_cells[: len(headers)]
            row_html = "<tr>" + "".join(f"<td>{c}</td>" for c in row_cells) + "</tr>"
            parts.append(row_html)

        parts.append("</table>")
        return "\n".join(parts)

    @staticmethod
    def _filter_false_claims(text: str) -> str:
        """过滤 LLM 回复中的虚假能力声明"""
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

        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    def _adapt_reply_for_dingtalk(self, text: str) -> str:
        """将 AI 回复中的 PC 端操作提示替换为钉钉端描述"""
        # 删除“文件已就绪/点击下载”整段（钉钉会自动发送文件，不需要这段说明）
        text = re.sub(
            r"\n*\s*.*文件已就绪.*?(?=\n\s*需要我进一步协助|$)",
            "\n",
            text,
            flags=re.DOTALL,
        )
        # 删除“进一步协助”段落（按产品要求在钉钉确认消息中不展示）
        text = re.sub(
            r"\n*\s*需要我进一步协助[\s\S]*$",
            "",
            text,
            flags=re.DOTALL,
        )

        # 正则替换：覆盖各种"点击下载"相关文案
        # 匹配包含"点击"和"下载"的整句话（到句号或换行结束）
        text = re.sub(
            r'[请您]?[可直接]*点击[页面上的]*【[^】]*下载[^】]*】[^。\n]*[。]?',
            '文件将自动发送到本会话。',
            text
        )
        # 匹配"即可一键获取"相关内容
        text = re.sub(
            r'[，,]?\s*即可一键获取[^。\n]*[。]?',
            '',
            text
        )
        # 匹配"点击「xxx」按钮下载"
        text = re.sub(
            r'[可请]?点击[「【][^」】]*[」】][按钮]*下载[^。\n]*[。]?',
            '系统将自动生成并发送到本会话。',
            text
        )
        # 清理"文件已生成完毕"后面的 PC 端提示段落
        text = re.sub(
            r'请直接点击[^。\n]*按钮[^。\n]*[。]',
            '文件将自动发送到本会话。',
            text
        )
        # 额外清理常见下载提示残留
        text = re.sub(r"^\s*[\[\(（]?下载[^\n]*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*.*如未触发下载.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*请随时告诉我.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    async def _send_file_reply(
        self, session_webhook: str, media_id: str, file_name: str, file_type: str = ""
    ) -> bool:
        """通过 sessionWebhook 发送文件消息，返回是否成功"""
        logger.info(
            f"[_send_file_reply] 尝试通过 sessionWebhook 发送文件: {file_name}"
        )
        if not session_webhook:
            logger.warning("[_send_file_reply] session_webhook 为空，无法发送文件")
            return False

        if not file_type and "." in file_name:
            file_type = file_name.rsplit(".", 1)[-1]

        payload = {
            "msgtype": "file",
            "file": {
                "mediaId": media_id,
                "fileName": file_name,
                "fileType": file_type,
            },
        }
        logger.debug(f"[_send_file_reply] 请求参数: {payload}")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(session_webhook, json=payload)
                logger.debug(
                    f"[_send_file_reply] 响应状态码: {resp.status_code}"
                )
                resp_data = resp.json()
                logger.debug(f"[_send_file_reply] 响应内容: {resp_data}")
                errcode = resp_data.get("errcode", 0)
                if errcode != 0:
                    logger.warning(
                        f"[_send_file_reply] 钉钉返回错误: "
                        f"errcode={errcode}, errmsg={resp_data.get('errmsg')}"
                    )
                    return False
                else:
                    logger.info(
                        f"[_send_file_reply] 文件发送成功: {file_name}"
                    )
                    return True
        except Exception as e:
            logger.error(f"[_send_file_reply] 发送异常: {e}")
            return False

    @staticmethod
    def _extract_access_token_from_webhook(
        session_webhook: str,
    ) -> Optional[str]:
        """从 session_webhook URL 中提取 access_token 参数"""
        if not session_webhook:
            return None
        try:
            from urllib.parse import urlparse, parse_qs

            parsed = urlparse(session_webhook)
            query = parse_qs(parsed.query)
            tokens = query.get("access_token", [])
            return tokens[0] if tokens else None
        except Exception:
            return None

    async def _send_file_via_server_api(
        self, session_webhook: str, media_id: str, file_name: str, file_type: str = ""
    ) -> bool:
        """通过钉钉服务端 API 发送文件消息（sessionWebhook 失败时的兜底）"""
        logger.info(
            f"[_send_file_via_server_api] 尝试通过服务端 API 发送文件: {file_name}"
        )

        if not file_type and "." in file_name:
            file_type = file_name.rsplit(".", 1)[-1]

        # 直接调用 _get_access_token 获取 token
        token = await self._get_access_token()
        if not token:
            logger.warning(
                "[_send_file_via_server_api] 无法获取 access_token"
            )
            return False

        # 用新获取的 access_token 替换 session_webhook 中的旧 token，重新构造 webhook URL
        url = re.sub(
            r'access_token=[^&]*',
            f'access_token={token}',
            session_webhook,
        )
        # 如果 URL 中原本没有 access_token 参数，则追加
        if 'access_token=' not in url:
            sep = '&' if '?' in url else '?'
            url = f"{url}{sep}access_token={token}"

        payload = {
            "msgtype": "file",
            "file": {
                "mediaId": media_id,
                "fileName": file_name,
                "fileType": file_type,
            },
        }
        logger.debug(
            f"[_send_file_via_server_api] 请求 URL: {url}, payload: {payload}"
        )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=payload)
                logger.debug(
                    f"[_send_file_via_server_api] 响应状态码: {resp.status_code}"
                )
                resp_data = resp.json()
                logger.debug(
                    f"[_send_file_via_server_api] 响应内容: {resp_data}"
                )
                errcode = resp_data.get("errcode", 0)
                if errcode != 0:
                    logger.warning(
                        f"[_send_file_via_server_api] 钉钉返回错误: "
                        f"errcode={errcode}, errmsg={resp_data.get('errmsg')}"
                    )
                    return False
                logger.info(
                    f"[_send_file_via_server_api] 文件发送成功: {file_name}"
                )
                return True
        except Exception as e:
            logger.error(f"[_send_file_via_server_api] 发送异常: {e}")
            return False

    async def _send_download_action_card(
        self,
        session_webhook: str,
        excel_id: Optional[int],
        manual_id: Optional[int],
    ):
        """发送 ActionCard 消息提供文件下载链接（file 类型发送失败时的降级方案）"""
        if not session_webhook:
            return

        btns = []
        if excel_id:
            btns.append(
                {
                    "title": "下载Excel报价单",
                    "actionURL": f"{APP_BASE_URL}/api/excel/{excel_id}/download",
                }
            )
        if manual_id:
            btns.append(
                {
                    "title": "下载Word服务手册",
                    "actionURL": f"{APP_BASE_URL}/api/manual/{manual_id}/download",
                }
            )

        if not btns:
            return

        payload = {
            "msgtype": "actionCard",
            "actionCard": {
                "title": "文件下载",
                "text": "## 文件已生成\n\nExcel报价单和Word服务手册已准备好，请点击下载。",
                "btnOrientation": "0",
                "btns": btns,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(session_webhook, json=payload)
                resp_data = resp.json()
                errcode = resp_data.get("errcode", 0)
                if errcode != 0:
                    logger.warning(
                        f"[_send_download_action_card] 钉钉返回错误: "
                        f"errcode={errcode}, errmsg={resp_data.get('errmsg')}"
                    )
                else:
                    logger.info("[_send_download_action_card] 下载链接发送成功")
        except Exception as e:
            logger.error(f"[_send_download_action_card] 发送异常: {e}")

    # ========== Access Token ==========

    async def _get_access_token(self) -> Optional[str]:
        """获取钉钉 access_token"""
        if not DINGTALK_CLIENT_ID or not DINGTALK_CLIENT_SECRET:
            logger.warning("[_get_access_token] 钉钉 Client ID / Secret 未配置")
            return None

        url = (
            "https://oapi.dingtalk.com/gettoken"
            f"?appkey={DINGTALK_CLIENT_ID}"
            f"&appsecret={DINGTALK_CLIENT_SECRET}"
        )
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                data = resp.json()
                if data.get("errcode") == 0:
                    token = data.get("access_token")
                    logger.info("[_get_access_token] 获取 access_token 成功")
                    return token
                logger.warning(
                    f"[_get_access_token] 获取失败: {data}"
                )
        except Exception as e:
            logger.error(f"[_get_access_token] 异常: {e}")
        return None

    # ========== 文件上传 ==========

    async def _upload_file_to_dingtalk(
        self, file_path: str, file_name: str
    ) -> Optional[DingtalkFileInfo]:
        """上传文件到钉钉获取 mediaId"""
        logger.info(
            f"[_upload_file] 开始上传文件: {file_name}, 路径: {file_path}"
        )
        if not os.path.exists(file_path):
            logger.error(f"[_upload_file] 文件不存在: {file_path}")
            return None

        access_token = await self._get_access_token()
        if not access_token:
            logger.warning("[_upload_file] 获取 access_token 失败，无法上传")
            return None

        url = (
            "https://oapi.dingtalk.com/media/upload"
            f"?access_token={access_token}&type=file"
        )
        logger.debug(f"[_upload_file] 上传 URL: {url}")

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                with open(file_path, "rb") as f:
                    files = {
                        "media": (file_name, f, "application/octet-stream")
                    }
                    resp = await client.post(url, files=files)

                logger.debug(
                    f"[_upload_file] 响应状态码: {resp.status_code}"
                )
                data = resp.json()
                logger.debug(f"[_upload_file] 响应内容: {data}")
                if data.get("errcode") == 0:
                    media_id = data.get("media_id", "")
                    logger.info(
                        f"[_upload_file] 上传成功: {file_name}, "
                        f"media_id={media_id[:20]}..."
                    )
                    return DingtalkFileInfo(
                        media_id=media_id,
                        file_name=file_name,
                        file_type=file_name.split(".")[-1]
                        if "." in file_name
                        else "",
                    )
                logger.warning(f"[_upload_file] 上传失败: {data}")
        except Exception as e:
            logger.error(f"[_upload_file] 上传异常: {e}")
        return None

    # ========== 方案确认后的文件生成 ==========

    async def _handle_confirmed_scheme(
        self, db, msg: DingtalkMessage, scheme: dict
    ):
        """方案确认后，生成并发送 Excel 和 Word 文件"""
        scheme_id = scheme.get("id")
        if not scheme_id:
            logger.warning(
                "[_handle_confirmed_scheme] scheme 无 id，跳过文件生成"
            )
            return

        logger.info(
            f"[_handle_confirmed_scheme] 方案 {scheme_id} 已确认，开始生成文件"
        )

        excel_path: Optional[str] = None
        manual_path: Optional[str] = None
        excel_id: Optional[int] = None
        manual_id: Optional[int] = None
        excel_send_success = False
        manual_send_success = False
        files_sent: List[str] = []

        # 1) 生成 Excel
        try:
            excel = self.excel_generator.generate_excel(db, scheme_id)
            db.commit()
            excel_path = excel.excel_path
            excel_id = excel.id
            logger.info(
                f"[_handle_confirmed_scheme] Excel 生成成功: {excel_path}, "
                f"id={excel_id}"
            )
        except Exception as e:
            logger.error(f"[_handle_confirmed_scheme] Excel 生成失败: {e}")
            await self._send_markdown_reply(
                msg.session_webhook,
                "方案已确认，但 Excel 报价单生成失败，请联系技术支持手动获取。",
            )

        # 2) 生成 Word 手册
        try:
            manual, _missing = self.manual_generator.generate_manual(
                db, scheme_id
            )
            db.commit()
            manual_path = manual.docx_path
            manual_id = manual.id
            logger.info(
                f"[_handle_confirmed_scheme] 手册生成成功: {manual_path}, "
                f"id={manual_id}"
            )
        except Exception as e:
            logger.error(f"[_handle_confirmed_scheme] 手册生成失败: {e}")
            await self._send_markdown_reply(
                msg.session_webhook,
                "方案已确认，但服务手册生成失败，请联系技术支持手动获取。",
            )

        # 3) 上传并发送 Excel
        if excel_path and os.path.exists(excel_path):
            file_name = os.path.basename(excel_path)
            file_info = await self._upload_file_to_dingtalk(
                excel_path, file_name
            )
            if file_info:
                excel_send_success = await self._send_file_reply(
                    msg.session_webhook,
                    file_info.media_id,
                    file_info.file_name,
                    file_info.file_type,
                )
                if not excel_send_success:
                    # sessionWebhook 失败，尝试服务端 API
                    logger.warning(
                        "[_handle_confirmed_scheme] Excel sessionWebhook "
                        "发送失败，尝试服务端 API"
                    )
                    excel_send_success = await self._send_file_via_server_api(
                        msg.session_webhook,
                        file_info.media_id,
                        file_info.file_name,
                        file_info.file_type,
                    )

                if excel_send_success:
                    files_sent.append("Excel报价单")
                else:
                    logger.warning(
                        "[_handle_confirmed_scheme] Excel 所有发送方式均失败"
                    )
            else:
                logger.warning(
                    "[_handle_confirmed_scheme] Excel 上传钉钉失败"
                )

        # 4) 上传并发送 Word
        if manual_path and os.path.exists(manual_path):
            file_name = os.path.basename(manual_path)
            file_info = await self._upload_file_to_dingtalk(
                manual_path, file_name
            )
            if file_info:
                manual_send_success = await self._send_file_reply(
                    msg.session_webhook,
                    file_info.media_id,
                    file_info.file_name,
                    file_info.file_type,
                )
                if not manual_send_success:
                    # sessionWebhook 失败，尝试服务端 API
                    logger.warning(
                        "[_handle_confirmed_scheme] Word sessionWebhook "
                        "发送失败，尝试服务端 API"
                    )
                    manual_send_success = await self._send_file_via_server_api(
                        msg.session_webhook,
                        file_info.media_id,
                        file_info.file_name,
                        file_info.file_type,
                    )

                if manual_send_success:
                    files_sent.append("服务手册")
                else:
                    logger.warning(
                        "[_handle_confirmed_scheme] Word 所有发送方式均失败"
                    )
            else:
                logger.warning(
                    "[_handle_confirmed_scheme] Word 上传钉钉失败"
                )

        # 5) 汇总通知
        if files_sent:
            await self._send_markdown_reply(
                msg.session_webhook,
                f"✅ 方案已确认，文件已发送：{', '.join(files_sent)}",
            )
        elif excel_id or manual_id:
            # 文件已生成但所有发送方式均失败
            await self._send_markdown_reply(
                msg.session_webhook,
                "方案已确认，文件已生成，但发送失败。"
                "请登录 PC 端下载，或联系技术支持。",
            )
        else:
            # 两个都生成失败
            await self._send_markdown_reply(
                msg.session_webhook,
                "方案已确认，但文件生成均失败，请联系技术支持手动获取。",
            )
