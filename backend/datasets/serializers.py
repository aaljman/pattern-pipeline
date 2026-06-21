from rest_framework import serializers

from django.urls import reverse

from .models import Dataset, TransformRun


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


class RegexGenerationRequestSerializer(serializers.Serializer):
    instruction = serializers.CharField(max_length=1_000)
    columns = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
    )

    def validate_columns(self, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class TransformationApplyRequestSerializer(TransformationPreviewRequestSerializer):
    instruction = serializers.CharField(
        allow_blank=True,
        required=False,
        default="",
        max_length=1_000,
    )
    explanation = serializers.CharField(allow_blank=True, required=False, default="")
    provider = serializers.CharField(allow_blank=True, required=False, default="", max_length=64)
    model = serializers.CharField(allow_blank=True, required=False, default="", max_length=128)


class TransformRunSerializer(serializers.ModelSerializer):
    dataset_id = serializers.UUIDField(read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = TransformRun
        fields = [
            "id",
            "dataset_id",
            "instruction",
            "pattern",
            "flags",
            "replacement",
            "columns",
            "explanation",
            "provider",
            "model_name",
            "status",
            "match_count",
            "affected_rows",
            "changed_cells",
            "warnings",
            "output_format",
            "download_url",
            "created_at",
        ]

    def get_download_url(self, instance: TransformRun) -> str:
        return reverse("transform-download", kwargs={"run_id": instance.id})
