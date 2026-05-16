from .base import *  # noqa
DEBUG = False
ALLOWED_HOSTS = ["*"]
CHANNEL_LAYERS = {"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [("redis", 6379)]}}}

