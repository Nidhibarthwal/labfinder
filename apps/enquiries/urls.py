from django.urls import path

from . import views

urlpatterns = [
    path("enquiry_now", views.EnquiryNowView.as_view(), name="enquiry_now"),
    path("success/<int:enquiry_id>/", views.enquiry_success, name="enquiry_success"),
    path("lead/<int:enquiry_id>/", views.lead_detail, name="lead_detail"),
    path("lead/<int:enquiry_id>/quote/", views.create_quotation, name="create_quotation"),
    path("lead/<int:enquiry_id>/won/", views.mark_lead_won, name="mark_lead_won"),
    path("lead/<int:enquiry_id>/create-order/", views.create_order_from_lead, name="create_order_from_lead"),
    path("order/<int:order_id>/", views.order_detail, name="order_detail"),
    path("submit-lab-review/<uuid:lab_id>/", views.SubmitLabReviewView.as_view(), name="submit_lab_review"),
    path("review/reply/", views.ReplyLabReviewView.as_view(), name="reply_lab_review"),
    path("review/<int:review_id>/update/", views.UpdateCustomerReviewView.as_view(), name="update_customer_review"),
]
