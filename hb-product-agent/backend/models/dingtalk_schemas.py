"""钉钉机器人消息数据模型"""
from typing import Optional
from pydantic import BaseModel


class DingtalkMessage(BaseModel):
    """钉钉接收到的消息"""
    sender_staff_id: str          # 发送者企业内用户ID
    conversation_id: str          # 会话ID
    conversation_type: str        # "1"=单聊, "2"=群聊
    text_content: str             # 消息文本（已去除@机器人前缀）
    session_webhook: str          # 回复地址（5分钟内有效）
    sender_nick: Optional[str] = None    # 发送者昵称
    sender_corp_id: Optional[str] = None # 发送者企业ID
    chatbot_user_id: Optional[str] = None # 机器人用户ID


class DingtalkReply(BaseModel):
    """钉钉回复消息"""
    msgtype: str = "markdown"
    markdown: Optional[dict] = None      # {"title": "...", "text": "..."}
    text: Optional[dict] = None          # {"content": "..."}


class DingtalkFileInfo(BaseModel):
    """钉钉文件信息"""
    media_id: str                 # 上传后的文件ID
    file_name: str                # 文件名
    file_type: str                # 文件类型（xlsx/docx）
