import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import re_path
from apps.audit.consumers import CaseProgressConsumer

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter([
        re_path(r"^ws/cases/(?P<case_id>[^/]+)/$", CaseProgressConsumer.as_asgi()),
        re_path(r"^c/ws/cases/(?P<case_id>[^/]+)/$", CaseProgressConsumer.as_asgi()),
    ]),
})
