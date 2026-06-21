from pathlib import Path

from django.http import FileResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Dataset, TransformRun
from .serializers import (
    DatasetSerializer,
    RegexGenerationRequestSerializer,
    TransformationApplyRequestSerializer,
    TransformationPreviewRequestSerializer,
    TransformRunSerializer,
)
from .services.ingestion import DatasetValidationError, ingest_dataset
from .services.regex_generation import ProposalGenerationError, generate_regex_proposal
from .services.transformations import (
    TransformationSpec,
    TransformationValidationError,
    apply_transformation,
    preview_transformation,
)


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


class DatasetListCreateView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"code": "file_required", "message": "Choose a CSV or XLSX file."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            dataset = ingest_dataset(upload)
        except DatasetValidationError as exc:
            return Response(
                {"code": "invalid_file", "message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(DatasetSerializer(dataset).data, status=status.HTTP_201_CREATED)


class DatasetDetailView(APIView):
    def get(self, request, dataset_id):
        try:
            dataset = Dataset.objects.get(id=dataset_id)
        except Dataset.DoesNotExist:
            return Response(
                {"code": "not_found", "message": "Dataset not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(DatasetSerializer(dataset).data)


class TransformationPreviewView(APIView):
    def post(self, request, dataset_id):
        try:
            dataset = Dataset.objects.get(id=dataset_id)
        except Dataset.DoesNotExist:
            return Response(
                {"code": "not_found", "message": "Dataset not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TransformationPreviewRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": "invalid_request",
                    "message": "Check the transformation fields and try again.",
                    "field_errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        spec = TransformationSpec(**serializer.validated_data)
        try:
            result = preview_transformation(dataset, spec)
        except TransformationValidationError as exc:
            return Response(
                {"code": "unsafe_transform", "message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result)


class RegexGenerationView(APIView):
    def post(self, request, dataset_id):
        try:
            dataset = Dataset.objects.get(id=dataset_id)
        except Dataset.DoesNotExist:
            return Response(
                {"code": "not_found", "message": "Dataset not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = RegexGenerationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": "invalid_request",
                    "message": "Check the pattern description and selected columns.",
                    "field_errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            proposal = generate_regex_proposal(dataset, **serializer.validated_data)
        except (ProposalGenerationError, TransformationValidationError) as exc:
            return Response(
                {"code": "generation_failed", "message": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response(proposal)


class TransformationApplyView(APIView):
    def post(self, request, dataset_id):
        try:
            dataset = Dataset.objects.get(id=dataset_id)
        except Dataset.DoesNotExist:
            return Response(
                {"code": "not_found", "message": "Dataset not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TransformationApplyRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": "invalid_request",
                    "message": "Check the transformation fields and try again.",
                    "field_errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        values = dict(serializer.validated_data)
        metadata = {
            key: values.pop(key)
            for key in ["instruction", "explanation", "provider", "model"]
        }
        spec = TransformationSpec(**values)
        try:
            run = apply_transformation(dataset, spec, metadata)
        except TransformationValidationError as exc:
            return Response(
                {"code": "unsafe_transform", "message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(TransformRunSerializer(run).data, status=status.HTTP_201_CREATED)


class TransformRunDetailView(APIView):
    def get(self, request, run_id):
        try:
            run = TransformRun.objects.get(id=run_id)
        except TransformRun.DoesNotExist:
            return Response(
                {"code": "not_found", "message": "Transformation run not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(TransformRunSerializer(run).data)


class TransformDownloadView(APIView):
    def get(self, request, run_id):
        try:
            run = TransformRun.objects.select_related("dataset").get(id=run_id)
        except TransformRun.DoesNotExist:
            return Response(
                {"code": "not_found", "message": "Transformation run not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        extension = run.output_format
        download_name = f"processed-{Path(run.dataset.original_name).stem}.{extension}"
        return FileResponse(
            run.result_file.open("rb"),
            as_attachment=True,
            filename=download_name,
        )
