from django.core.files.base import ContentFile
from django.test import TestCase

from datasets.models import StoredFile
from datasets.storage import DatabaseStorage


class DatabaseStorageTests(TestCase):
    def test_saves_opens_sizes_and_deletes_blob(self):
        storage = DatabaseStorage()

        name = storage.save("datasets/example.csv", ContentFile(b"name\nAda\n"))

        self.assertTrue(storage.exists(name))
        self.assertEqual(storage.size(name), 9)
        self.assertEqual(storage.open(name, "rb").read(), b"name\nAda\n")

        storage.delete(name)

        self.assertFalse(storage.exists(name))
        self.assertFalse(StoredFile.objects.filter(name=name).exists())
