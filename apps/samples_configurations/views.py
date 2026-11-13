from apps.labs.models import BranchItem
from django.db.models import Q, F, Value, CharField
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.filters import SearchFilter
from rest_framework import permissions, status, authentication
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.generics import RetrieveAPIView, DestroyAPIView
from apps.labs.models import BranchItem, TestingScopeFacility,FacilityRangeValue
from apps.samples.models import TestRequest
from django.shortcuts import get_object_or_404
from django.db import DataError, IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError
from apps.samples_configurations.models import TRConfiguration, TermsCondition, \
    ServiceCategory, SampleClauseSubCategory, SampleClauseCategory, Category,TestMethod, \
    ParameterRangeValue
from apps.samples_configurations.permissions import MasterObjectPermission
from apps.samples_configurations.serializers import CategorySerializer, TRConfigurationSerializer, TestMethodSerializer, \
    TermsConditionSerializer, ParameterRangeValueSerializer
from apps.samples_configurations.filters import StandardsFilter
from apps.samples.utility import get_type_of_logged_in_user
from apps.utility.models import Department
from apps.utility.utility import get_lab_of_logged_in_manpower, CustomPagination, natural_sort_key
from uuid import UUID
from rest_framework import generics



# class TRConfigurationApiView(APIView):
#     """
#     This api returns if global payment status applicable for TRConfiguration.
#     """
#     authentication_classes = [authentication.TokenAuthentication, ]
#     permission_classes = [permissions.IsAuthenticated, ]

#     def get(self, request):
#         queryset = TRConfiguration.objects.last()
#         config = {}
#         if queryset:
#             config = {"is_payment_applicable": queryset.is_payment_applicable,
#                     #   "is_verification_required": queryset.is_verification_required
#                     "is_report_verification_required":queryset.is_report_verification_required,
#                     "is_report_approval_required":queryset.is_report_approval_required
                      
#                       }
#         return Response({'results': config, "status": status.HTTP_200_OK})


class TRConfigurationApiView(APIView):

    def get_object(self):
        # pk = self.kwargs.get('pk')
        # if pk:
        #     return TRConfiguration.objects.get(pk=pk)

        obj, _ = TRConfiguration.objects.get_or_create()
        return obj

    def get(self, request):
        config = self.get_object()
        # serializer = TRConfigurationSerializer(
        #     config,
        #     context={'request': request}
        # )
        serializer = TRConfigurationSerializer(config)

        return Response(
            {
                "results": serializer.data,
                "status": status.HTTP_200_OK
            },
            status=status.HTTP_200_OK
        )

    def post(self, request):
        config = self.get_object()

        serializer = TRConfigurationSerializer(
            config,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "results": serializer.data,
                "status": status.HTTP_200_OK
            },
            status=status.HTTP_200_OK
        )

    def put(self, request):
        config = self.get_object()

        serializer = TRConfigurationSerializer(
            config,
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "results": serializer.data,
                "status": status.HTTP_200_OK
            },
            status=status.HTTP_200_OK
        )

    def patch(self, request):
        config = self.get_object()

        serializer = TRConfigurationSerializer(
            config,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "results": serializer.data,
                "status": status.HTTP_200_OK
            },
            status=status.HTTP_200_OK
        )

class TermsConditionApiView(APIView):
    """
    This api returns TermsCondition applicable for Lab Sample Page.
    """
    authentication_classes = [authentication.TokenAuthentication, ]
    permission_classes = [permissions.IsAuthenticated, ]

    def get(self, request):
        # getting only active terms_n_conditions in page
        name = self.request.query_params.get("name", None)
        if name:
            queryset = TermsCondition.objects.filter(
                active=True, name__icontains=name) .order_by('order')
        else:
            queryset = TermsCondition.objects.all().filter(active=True) .order_by('order')
        terms_n_conditions = []
        if queryset:
            for query in queryset:
                terms_n_conditions.append(query.terms_n_condition)
        return Response({'results': terms_n_conditions, "status": status.HTTP_200_OK})


