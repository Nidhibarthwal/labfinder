import pytest
from apps.crawler.normalizer import (
    normalize_url,
    extract_domain,
    is_same_domain,
    is_valid_http_url
)

class TestNormalizer:

    def test_relative_url_resolution(self):
        base = "https://example.com/products/index.html"
        result = normalize_url("../about-us", base_url=base)
        assert result == "https://example.com/about-us"

    def test_strips_fragments(self):
        url = "https://example.com/team#leadership"
        assert normalize_url(url) == "https://example.com/team"

    def test_strips_tracking_params_while_keeping_content_params(self):
        url = "https://example.com/search?q=ai&utm_source=twitter&utm_medium=cpc&page=2"
        normalized = normalize_url(url)
        assert "utm_source" not in normalized
        assert "utm_medium" not in normalized
        assert "page=2" in normalized
        assert "q=ai" in normalized

    def test_trailing_slash_normalization(self):
        assert normalize_url("https://example.com/company/") == "https://example.com/company"
        assert normalize_url("https://example.com/") == "https://example.com/"

    def test_extract_domain(self):
        assert extract_domain("https://www.example.com/about") == "example.com"
        assert extract_domain("https://sub.domain.co.uk:8080/path") == "sub.domain.co.uk"

    def test_same_domain_check(self):
        assert is_same_domain("https://example.com", "https://www.example.com/contact")
        assert not is_same_domain("https://example.com", "https://google.com")

    def test_ignores_static_assets(self):
        assert normalize_url("https://example.com/report.pdf") is None
        assert normalize_url("https://example.com/logo.png") is None
        assert normalize_url("https://example.com/styles.css") is None
