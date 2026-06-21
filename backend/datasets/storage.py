from django.core.files.base import ContentFile
from django.core.files.storage import Storage


class DatabaseStorage(Storage):
    """Small, durable blob storage for the short-lived public demo artifacts."""

    def _open(self, name, mode="rb"):
        from datasets.models import StoredFile

        try:
            stored = StoredFile.objects.only("name", "content").get(name=name)
        except StoredFile.DoesNotExist as exc:
            raise FileNotFoundError(name) from exc
        return ContentFile(bytes(stored.content), name=stored.name)

    def _save(self, name, content):
        from datasets.models import StoredFile

        payload = b"".join(content.chunks())
        StoredFile.objects.create(name=name, content=payload, size_bytes=len(payload))
        return name

    def delete(self, name):
        from datasets.models import StoredFile

        if name:
            StoredFile.objects.filter(name=name).delete()

    def exists(self, name):
        from datasets.models import StoredFile

        return StoredFile.objects.filter(name=name).exists()

    def size(self, name):
        from datasets.models import StoredFile

        return StoredFile.objects.values_list("size_bytes", flat=True).get(name=name)