class TermsConditionViewSet(ModelViewSet):
    authentication_classes = [authentication.TokenAuthentication, ]
    permission_classes = [MasterObjectPermission, ]
    serializer_class = TermsConditionSerializer
    queryset = TermsCondition.objects.all().order_by('-created_at')

    def get_queryset(self):
        name = self.request.query_params.get("name", None)
        if name:
            queryset = TermsCondition.objects.filter(
                active=True, name__icontains=name).order_by('order')
        else:
            queryset = TermsCondition.objects.all().filter(active=True).order_by('order')
        return queryset





class ServiceCategoryApiView(APIView):
    """
    This api is used to provide the list of all service category
    """
    authentication_classes = [authentication.TokenAuthentication, ]
    permission_classes = [permissions.IsAuthenticated, ]

    def get(self, request):
        queryset = ServiceCategory.objects.filter(
            active=True).values("id", "name", "order")
        service_list = []
        for query in queryset:
            service_list.append({'id': query['id'], 'text': query['name'], 'order': query['order']})
        return Response({'results': service_list, "status": status.HTTP_200_OK})


class SampleClauseCategoryApiView(APIView):
    """
    This api is used to provide the list of all service category
    """
    authentication_classes = [authentication.TokenAuthentication, ]
    permission_classes = [permissions.IsAuthenticated, ]

    def get(self, request):
        queryset = SampleClauseCategory.objects.filter(
            active=True).values("id", "name")
        cat_list = []
        for query in queryset:
            cat_list.append({'id': query['id'], 'text': query['name']})
        return Response({'results': cat_list, "status": status.HTTP_200_OK})


class SampleClauseSubCategoryApiView(APIView):
    """
    This api is used to provide the list of all SampleClauseSubCategory
    """
    authentication_classes = [authentication.TokenAuthentication, ]
    permission_classes = [permissions.IsAuthenticated, ]

    def get(self, request):
        queryset = SampleClauseSubCategory.objects.filter(
            active=True).values("id", "name")
        sub_cat_list = []
        for query in queryset:
            sub_cat_list.append({'id': query['id'], 'text': query['name']})
        return Response({'results': sub_cat_list, "status": status.HTTP_200_OK})



class TestMethodViewSet(ModelViewSet):
    authentication_classes = [authentication.TokenAuthentication, ]
    permission_classes = [MasterObjectPermission, ]
    serializer_class = TestMethodSerializer
    queryset = TestMethod.objects.all().order_by('-created_at')


class TestMethodApiView(APIView):
    """
    This api is used to provide the list of all Test Method
    """
    authentication_classes = [authentication.TokenAuthentication, ]
    permission_classes = [permissions.IsAuthenticated, ]

    def get(self, request):
        filters = {'active': True}
        year = request.query_params.get('year')
        if year:
            filters['year'] = year
        queryset = TestMethod.objects.filter(**filters).values("id", "name", "ref_no", "year")
        test_list = []
        for query in queryset:
            method_dict = {'id': query['id'], 'ref_no': query['ref_no'], 'year': query['year']}
            if query['year']:
                method_dict['text'] = f"{query['name']} ({query['year']})"
            else:
                method_dict['text'] = f"{query['name']}"
            test_list.append(method_dict)
        return Response({'results': test_list, "status": status.HTTP_200_OK})


class ParameterRangeValueViewSet(ModelViewSet):
    authentication_classes = [authentication.TokenAuthentication, ]
    permission_classes = [permissions.IsAuthenticated, ]
    serializer_class = ParameterRangeValueSerializer
    queryset = ParameterRangeValue.objects.all().order_by('-created_at')







class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by("order")
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    # Optional: soft delete instead of hard delete
    def perform_destroy(self, instance):
        instance.active = False
        instance.save()
    

