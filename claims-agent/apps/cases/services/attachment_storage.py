"""附件存储抽象 + 本地/对象存储实现"""
from abc import ABC, abstractmethod
from pathlib import Path
from django.conf import settings


class AttachmentStorage(ABC):
    @abstractmethod
    def read(self, path: str) -> bytes: ...
    @abstractmethod
    def save(self, path: str, data: bytes) -> str: ...


class LocalFileAdapter(AttachmentStorage):
    def __init__(self):
        self.root = Path(settings.BASE_DIR) / "data" / "attachments"
        self.root.mkdir(parents=True, exist_ok=True)

    def read(self, path: str) -> bytes:
        return (self.root / path).read_bytes()

    def save(self, path: str, data: bytes) -> str:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return str(target.relative_to(self.root))


class ObjectStorageAdapter(AttachmentStorage):
    """旧系统同步案件：附件通过URL读取"""
    def read(self, url: str) -> bytes:
        import requests
        return requests.get(url, timeout=30).content

    def save(self, path: str, data: bytes) -> str:
        raise NotImplementedError("Object storage write not yet implemented")


def get_storage() -> AttachmentStorage:
    storage_type = getattr(settings, "ATTACHMENT_STORAGE", "local")
    if storage_type == "local":
        return LocalFileAdapter()
    return ObjectStorageAdapter()
