import pytest
from apps.analysis.models import Website, AnalysisJob, PageType
from apps.workflow.config import TargetExtractionConfig
from apps.workflow.agent import AgentPlanner, CandidatePage
from apps.classifier.classifier import PageRanker
from apps.api.serializers import AnalysisJobCreateSerializer

@pytest.mark.django_db
class TestTargetExtractionConfig:

    def test_default_profile_resolution(self):
        website = Website.objects.create(domain='example.com', root_url='https://example.com')
        job = AnalysisJob.objects.create(website=website, objective='product_intelligence')

        cfg = TargetExtractionConfig.from_job(job)
        assert cfg.objective == 'product_intelligence'
        assert 'PRODUCT' in cfg.target_page_types
        assert 'SERVICE' in cfg.target_page_types
        assert cfg.max_pages >= 5

    def test_job_options_override(self):
        website = Website.objects.create(domain='custom.com', root_url='https://custom.com')
        job = AnalysisJob.objects.create(
            website=website,
            objective='custom',
            options={
                'target_page_types': ['CAREERS', 'CONTACT'],
                'target_paths': ['/jobs', '/contact-us'],
                'max_pages': 3,
                'min_pages': 1
            }
        )

        cfg = TargetExtractionConfig.from_job(job)
        assert cfg.target_page_types == ['CAREERS', 'CONTACT']
        assert cfg.target_paths == ['/jobs', '/contact-us']
        assert cfg.max_pages == 3
        assert cfg.min_pages == 1
        assert cfg.is_eligible('CAREERS', 'https://custom.com/careers/openings')
        assert cfg.is_eligible('OTHER', 'https://custom.com/jobs/dev')  # matches target_paths
        assert not cfg.is_eligible('BLOG', 'https://custom.com/blog/article-1')

    def test_pageranker_with_target_config(self):
        cfg = TargetExtractionConfig(
            objective='custom',
            target_page_types=['CAREERS'],
            target_paths=['/join-our-team'],
            required_page_types=['CAREERS'],
            max_pages=2
        )

        c1 = CandidatePage(url='https://example.com/about', normalized_url='https://example.com/about', page_type='ABOUT', confidence=0.9)
        c2 = CandidatePage(url='https://example.com/careers', normalized_url='https://example.com/careers', page_type='CAREERS', confidence=0.8)
        c3 = CandidatePage(url='https://example.com/join-our-team', normalized_url='https://example.com/join-our-team', page_type='OTHER', confidence=0.5)

        ranked = PageRanker.rank_candidates([c1, c2, c3], objective='custom', target_config=cfg)
        # c2 is both CAREERS and required -> highest score
        # c3 matches target_path -> second
        # c1 is ABOUT (not in target_page_types) -> demoted
        assert ranked[0].page_type == 'CAREERS'
        assert ranked[1].normalized_url == 'https://example.com/join-our-team'

    def test_agent_planner_respects_target_config(self):
        cfg = TargetExtractionConfig(
            objective='custom',
            target_page_types=['CAREERS', 'CONTACT'],
            required_page_types=['CAREERS'],
            max_pages=2,
            min_pages=1
        )

        planner = AgentPlanner(objective='custom', target_config=cfg)

        c_about = CandidatePage(url='https://example.com/about', normalized_url='https://example.com/about', page_type='ABOUT', confidence=0.9)
        c_careers = CandidatePage(url='https://example.com/careers', normalized_url='https://example.com/careers', page_type='CAREERS', confidence=0.85)
        c_contact = CandidatePage(url='https://example.com/contact', normalized_url='https://example.com/contact', page_type='CONTACT', confidence=0.7)

        candidates = [c_about, c_careers, c_contact]

        # First action: should select CAREERS because it is target and required
        action, candidate = planner.select_next_action(
            candidates=candidates,
            analysed_urls=set(),
            collected_categories=set(),
            budget_exhausted=False
        )
        assert action == 'ANALYSE_PAGE'
        assert candidate.page_type == 'CAREERS'

        # After analyzing CAREERS and CONTACT, max_pages (2) is reached -> should FINISH
        action, candidate = planner.select_next_action(
            candidates=candidates,
            analysed_urls={'https://example.com/careers', 'https://example.com/contact'},
            collected_categories={'CAREERS', 'CONTACT'},
            budget_exhausted=False,
            attempted_urls={'https://example.com/careers', 'https://example.com/contact'}
        )
        assert action == 'FINISH'

    def test_api_serializer_target_page_validation(self):
        # Valid payload
        valid_payload = {
            'url': 'https://example.com',
            'objective': 'talent_recruitment',
            'target_page_types': ['CAREERS', 'TEAM'],
            'max_pages': 4
        }
        ser = AnalysisJobCreateSerializer(data=valid_payload)
        assert ser.is_valid(), ser.errors
        assert ser.validated_data['options']['target_page_types'] == ['CAREERS', 'TEAM']
        assert ser.validated_data['options']['max_pages'] == 4

        # Invalid page type
        invalid_payload = {
            'url': 'https://example.com',
            'target_page_types': ['INVALID_PAGE_TYPE_FOO']
        }
        ser_bad = AnalysisJobCreateSerializer(data=invalid_payload)
        assert not ser_bad.is_valid()
        assert 'target_page_types' in ser_bad.errors
