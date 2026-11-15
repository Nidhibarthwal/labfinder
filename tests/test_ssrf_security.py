import pytest
from apps.crawler.security import (
    validate_url_security,
    SSRFBlockedException,
    InvalidURLException,
    DNSResolutionException,
)

class TestSSRFSecurity:

    @pytest.mark.parametrize("blocked_url", [
        "http://127.0.0.1",
        "http://127.0.0.1:8000/admin",
        "http://localhost",
        "http://localhost:11434",
        "http://0.0.0.0",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/internal",
        "http://172.16.0.1",
        "http://192.168.1.1",
        "http://100.64.0.1",
        "http://[::1]/",
        "http://[fe80::1]/",
    ])
    def test_ssrf_blocks_private_and_loopback_destinations(self, blocked_url):
        with pytest.raises(SSRFBlockedException):
            validate_url_security(blocked_url)

    @pytest.mark.parametrize("invalid_scheme_url", [
        "file:///etc/passwd",
        "ftp://ftp.example.com",
        "gopher://example.com",
        "javascript:alert(1)",
        "mailto:admin@example.com",
        "",
        "not-a-valid-url",
    ])
    def test_rejects_invalid_schemes_and_malformed_urls(self, invalid_scheme_url):
        with pytest.raises(InvalidURLException):
            validate_url_security(invalid_scheme_url)

    def test_rejects_unresolvable_dns(self):
        with pytest.raises(DNSResolutionException):
            validate_url_security("https://non-existent-subdomain-dns-test-12345.com")

    def test_allows_legitimate_public_url(self):
        host, ip = validate_url_security("https://example.com")
        assert host == "example.com"
        assert ip is not None
