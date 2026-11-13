from django.shortcuts import render
from django.conf import settings
import json
from apps.analysis.models import PageType

def dashboard_view(request):
    """
    Renders the modern Website Intelligence command center dashboard.
    """
    global_conf = getattr(settings, 'WEBSITE_INTEL', {})
    profiles = global_conf.get('ANALYSIS_PROFILES', {})
    default_targets = {
        k: v.get('target_page_types', [])
        for k, v in profiles.items()
    }
    
    ALLOWED_PAGE_TYPES = {'ABOUT', 'CONTACT', 'PRODUCT', 'SERVICE'}
    page_types = [
        {'value': choice[0], 'label': str(choice[1])}
        for choice in PageType.choices
        if choice[0] in ALLOWED_PAGE_TYPES
    ]
    
    context = {
        'page_types': page_types,
        'page_types_json': json.dumps(page_types),
        'analysis_profiles_json': json.dumps(profiles),
        'default_targets_json': json.dumps(default_targets),
    }
    return render(request, 'index.html', context)
