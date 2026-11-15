import pytest
from apps.evidence.validator import ClaimValidator
from apps.evidence.conflicts import ConflictDetector

class TestEvidenceGrounding:

    def setup_method(self):
        self.validator = ClaimValidator()
        self.detector = ConflictDetector()

    def test_verifies_grounded_quote_and_calculates_offsets(self):
        clean_text = "Founded in 2018, CyberFlow provides autonomous threat response systems to financial institutions."
        valid_quote = "provides autonomous threat response systems"

        is_verified, start, end = self.validator.verify_quote(clean_text, valid_quote)
        assert is_verified is True
        assert start >= 0
        assert end > start
        assert clean_text[start:end] == valid_quote

    def test_drops_hallucinated_claim(self):
        clean_text = "Acme Corp builds widgets for consumers."
        hallucinated_quote = "Acme Corp is the world leader in quantum computing"

        is_verified, start, end = self.validator.verify_quote(clean_text, hallucinated_quote)
        assert is_verified is False
        assert start == -1
        assert end == -1

        raw_facts = [
            {
                "category": "COMPANY",
                "field": "leader",
                "value": "Quantum computing",
                "source_quote": hallucinated_quote
            },
            {
                "category": "PRODUCT",
                "field": "product_type",
                "value": "widgets",
                "source_quote": "builds widgets for consumers"
            }
        ]

        filtered = self.validator.validate_and_filter_facts(clean_text, raw_facts)
        assert len(filtered) == 1
        assert filtered[0]['field'] == 'product_type'
        assert filtered[0]['is_verified'] is True

    def test_detects_cross_page_conflicts(self):
        facts = [
            {
                "category": "COMPANY",
                "field": "founded_year",
                "value": "2010",
                "source_quote": "Founded in 2010",
                "source_url": "https://example.com/about"
            },
            {
                "category": "COMPANY",
                "field": "founded_year",
                "value": "2014",
                "source_quote": "Established in 2014",
                "source_url": "https://example.com/history"
            }
        ]

        conflicts = self.detector.detect_conflicts(facts)
        assert len(conflicts) == 1
        assert conflicts[0]['field'] == 'founded_year'
        assert conflicts[0]['conflict'] is True
        assert len(conflicts[0]['competing_values']) == 2
