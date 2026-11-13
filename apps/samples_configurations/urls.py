from django.conf import urls
from django.urls import path, include
from apps.samples_configurations.views import TRConfigurationApiView, \
    TermsConditionApiView, ServiceCategoryApiView, SampleClauseCategoryApiView, SampleClauseSubCategoryApiView, \
    TestMethodViewSet, TestMethodApiView, TermsConditionViewSet, ParameterRangeValueViewSet,CategoryViewSet
from rest_framework import routers

router = routers.DefaultRouter()

router.register(r'test-methods', TestMethodViewSet)
router.register(r'terms-condition', TermsConditionViewSet)
router.register(r'parameter-range-values', ParameterRangeValueViewSet)
router.register(r'module-wise-categories', CategoryViewSet, basename='module-wise-categories')




urlpatterns = [
    path('api/', include(router.urls)),
    path('tr-configurations/', TRConfigurationApiView.as_view(), name='tr-configurations'),
    path('tr-configurations/<uuid:pk>/', TRConfigurationApiView.as_view(), name='tr-configurations-detail'),
    path('terms-conditions/', TermsConditionApiView.as_view(), name='terms-conditions'),
    path('service-categories/', ServiceCategoryApiView.as_view(), name='service-category-list'),
    path('clause-categories/', SampleClauseCategoryApiView.as_view(), name='clause-category-list'),
    path('clause-sub-categories/', SampleClauseSubCategoryApiView.as_view(), name='clause-sub-category-list'),
    path('test-method-list/', TestMethodApiView.as_view(), name='test-method-list'),

]
