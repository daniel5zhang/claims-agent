"""POC Test 3: Django Channels WebSocket 推送进度事件"""
import asyncio
import json
import os
import sys
import time
import django

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.conf import settings
if not settings.configured:
    settings.configure(
        INSTALLED_APPS=["channels", "django.contrib.contenttypes"],
        CHANNEL_LAYERS={
            "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
        },
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        SECRET_KEY="poc-test",
        ROOT_URLCONF=[],
    )
    django.setup()


async def run_test():
    sys.stderr.write("[Test  3] Django Channels WebSocket...\n")

    from channels.routing import URLRouter
    from channels.testing import WebsocketCommunicator
    from channels.generic.websocket import AsyncWebsocketConsumer
    from django.urls import re_path

    class ProgressConsumer(AsyncWebsocketConsumer):
        async def connect(self):
            await self.accept()
            for event, msg in [
                ("phase_start", "Phase 0: 案件解析"),
                ("phase_complete", "Phase 0: 完成"),
                ("rule_result", "特药匹配: pass"),
            ]:
                await self.send(json.dumps(
                    {"event": event, "message": msg, "ts": time.time()},
                    ensure_ascii=False
                ))

    application = URLRouter([re_path(r"^ws/test/$", ProgressConsumer.as_asgi())])

    communicator = WebsocketCommunicator(application, "/ws/test/")
    connected, _ = await communicator.connect()
    if not connected:
        sys.stderr.write("[Test  3] FAIL — WebSocket 连接失败\n")
        return False

    events = []
    for _ in range(3):
        msg = await communicator.receive_from()
        data = json.loads(msg)
        events.append(data["event"])

    await communicator.disconnect()

    expected = ["phase_start", "phase_complete", "rule_result"]
    ok = events == expected
    if ok:
        sys.stderr.write(f"[Test  3] OK — received events: {events}\n")
    else:
        sys.stderr.write(f"[Test  3] FAIL — expected {expected}, got {events}\n")
    return ok


def test():
    return asyncio.run(run_test())


if __name__ == "__main__":
    ok = test()
    print(f"TEST3: websocket {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)
