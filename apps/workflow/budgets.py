import time
from typing import Dict, Any
from django.conf import settings

class ExecutionBudget:
    """
    Manages and bounds resource usage during analysis execution.
    """

    def __init__(
        self,
        max_iterations: int = 30,
        max_discovered_pages: int = 50,
        max_analysed_pages: int = 10,
        max_http_requests: int = 35,
        max_browser_requests: int = 5,
        max_llm_calls: int = 25,
        max_execution_time_seconds: int = 300,
    ):
        config = getattr(settings, 'WEBSITE_INTEL', {})
        self.max_iterations = max_iterations or config.get('MAX_AGENT_ITERATIONS', 30)
        self.max_discovered_pages = max_discovered_pages or config.get('MAX_DISCOVERED_PAGES', 50)
        self.max_analysed_pages = max_analysed_pages or config.get('MAX_ANALYSED_PAGES', 10)
        self.max_http_requests = max_http_requests or config.get('MAX_HTTP_REQUESTS', 35)
        self.max_browser_requests = max_browser_requests or config.get('MAX_BROWSER_REQUESTS', 5)
        self.max_llm_calls = max_llm_calls or config.get('MAX_LLM_CALLS', 25)
        self.max_execution_time_seconds = max_execution_time_seconds or config.get('MAX_EXECUTION_TIME_SECONDS', 300)

        # Counters
        self.iterations = 0
        self.discovered_pages = 0
        self.analysed_pages = 0
        self.http_requests = 0
        self.browser_requests = 0
        self.llm_calls = 0
        self.start_time = time.monotonic()

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.start_time

    def is_exhausted(self) -> bool:
        """Returns True if any critical budget limit has been reached."""
        if self.iterations >= self.max_iterations:
            return True
        if self.analysed_pages >= self.max_analysed_pages:
            return True
        if self.http_requests >= self.max_http_requests:
            return True
        if self.llm_calls >= self.max_llm_calls:
            return True
        if self.elapsed_seconds >= self.max_execution_time_seconds:
            return True
        return False

    def can_make_http_request(self) -> bool:
        return self.http_requests < self.max_http_requests and self.elapsed_seconds < self.max_execution_time_seconds

    def can_make_llm_call(self) -> bool:
        return self.llm_calls < self.max_llm_calls and self.elapsed_seconds < self.max_execution_time_seconds

    def can_analyse_page(self) -> bool:
        return self.analysed_pages < self.max_analysed_pages and not self.is_exhausted()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'iterations': self.iterations,
            'discovered_pages': self.discovered_pages,
            'analysed_pages': self.analysed_pages,
            'http_requests': self.http_requests,
            'browser_requests': self.browser_requests,
            'llm_calls': self.llm_calls,
            'elapsed_seconds': round(self.elapsed_seconds, 2),
            'exhausted': self.is_exhausted()
        }
