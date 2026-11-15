import pytest
from apps.analysis.schema import validate_and_normalize_structured_data, CANONICAL_SCHEMA_KEYS

class TestSchemaValidation:

    def test_schema_key_invariance(self):
        input_data = {
            "website": "https://example.com",
            "summary": "Example website summary",
            "company_logo": {"url": "https://example.com/logo.png"},
            "about_us": {"summary": "A test lab summary"},
            "contact_us": {
                "headquarter": {"phone": ["+1-800-555-0199"], "email": "info@example.com"},
                "social_links": {"twitter": "https://twitter.com/example"}
            },
            "products_services": [{"name": "Blood Test", "summary": "Full blood analysis"}],
            "accreditations": [{"name": "ISO 9001:2015"}]
        }
        normalized = validate_and_normalize_structured_data(input_data, root_url="https://example.com")
        
        assert set(normalized.keys()) == CANONICAL_SCHEMA_KEYS
        assert normalized["website"] == "https://example.com"
        assert normalized["summary"] == "Example website summary"
        assert normalized["company_logo"]["url"] == "https://example.com/logo.png"
        assert normalized["company_logo"]["base64"] is None
        assert normalized["about_us"]["summary"] == "A test lab summary"
        assert normalized["contact_us"]["headquarter"]["phone"] == ["+1-800-555-0199"]
        assert normalized["contact_us"]["headquarter"]["email"] == "info@example.com"
        assert isinstance(normalized["contact_us"]["social_links"], dict)
        assert normalized["contact_us"]["social_links"]["twitter"] == "https://twitter.com/example"
        assert len(normalized["products_services"]) == 1
        assert normalized["products_services"][0]["name"] == "Blood Test"
        assert len(normalized["accreditations"]) == 1
        assert normalized["accreditations"][0]["name"] == "ISO 9001:2015"

    def test_unknown_keys_stripped(self):
        input_data = {
            "website": "https://example.com",
            "unknown_extra_field": "should be stripped",
            "hallucinated_section": {"random": 123},
        }
        normalized = validate_and_normalize_structured_data(input_data, root_url="https://example.com")
        
        assert "unknown_extra_field" not in normalized
        assert "hallucinated_section" not in normalized
        assert set(normalized.keys()) == CANONICAL_SCHEMA_KEYS

    def test_missing_fields_defaulted(self):
        normalized = validate_and_normalize_structured_data(None, root_url="https://empty-lab.example")
        
        assert normalized["website"] == "https://empty-lab.example"
        assert normalized["summary"] == ""
        assert normalized["company_logo"] == {"url": None, "base64": None, "alt": None, "source_page": None}
        assert normalized["about_us"] == {"summary": "", "source_url": ""}
        assert normalized["contact_us"]["headquarter"]["phone"] == []
        assert normalized["contact_us"]["headquarter"]["email"] == ""
        assert normalized["contact_us"]["headquarter"]["address"]["full_address"] == ""
        assert normalized["contact_us"]["branches"] == {}
        assert normalized["contact_us"]["social_links"]["facebook"] == ""
        assert normalized["products_services"] == []
        assert normalized["accreditations"] == []

