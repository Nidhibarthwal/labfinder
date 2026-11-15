from django.urls import path
from apps.labs.api import get_top_labs_api

from .views import (
    HomeLabSearchAPI,
    HomeProductSearchAPI,
    HomeView,
    LabSearchView,
    ProductSearchView,
)

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("search/product/", ProductSearchView.as_view(), name="search-product"),
    path("search/products/", ProductSearchView.as_view(), name="search-products-alias"),
    path("search/lab/", LabSearchView.as_view(), name="search-lab"),
    path("search/labs/", LabSearchView.as_view(), name="search-labs-alias"),
    path(
        "api/home/search/products/",
        HomeProductSearchAPI.as_view(),
        name="home-product-search",
    ),
    path(
        "api/home/search/labs/",
        HomeLabSearchAPI.as_view(),
        name="home-lab-search",
    ),
    path("api/home/top-labs/", get_top_labs_api, name="top-labs-api"),
]
