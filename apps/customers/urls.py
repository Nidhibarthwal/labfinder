from django.urls import path
from .views import (
    CustomerLeadDetailView,
    ProcessCustomerDecisionView,
)

urlpatterns = [
    path(
        "customer/lead/<int:enquiry_id>/",
        CustomerLeadDetailView.as_view(),
        name="customer_lead_detail",
    ),
    path(
        "customer/lead/<int:enquiry_id>/decision/",
        ProcessCustomerDecisionView.as_view(),
        name="process_customer_decision",
    ),
]