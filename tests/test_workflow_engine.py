import pytest
from unittest.mock import MagicMock, patch
from django.utils import timezone
from apps.analysis.models import Website, AnalysisJob, WorkflowState, Page
from apps.workflow.engine import WorkflowEngine
from apps.workflow.budgets import ExecutionBudget
from apps.crawler.http_client import FetchResult

@pytest.mark.django_db
class TestWorkflowEngine:

    def test_budget_exhaustion(self):
        budget = ExecutionBudget(max_iterations=2, max_analysed_pages=1, max_http_requests=2)
        assert not budget.is_exhausted()

        budget.iterations = 2
        assert budget.is_exhausted()

    @patch('apps.ai.ollama.OllamaProvider.generate')
    @patch('apps.workflow.engine.SafeHttpClient.fetch')
    @patch('apps.workflow.engine.validate_url_security')
    def test_end_to_end_workflow_execution(self, mock_validate, mock_fetch, mock_llm_generate):
        # Mock SSRF validation
        mock_validate.return_value = ("test-company.com", "93.184.216.34")

        # Mock HTML responses
        home_html = """
        <html>
        <head><title>Test Company Home</title></head>
        <body>
            <header>
                <nav>
                    <a href="/who-we-are">Who We Are</a>
                    <a href="/platform">Platform</a>
                </nav>
            </header>
            <main>
                <h1>Autonomous Enterprise Cloud</h1>
                <p>Test Company was founded in 2022. We provide secure cloud orchestration.</p>
            </main>
        </body>
        </html>
        """

        about_html = """
        <html>
        <head><title>Who We Are | Test Company</title></head>
        <body>
            <main>
                <h1>Our Mission and History</h1>
                <p>Test Company was established to solve distributed data challenges. Our CEO is Alice Smith.</p>
            </main>
        </body>
        </html>
        """

        def mock_fetch_side_effect(url, **kwargs):
            if "who-we-are" in url:
                return FetchResult(url=url, status_code=200, html=about_html)
            elif "robots.txt" in url:
                return FetchResult(url=url, status_code=200, html="User-agent: *\nAllow: /\n")
            return FetchResult(url=url, status_code=200, html=home_html)

        mock_fetch.side_effect = mock_fetch_side_effect

        # Mock LLM generation outputs
        def mock_llm_side_effect(prompt, **kwargs):
            if "Who We Are" in prompt:
                return """{
                    "page_summary": "About page detailing CEO and mission",
                    "facts": [
                        {
                            "category": "LEADERSHIP",
                            "field": "ceo",
                            "value": "Alice Smith",
                            "source_quote": "Our CEO is Alice Smith."
                        }
                    ]
                }"""
            elif "Autonomous Enterprise Cloud" in prompt:
                return """{
                    "page_summary": "Homepage describing secure cloud orchestration",
                    "facts": [
                        {
                            "category": "COMPANY",
                            "field": "founded_year",
                            "value": "2022",
                            "source_quote": "Test Company was founded in 2022."
                        }
                    ]
                }"""
            else:
                # Synthesis call
                return """{
                    "company_overview": "Test Company is an enterprise cloud company founded in 2022.",
                    "core_offerings": ["secure cloud orchestration"],
                    "leadership": ["Alice Smith (CEO)"],
                    "key_technologies": ["cloud"],
                    "target_industries": ["enterprise"],
                    "contact_details": "Not mentioned on the analysed website",
                    "conflicts": [],
                    "missing_information": ["headquarters location"],
                    "summary_markdown": "# Test Company Intelligence Summary\\n\\nTest Company was founded in 2022 and is led by CEO Alice Smith."
                }"""

        mock_llm_generate.side_effect = mock_llm_side_effect

        # Setup database records
        website = Website.objects.create(
            domain="test-company.com",
            root_url="https://test-company.com"
        )
        job = AnalysisJob.objects.create(
            website=website,
            objective="company_intelligence",
            status=WorkflowState.PENDING
        )

        # Run WorkflowEngine
        engine = WorkflowEngine(job_id=str(job.id))
        completed_job = engine.execute()

        assert completed_job.status == WorkflowState.COMPLETED
        assert hasattr(completed_job, 'result')
        assert completed_job.result is not None
        assert "Alice Smith" in completed_job.result.summary_markdown

        # Check pages were persisted
        pages = Page.objects.filter(website=website)
        assert pages.count() >= 1
