from django.urls import path
from .views import LabDetailView, PurchasePromotionalPlanView, PurchasePromotionalAddonView

urlpatterns = [
    path('lab-detail/<slug:slug>/', LabDetailView.as_view(), name='lab-detail'),
    path('lab-detail/<uuid:pk>/', LabDetailView.as_view(), name='lab-detail-pk'),
    path('api/promotional/subscribe/', PurchasePromotionalPlanView.as_view(), name='purchase-promotional-plan'),
    path('api/promotional/addon-purchase/', PurchasePromotionalAddonView.as_view(), name='purchase-promotional-addon'),
]