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


class TransformationPreviewRequestSerializer(serializers.Serializer):
    pattern = serializers.CharField(trim_whitespace=False)
    replacement = serializers.CharField(
        allow_blank=True,
        required=False,
        default="",
        trim_whitespace=False,
    )
    columns = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
    )
    flags = serializers.ListField(
        child=serializers.ChoiceField(choices=["IGNORECASE", "MULTILINE"]),
        required=False,
        default=list,
    )

    def validate_columns(self, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))
