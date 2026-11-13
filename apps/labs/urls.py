from django.urls import path
from .views import LabDetailView

urlpatterns = [
    path('lab-detail/<uuid:pk>/', LabDetailView.as_view(), name='lab-detail'),
]