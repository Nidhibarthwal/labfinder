import pytest
from apps.crawler.discovery import LinkDiscovery

class TestDiscovery:

    def test_link_discovery_and_structural_locations(self):
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Test Company</title></head>
        <body>
            <header>
                <nav>
                    <a href="/who-we-are">Who We Are</a>
                    <a href="/platform">Our Platform</a>
                </nav>
            </header>
            <main>
                <p>Welcome to our site. Check out our <a href="/case-studies">Customer Stories</a>.</p>
                <p>External link to our partner: <a href="https://external-partner.com/info">Partner</a>.</p>
            </main>
            <footer>
                <div class="footer-links">
                    <a href="/corporate-profile">Corporate Profile</a>
                    <a href="/contact">Get in Touch</a>
                </div>
            </footer>
        </body>
        </html>
        """
        discovery = LinkDiscovery(base_url="https://testcompany.com")
        links = discovery.discover_links(sample_html, page_url="https://testcompany.com")

        # Assert internal links discovered
        normalized_urls = {l.normalized_url: l for l in links}

        assert "https://testcompany.com/who-we-are" in normalized_urls
        assert "https://testcompany.com/platform" in normalized_urls
        assert "https://testcompany.com/case-studies" in normalized_urls
        assert "https://testcompany.com/corporate-profile" in normalized_urls
        assert "https://testcompany.com/contact" in normalized_urls

        # External partner link should be excluded
        assert "https://external-partner.com/info" not in normalized_urls

        # Check location annotations
        who_we_are = normalized_urls["https://testcompany.com/who-we-are"]
        assert who_we_are.location in ("nav", "header")
        assert who_we_are.anchor_text == "Who We Are"

        corp_profile = normalized_urls["https://testcompany.com/corporate-profile"]
        assert corp_profile.location == "footer"
        assert corp_profile.anchor_text == "Corporate Profile"

        case_studies = normalized_urls["https://testcompany.com/case-studies"]
        assert case_studies.location == "body"
