from django.urls import path
from . import health_views

urlpatterns = [
    path('health/', health_views.detailed_health_check, name='health_detail'),
    path('health/live/', health_views.liveness_check, name='health_live'),
    path('health/ready/', health_views.readiness_check, name='health_ready'),
]
