from django.urls import path
from .views import (
    DashboardView, GetDepartmentsByDisciplineView, RegisterView, SaveTestingPackageView, VerifyEmailView, LabWebsiteURLView,
    ClaimLabs, LabReviewDetailView, SaveProductScopeView, ParseScopeExcelView, account_api_login, account_api_signup, update_branch_coordinates,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name="register"),
    path('account_api_login', account_api_login, name='account_api_login'),
    path('account_api_signup', account_api_signup, name='account_api_signup'),    
    path('verify-email/', VerifyEmailView.as_view(), name='verify_email'),
    path('lab-website-url/', LabWebsiteURLView.as_view(), name='lab-website-url'),
    path('claim-labs/', ClaimLabs.as_view(), name='claim-labs'),
    path('api/get-departments-by-disciplines/', GetDepartmentsByDisciplineView.as_view(), name='get-departments-by-disciplines'),
    path('lab-review-detail/', LabReviewDetailView.as_view(), name='lab-review-detail'),
    # path('dashboard/', LabDashboardView.as_view(), name="dashboard"),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('save-product-scope/', SaveProductScopeView.as_view(), name='save-product-scope'),
    path('parse-scope-excel/', ParseScopeExcelView.as_view(), name='parse-scope-excel'),
    path('save-testing-package/', SaveTestingPackageView.as_view(), name='save-testing-package'),
    path('api/lab/<uuid:lab_id>/update-coordinates/', update_branch_coordinates, name='update_branch_coordinates'),
]