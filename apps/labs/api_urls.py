from apps.labs.api import BranchSearchAPIView, ImportScopeAPIView, LabCrawlerDataIngestAPIView, LaboratoryImportAPIView, ProductSearchAPIView, VistaSyncAPIView, search_services_api
from apps.labs.views import LabNavigationMenuAPIView
from django.urls import path

urlpatterns = [
    path(
        "labs/import/",
        LaboratoryImportAPIView.as_view(),
        name="laboratory-import"
    ),
    path(
        "scopes/import/",
        ImportScopeAPIView.as_view(),
        name="import-scope",
    ),

    # Crawler Data Ingestion Endpoint
    # path('<uuid:branch_id>/ingest-crawler-data/', LabCrawlerDataIngestAPIView.as_view(), name='ingest-crawler-data-by-id'),
    path('ingest-crawler-data/', LabCrawlerDataIngestAPIView.as_view(), name='ingest-crawler-data'),
    
    # Lab Website Navigation Menu Retrieval
    path('labs/<uuid:branch_id>/menu/', LabNavigationMenuAPIView.as_view(), name='lab-website-menu'),

    # Vista Sync Endpoint
    path('vista-sync/', VistaSyncAPIView.as_view(), name='vista-sync'),
    path('branches/search/', BranchSearchAPIView.as_view(), name='branch-search'),
    path('products/search/', ProductSearchAPIView.as_view(), name='product-search'),
    path('search-services/', search_services_api, name='search_services_api'),
]