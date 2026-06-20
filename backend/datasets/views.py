from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Dataset
from .serializers import DatasetSerializer
from .services.ingestion import DatasetValidationError, ingest_dataset


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
