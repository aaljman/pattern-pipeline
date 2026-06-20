from django.urls import path

from .views import DatasetDetailView, DatasetListCreateView, health


urlpatterns = [
    path("health/", health, name="health"),
    path("datasets/", DatasetListCreateView.as_view(), name="dataset-create"),
    path("datasets/<uuid:dataset_id>/", DatasetDetailView.as_view(), name="dataset-detail"),
]
