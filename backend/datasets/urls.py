from django.urls import path

from .views import (
    DatasetDetailView,
    DatasetListCreateView,
    RegexGenerationView,
    TransformationPreviewView,
    health,
)


urlpatterns = [
    path("health/", health, name="health"),
    path("datasets/", DatasetListCreateView.as_view(), name="dataset-create"),
    path("datasets/<uuid:dataset_id>/", DatasetDetailView.as_view(), name="dataset-detail"),
    path(
        "datasets/<uuid:dataset_id>/transforms/generate/",
        RegexGenerationView.as_view(),
        name="regex-generate",
    ),
    path(
        "datasets/<uuid:dataset_id>/transforms/preview/",
        TransformationPreviewView.as_view(),
        name="transformation-preview",
    ),
]
