from django.utils.deprecation import MiddlewareMixin

class DisableCSRFForAPIs(MiddlewareMixin):
    def process_request(self, request):
        # Exclude all requests starting with /api/ from CSRF checks
        if request.path.startswith('/api/'):
            setattr(request, '_dont_enforce_csrf_checks', True)