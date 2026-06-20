from rest_framework import serializers

from .models import Dataset


class DatasetSerializer(serializers.ModelSerializer):
    text_columns = serializers.SerializerMethodField()

    class Meta:
        model = Dataset
        fields = [
            "id",
            "original_name",
            "file_format",
            "size_bytes",
            "sha256",
            "sheet_name",
            "row_count",
            "columns",
            "text_columns",
            "preview",
            "status",
            "expires_at",
            "created_at",
        ]

    def get_text_columns(self, instance: Dataset) -> list[str]:
        return [column["name"] for column in instance.columns if column["type"] == "text"]
