from pathlib import Path

from django.db import connection
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Dataset, TransformRun
from .serializers import (
    AiTransformApplyRequestSerializer,
    AiTransformGenerateRequestSerializer,
    AiTransformPlanRequestSerializer,
    DatasetSerializer,
    RegexGenerationRequestSerializer,
    TransformationApplyRequestSerializer,
    TransformationPreviewRequestSerializer,
    TransformRunSerializer,
)
from .services.ai_transformations import (
    apply_ai_transformation,
    generate_ai_transform_plan,
    preview_ai_transformation,
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
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return Response({"status": "unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    response = Response({"status": "ok"})
    response["Cache-Control"] = "no-store"
    return response


class PrivateAPIView(APIView):
    throttle_classes = [ScopedRateThrottle]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        return response


def get_dataset_or_error(dataset_id):
    try:
        dataset = Dataset.objects.get(id=dataset_id)
    except Dataset.DoesNotExist:
        return None, Response(
            {"code": "not_found", "message": "Dataset not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if dataset.expires_at <= timezone.now():
        return None, Response(
            {"code": "dataset_expired", "message": "This dataset has expired. Upload it again."},
            status=status.HTTP_410_GONE,
        )
    return dataset, None


def get_run_or_error(run_id):
    try:
        run = TransformRun.objects.select_related("dataset").get(id=run_id)
    except TransformRun.DoesNotExist:
        return None, Response(
            {"code": "not_found", "message": "Transformation run not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if run.dataset.expires_at <= timezone.now():
        return None, Response(
            {"code": "dataset_expired", "message": "This dataset has expired. Upload it again."},
            status=status.HTTP_410_GONE,
        )
    return run, None


class DatasetListCreateView(PrivateAPIView):
    parser_classes = [MultiPartParser, FormParser]
    throttle_scope = "upload"

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


class DatasetDetailView(PrivateAPIView):
    throttle_scope = "read"

    def get(self, request, dataset_id):
        dataset, error = get_dataset_or_error(dataset_id)
        if error:
            return error
        return Response(DatasetSerializer(dataset).data)


class TransformationPreviewView(PrivateAPIView):
    throttle_scope = "transform"

    def post(self, request, dataset_id):
        dataset, error = get_dataset_or_error(dataset_id)
        if error:
            return error

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


class RegexGenerationView(PrivateAPIView):
    throttle_scope = "generation"

    def post(self, request, dataset_id):
        dataset, error = get_dataset_or_error(dataset_id)
        if error:
            return error

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


class TransformationApplyView(PrivateAPIView):
    throttle_scope = "transform"

    def post(self, request, dataset_id):
        dataset, error = get_dataset_or_error(dataset_id)
        if error:
            return error

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


class TransformRunDetailView(PrivateAPIView):
    throttle_scope = "read"

    def get(self, request, run_id):
        run, error = get_run_or_error(run_id)
        if error:
            return error
        return Response(TransformRunSerializer(run).data)


class TransformDownloadView(PrivateAPIView):
    throttle_scope = "download"

    def get(self, request, run_id):
        run, error = get_run_or_error(run_id)
        if error:
            return error

        extension = run.output_format
        download_name = f"processed-{Path(run.dataset.original_name).stem}.{extension}"
        try:
            result_file = run.result_file.open("rb")
        except OSError:
            return Response(
                {"code": "artifact_unavailable", "message": "The output file is no longer available."},
                status=status.HTTP_410_GONE,
            )
        return FileResponse(result_file, as_attachment=True, filename=download_name)


class AiTransformGenerateView(PrivateAPIView):
    throttle_scope = "generation"

    def post(self, request, dataset_id):
        dataset, error = get_dataset_or_error(dataset_id)
        if error:
            return error

        serializer = AiTransformGenerateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": "invalid_request",
                    "message": "Check the optional transformation request.",
                    "field_errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            plan = generate_ai_transform_plan(dataset, **serializer.validated_data)
        except (ProposalGenerationError, TransformationValidationError) as exc:
            return Response(
                {"code": "generation_failed", "message": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response(plan)


class AiTransformPreviewView(PrivateAPIView):
    throttle_scope = "transform"

    def post(self, request, dataset_id):
        dataset, error = get_dataset_or_error(dataset_id)
        if error:
            return error

        serializer = AiTransformPlanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": "invalid_request",
                    "message": "Check the optional transformation plan.",
                    "field_errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = preview_ai_transformation(dataset, **serializer.validated_data)
        except TransformationValidationError as exc:
            return Response(
                {"code": "unsafe_transform", "message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result)


class AiTransformApplyView(PrivateAPIView):
    throttle_scope = "transform"

    def post(self, request, dataset_id):
        dataset, error = get_dataset_or_error(dataset_id)
        if error:
            return error

        serializer = AiTransformApplyRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": "invalid_request",
                    "message": "Check the optional transformation plan.",
                    "field_errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        values = dict(serializer.validated_data)
        metadata = {
            key: values.pop(key)
            for key in ["instruction", "explanation", "provider", "model"]
        }
        try:
            run = apply_ai_transformation(dataset, metadata=metadata, **values)
        except TransformationValidationError as exc:
            return Response(
                {"code": "unsafe_transform", "message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(TransformRunSerializer(run).data, status=status.HTTP_201_CREATED)
