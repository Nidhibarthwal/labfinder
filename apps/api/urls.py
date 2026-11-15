from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WebsiteAnalysisViewSet

router = DefaultRouter()
router.register(r'website-analysis', WebsiteAnalysisViewSet, basename='website-analysis')

urlpatterns = [
    path('', include(router.urls)),
]
