from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from django.conf import settings
from apps.analysis.models import PageType

@dataclass
class TargetExtractionConfig:
    """
    Standard configuration defining which pages to target, prioritize,
    and require during the website intelligence workflow.
    """
    objective: str = 'company_intelligence'
    target_page_types: List[str] = field(default_factory=list)
    target_paths: List[str] = field(default_factory=list)
    required_page_types: List[str] = field(default_factory=list)
    exclude_page_types: List[str] = field(default_factory=list)
    max_pages: int = 5
    min_pages: int = 2

    @classmethod
    def from_job(cls, job) -> 'TargetExtractionConfig':
        """
        Builds TargetExtractionConfig by merging:
        1. Global backend settings (settings.WEBSITE_INTEL['ANALYSIS_PROFILES'])
        2. Job objective profile
        3. Request-level overrides (job.options)
        """
        global_conf = getattr(settings, 'WEBSITE_INTEL', {})
        profiles = global_conf.get('ANALYSIS_PROFILES', {})

        objective = getattr(job, 'objective', 'company_intelligence') or 'company_intelligence'
        profile = profiles.get(objective, profiles.get('company_intelligence', {}))

        # Defaults from profile
        default_target_types = list(profile.get('target_page_types', global_conf.get('DEFAULT_TARGET_PAGE_TYPES', [])))
        default_required_types = list(profile.get('required_page_types', []))
        default_max_pages = profile.get('max_pages', global_conf.get('MAX_ANALYSED_PAGES', 5))
        default_min_pages = profile.get('min_pages', 2)

        # Job options overrides
        options = getattr(job, 'options', {}) or {}

        # 1. Target page types (allow list of strings e.g. ['ABOUT', 'PRODUCT'])
        raw_target_types = options.get('target_page_types')
        if raw_target_types and isinstance(raw_target_types, list):
            target_page_types = [str(t).strip().upper() for t in raw_target_types if str(t).strip()]
        else:
            target_page_types = default_target_types

        # 2. Target paths (e.g. ['/about-us', '/products'])
        raw_paths = options.get('target_paths', [])
        if isinstance(raw_paths, list):
            target_paths = [str(p).strip().lower() for p in raw_paths if str(p).strip()]
        else:
            target_paths = []

        # 3. Required page types
        raw_required = options.get('required_page_types')
        if raw_required and isinstance(raw_required, list):
            required_page_types = [str(t).strip().upper() for t in raw_required if str(t).strip()]
        else:
            required_page_types = default_required_types

        # 4. Exclude page types
        raw_exclude = options.get('exclude_page_types', [])
        if isinstance(raw_exclude, list):
            exclude_page_types = [str(t).strip().upper() for t in raw_exclude if str(t).strip()]
        else:
            exclude_page_types = []

        # 5. Page counts
        max_pages = options.get('max_pages', default_max_pages)
        min_pages = options.get('min_pages', default_min_pages)

        # Hard ceiling bounds from global config
        global_max = global_conf.get('MAX_ANALYSED_PAGES', 10)
        try:
            max_pages = min(max(1, int(max_pages)), global_max)
            min_pages = min(max(1, int(min_pages)), max_pages)
        except (ValueError, TypeError):
            max_pages = default_max_pages
            min_pages = default_min_pages

        return cls(
            objective=objective,
            target_page_types=target_page_types,
            target_paths=target_paths,
            required_page_types=required_page_types,
            exclude_page_types=exclude_page_types,
            max_pages=max_pages,
            min_pages=min_pages,
        )

    def is_eligible(self, page_type: str, url: str) -> bool:
        """
        Checks if candidate page qualifies for extraction based on target configuration.
        """
        if page_type in self.exclude_page_types:
            return False

        # If explicit target_paths are specified, check if url matches
        url_lower = url.lower()
        if self.target_paths:
            path_matches = any(p in url_lower for p in self.target_paths)
            if path_matches:
                return True

        # If target_page_types is specified, candidate must match one of them
        if self.target_page_types:
            return page_type in self.target_page_types

        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'objective': self.objective,
            'target_page_types': self.target_page_types,
            'target_paths': self.target_paths,
            'required_page_types': self.required_page_types,
            'exclude_page_types': self.exclude_page_types,
            'max_pages': self.max_pages,
            'min_pages': self.min_pages,
        }
