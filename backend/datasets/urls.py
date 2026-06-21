from django.urls import path

from .views import (
    AiTransformApplyView,
    AiTransformGenerateView,
    AiTransformPreviewView,
    DatasetDetailView,
    DatasetListCreateView,
    RegexGenerationView,
    TransformationApplyView,
    TransformationPreviewView,
    TransformDownloadView,
    TransformRunDetailView,
    health,
)


urlpatterns = [
    path("health/", health, name="health"),
    path("datasets/", DatasetListCreateView.as_view(), name="dataset-create"),
    path("datasets/<uuid:dataset_id>/", DatasetDetailView.as_view(), name="dataset-detail"),
    path(
        "datasets/<uuid:dataset_id>/ai-transforms/generate/",
        AiTransformGenerateView.as_view(),
        name="ai-transform-generate",
    ),
    path(
        "datasets/<uuid:dataset_id>/ai-transforms/preview/",
        AiTransformPreviewView.as_view(),
        name="ai-transform-preview",
    ),
    path(
        "datasets/<uuid:dataset_id>/ai-transforms/apply/",
        AiTransformApplyView.as_view(),
        name="ai-transform-apply",
    ),
    path(
        "datasets/<uuid:dataset_id>/transforms/apply/",
        TransformationApplyView.as_view(),
        name="transformation-apply",
    ),
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
    path("transforms/<uuid:run_id>/", TransformRunDetailView.as_view(), name="transform-detail"),
    path(
        "transforms/<uuid:run_id>/download/",
        TransformDownloadView.as_view(),
        name="transform-download",
    ),
]
