from django.urls import path

from . import views

urlpatterns = [
    path("api/ingest/", views.ingest_item, name="ingest_item"),
    path("api/items/", views.list_items, name="list_items"),
    path("api/query/", views.query_items, name="query_items"),
]
