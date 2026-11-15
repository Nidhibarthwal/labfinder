import pytest
from apps.classifier.classifier import PageClassifier, PageRanker
from apps.workflow.agent import CandidatePage

class TestClassification:

    def setup_method(self):
        self.classifier = PageClassifier()

    @pytest.mark.parametrize("url,anchor,title,expected_type", [
        ("https://example.com/who-we-are", "Who We Are", "Who We Are | Example", "ABOUT"),
        ("https://example.com/our-story", "Our Story", "Company History", "ABOUT"),
        ("https://example.com/corporate-profile", "Profile", "Corporate Profile", "ABOUT"),
        ("https://example.com/leadership", "Leadership", "Executive Leadership", "LEADERSHIP"),
        ("https://example.com/platform/features", "Platform Features", "Software Suite", "PRODUCT"),
        ("https://example.com/services/cloud", "Cloud Services", "Cloud Migration Consulting", "SERVICE"),
        ("https://example.com/contact-us", "Contact", "Get in touch with sales", "CONTACT"),
        ("https://example.com/careers/jobs", "Join Our Team", "Open Engineering Positions", "CAREERS"),
        ("https://example.com/press", "Press Releases", "Latest Press Mentions", "PRESS"),
        ("https://example.com/case-studies", "Case Studies", "Customer Success Stories", "CASE_STUDY"),
    ])
    def test_deterministic_page_classification(self, url, anchor, title, expected_type):
        p_type, conf = self.classifier.classify_deterministic(url=url, anchor_text=anchor, title=title)
        assert p_type == expected_type
        assert conf >= 0.5

    def test_candidate_page_ranking(self):
        c_about = CandidatePage(
            url="https://example.com/about",
            normalized_url="https://example.com/about",
            page_type="ABOUT",
            confidence=0.9,
            location="nav"
        )
        c_blog = CandidatePage(
            url="https://example.com/blog",
            normalized_url="https://example.com/blog",
            page_type="BLOG",
            confidence=0.5,
            location="body"
        )
        c_leadership = CandidatePage(
            url="https://example.com/leadership",
            normalized_url="https://example.com/leadership",
            page_type="LEADERSHIP",
            confidence=0.8,
            location="header"
        )

        ranked = PageRanker.rank_candidates([c_blog, c_about, c_leadership], objective="company_intelligence")
        ranked_types = [c.page_type for c in ranked]

        # For company_intelligence, ABOUT and LEADERSHIP must rank ahead of BLOG
        assert ranked_types[0] in ("ABOUT", "LEADERSHIP")
        assert ranked_types[-1] == "BLOG"
