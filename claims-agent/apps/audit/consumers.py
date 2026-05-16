"""WebSocket Consumer — Agent 执行进度实时推送"""
import json
import time
from channels.generic.websocket import AsyncWebsocketConsumer


class CaseProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.case_id = self.scope["url_route"]["kwargs"]["case_id"]
        self.group = f"case_{self.case_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        # C 端匿名，内部需登录
        user = self.scope.get("user")
        if user and user.is_authenticated:
            await self.accept()
        elif self.scope.get("path", "").startswith("/c/"):
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def progress_event(self, event):
        """转发进度事件到 WebSocket"""
        await self.send(text_data=json.dumps({
            "event": event["type"].replace("progress.", ""),
            **{k: v for k, v in event.items() if k != "type"},
        }, ensure_ascii=False))

    @classmethod
    async def push_event(cls, channel_layer, case_id: str, event_type: str, **kwargs):
        """静态方法：从 Orchestrator 推送事件"""
        await channel_layer.group_send(
            f"case_{case_id}",
            {
                "type": "progress.event",
                "event": event_type,
                "ts": time.time(),
                **kwargs,
            },
        )
