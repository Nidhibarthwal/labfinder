from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    """
    Production-grade exception handler that guarantees clean, structured error responses
    and suppresses internal stack traces from leaking to clients.
    """
    response = exception_handler(exc, context)

    if response is not None:
        custom_data = {
            'error': {
                'code': getattr(exc, 'default_code', 'API_ERROR').upper(),
                'message': str(exc.detail) if hasattr(exc, 'detail') else str(exc),
                'status_code': response.status_code,
            }
        }
        response.data = custom_data
        return response

    # Unhandled server errors (500)
    logger.exception("Unhandled server exception: %s", exc, extra={'context': str(context)})
    return Response(
        {
            'error': {
                'code': 'INTERNAL_SERVER_ERROR',
                'message': 'An unexpected error occurred while processing the request.',
                'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )
