import pytest
from apps.extractor.cleaner import ContentExtractor

class TestContentExtractor:

    def test_strips_boilerplate_and_preserves_content(self):
        raw_html = """
        <html>
        <head>
            <title>Enterprise AI Systems - Overview</title>
            <script>alert("tracking code");</script>
            <style>.banner { color: red; }</style>
        </head>
        <body>
            <header>Header Logo</header>
            <div class="cookie-consent-banner">We use cookies. Accept?</div>
            <main>
                <h1>Next-Gen Website Intelligence</h1>
                <h2>Architectural Foundations</h2>
                <p>Enterprise AI Systems was founded in 2021 by Jane Doe. The company builds automated discovery software.</p>
                <h3>Global Deployments</h3>
                <p>We serve 500+ enterprises across 30 countries globally with 99.99% availability.</p>
            </main>
            <div id="advertisement-box">Sponsored ad content</div>
            <footer>Copyright 2026 Enterprise AI Inc. All rights reserved.</footer>
        </body>
        </html>
        """
        extractor = ContentExtractor()
        extracted = extractor.extract(raw_html)

        assert extracted.title == "Enterprise AI Systems - Overview"
        assert "tracking code" not in extracted.clean_text
        assert "cookie" not in extracted.clean_text.lower()
        assert "Sponsored ad content" not in extracted.clean_text
        assert "Next-Gen Website Intelligence" in extracted.clean_text
        assert "founded in 2021" in extracted.clean_text
        assert len(extracted.headings['h1']) == 1
        assert len(extracted.headings['h2']) == 1
        assert extracted.quality_score >= 0.5

    def test_low_quality_empty_content(self):
        extractor = ContentExtractor()
        extracted = extractor.extract("<html><body><script>let a=1;</script></body></html>")
        assert extracted.text_length == 0
        assert extracted.quality_score == 0.0
