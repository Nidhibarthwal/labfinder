from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging

from apps.analysis.models import AnalysisJob, WorkflowState
from apps.workflow.manager import JobManager
from .serializers import (
    AnalysisJobCreateSerializer,
    AnalysisJobDetailSerializer,
    AnalysisJobListSerializer,
)

logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

@method_decorator(csrf_exempt, name='dispatch')
class WebsiteAnalysisViewSet(viewsets.ModelViewSet):
    """
    Production API endpoint for initiating and querying Website Intelligence analyses.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    queryset = AnalysisJob.objects.select_related('website', 'result').prefetch_related('website__pages').all()
    pagination_class = StandardResultsSetPagination
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return AnalysisJobCreateSerializer
        elif self.action == 'list':
            return AnalysisJobListSerializer
        return AnalysisJobDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = AnalysisJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        url = serializer.validated_data['url']
        objective = serializer.validated_data.get('objective', 'company_intelligence')
        options = serializer.validated_data.get('options', {})

        try:
            job = JobManager.create_and_dispatch_job(
                url=url,
                objective=objective,
                options=options,
                run_async=not options.get('sync', False)
            )

            status_code = status.HTTP_200_OK if job.status == WorkflowState.COMPLETED else status.HTTP_202_ACCEPTED
            detail_serializer = AnalysisJobDetailSerializer(job)
            return Response(detail_serializer.data, status=status_code)

        except ValueError as e:
            return Response(
                {'error': {'code': 'INVALID_REQUEST', 'message': str(e), 'status_code': 400}},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f"Unexpected error in WebsiteAnalysisViewSet.create: {e}")
            return Response(
                {'error': {'code': 'PROCESSING_ERROR', 'message': str(e), 'status_code': 500}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
