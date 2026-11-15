import json
import pytest
from unittest.mock import patch, MagicMock
from apps.analysis.models import Website, AnalysisJob, WorkflowState, AnalysisResult, Page
from apps.workflow.engine import WorkflowEngine
from apps.workflow.agent import AgentPlanner, CandidatePage
from apps.workflow.config import TargetExtractionConfig
from apps.crawler.http_client import FetchResult, SafeHttpClient
from apps.extractor.logo import LogoExtractor
from apps.extractor.sections import ProductServiceExtractor
from apps.extractor.deterministic import extract_contact_bundle
from apps.classifier.classifier import PageClassifier


class TestIntertekTargetConstraint:
    """
    Validates that only user-specified target pages (ABOUT, CONTACT, PRODUCT, SERVICE)
    are ever considered or crawled, and all other pages (CAREERS, BLOG, PRESS, etc.) are rejected.
    """

    def test_intertek_candidate_filtering_rejects_unrequested_pages(self):
        config = TargetExtractionConfig(
            objective="lab_intelligence",
            target_page_types=["ABOUT", "CONTACT", "PRODUCT", "SERVICE"],
            required_page_types=["ABOUT", "CONTACT"],
            max_pages=4,
            min_pages=2
        )
        planner = AgentPlanner(objective="lab_intelligence", target_config=config)

        candidates = [
            CandidatePage(url="https://www.intertek.com/about", normalized_url="https://www.intertek.com/about", page_type="ABOUT", confidence=1.0),
            CandidatePage(url="https://www.intertek.com/contact", normalized_url="https://www.intertek.com/contact", page_type="CONTACT", confidence=0.8),
            CandidatePage(url="https://www.intertek.com/services", normalized_url="https://www.intertek.com/services", page_type="SERVICE", confidence=0.9),
            CandidatePage(url="https://www.intertek.com/products-retail", normalized_url="https://www.intertek.com/products-retail", page_type="PRODUCT", confidence=0.9),
            # Unrequested pages that must be strictly rejected
            CandidatePage(url="https://www.intertek.com/careers", normalized_url="https://www.intertek.com/careers", page_type="CAREERS", confidence=0.9),
            CandidatePage(url="https://www.intertek.com/blog", normalized_url="https://www.intertek.com/blog", page_type="BLOG", confidence=0.9),
            CandidatePage(url="https://www.intertek.com/press", normalized_url="https://www.intertek.com/press", page_type="PRESS", confidence=0.9),
            CandidatePage(url="https://www.intertek.com/resources/case-studies", normalized_url="https://www.intertek.com/resources/case-studies", page_type="CASE_STUDY", confidence=0.9),
            CandidatePage(url="https://www.intertek.com/news/article", normalized_url="https://www.intertek.com/news/article", page_type="NEWS", confidence=0.7),
        ]

        analysed_urls = set()
        selected_pages = []

        # Simulate planner selections
        while len(selected_pages) < config.max_pages:
            action, candidate = planner.select_next_action(
                candidates=candidates,
                analysed_urls=analysed_urls,
                collected_categories={"ABOUT"} if len(selected_pages) > 0 else set(),
                budget_exhausted=False,
                attempted_urls=analysed_urls
            )
            if action == 'FINISH' or not candidate:
                break
            selected_pages.append(candidate)
            analysed_urls.add(candidate.normalized_url)

        # Ensure ONLY allowed page types were selected
        allowed_types = {"ABOUT", "CONTACT", "PRODUCT", "SERVICE"}
        for p in selected_pages:
            assert p.page_type in allowed_types, f"Unrequested page type {p.page_type} was selected: {p.url}"

        # Ensure careers, blog, press were NEVER selected
        selected_urls = [p.url for p in selected_pages]
        assert "https://www.intertek.com/careers" not in selected_urls
        assert "https://www.intertek.com/blog" not in selected_urls
        assert "https://www.intertek.com/press" not in selected_urls
        assert "https://www.intertek.com/resources/case-studies" not in selected_urls


class TestIntertekExtraction:
    """
    Validates logo, services, about, and contact extraction against Intertek HTML patterns.
    """

    def test_intertek_logo_extraction(self):
        intertek_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta property="og:image" content="https://www.intertek.com/globalassets/_media/co-branded-logos/itk-sustainability-logo.svg" />
        </head>
        <body>
            <header>
                <div class="logo-container">
                    <a href="/">
                        <img src="/globalassets/_media/co-branded-logos/itk-sustainability-logo.svg" alt="Intertek Total Sustainability logo" class="main-logo" />
                    </a>
                </div>
            </header>
        </body>
        </html>
        """
        extractor = LogoExtractor()
        logo = extractor.extract_logo(intertek_html, "https://www.intertek.com/")
        assert "itk-sustainability-logo.svg" in logo["url"]
        assert logo["alt"] == "Intertek Total Sustainability logo"
        assert logo["source_page"] == "https://www.intertek.com/"

    def test_intertek_services_segmentation(self):
        services_html = """
        <html>
        <body>
            <main>
                <h1>Intertek Testing & Laboratory Services</h1>
                <h2>Total Quality Assurance (TQA)</h2>
                <p>Systematic approach to evaluating products, processes, and assets to international standards.</p>
                <ul>
                    <li>Quality Benchmarking</li>
                    <li>Regulatory Risk Mitigation</li>
                </ul>

                <h2>Laboratory Analytical Testing</h2>
                <p>Comprehensive physical, chemical, and microbiological testing across global accredited laboratories.</p>
                <ul>
                    <li>Chromatography and Mass Spectrometry</li>
                    <li>Fast turnaround analytical verification</li>
                </ul>

                <h2>Global Inspection & Certification</h2>
                <p>Independent inspection services verifying compliance across global supply chains.</p>
                <ul>
                    <li>Pre-shipment verification</li>
                    <li>ISO 9001 and ISO 17025 conformity</li>
                </ul>
            </main>
        </body>
        </html>
        """
        extractor = ProductServiceExtractor()
        items = extractor.extract_from_html(services_html, "https://www.intertek.com/services")

        assert len(items) == 3
        names = [it["name"] for it in items]
        assert "Total Quality Assurance (TQA)" in names
        assert "Laboratory Analytical Testing" in names
        assert "Global Inspection & Certification" in names

        for it in items:
            assert it["type"] in ("service", "product", "unknown")
            assert len(it["details"]) >= 1
            assert it["source_url"] == "https://www.intertek.com/services"

    def test_intertek_contact_bundle_extraction(self):
        contact_html_text = """
        Intertek Headquarters and Testing Locations
        Call our main customer service center: +44 20 7396 3400 or toll-free +1 800 967 5352
        Email support: info@intertek.com or global.inquiries@intertek.com
        Headquarters: 33 Cavendish Square, London W1G 0PS, United Kingdom
        Hours of Operation: Mon-Fri: 08:30 - 17:30 GMT
        Official channels: https://linkedin.com/company/intertek
        """
        bundle = extract_contact_bundle(contact_html_text, "https://www.intertek.com/contact")
        assert len(bundle["phone"]) >= 1
        assert any("intertek.com" in e for e in bundle["email"])
        assert any("Cavendish Square" in a for a in bundle["address"])
        assert len(bundle["working_hours"]) >= 1
        assert "https://linkedin.com/company/intertek" in bundle["social_links"]
        assert bundle["source_url"] == "https://www.intertek.com/contact"


@pytest.mark.django_db
class TestIntertekWorkflowEndToEnd:

    @patch('apps.ai.ollama.OllamaProvider.generate')
    @patch('apps.workflow.engine.SafeHttpClient.fetch')
    @patch('apps.workflow.engine.validate_url_security')
    def test_intertek_lab_intelligence_pipeline(self, mock_validate, mock_fetch, mock_llm_generate):
        mock_validate.return_value = ("www.intertek.com", "93.184.216.34")

        home_html = """
        <html>
        <head>
            <title>Intertek | Total Quality Assured</title>
            <meta property="og:image" content="https://www.intertek.com/globalassets/_media/logo.svg" />
        </head>
        <body>
            <header>
                <nav>
                    <a href="/about">About Us</a>
                    <a href="/services">Services & Testing</a>
                    <a href="/contact">Contact</a>
                    <a href="/careers">Careers</a>
                    <a href="/blog">Blog</a>
                </nav>
            </header>
            <main>
                <h1>Total Quality. Assured.</h1>
                <p>Intertek is an industry leader with more than 44,000 employees in 1,000 locations across over 100 countries.</p>
            </main>
        </body>
        </html>
        """

        about_html = """
        <html>
        <head><title>About Intertek | Total Quality Assurance</title></head>
        <body>
            <main>
                <h1>About Intertek</h1>
                <p>Intertek is a leading Total Quality Assurance provider to industries worldwide delivering bespoke Assurance, Testing, Inspection and Certification solutions.</p>
                <p>Our network of more than 1,000 laboratories and offices in more than 100 countries delivers innovative Quality Assurance solutions.</p>
            </main>
        </body>
        </html>
        """

        services_html = """
        <html>
        <head><title>Intertek Laboratory Services</title></head>
        <body>
            <main>
                <h1>Intertek Lab Testing Services</h1>
                <h2>Analytical Laboratory Testing</h2>
                <p>Comprehensive laboratory analysis across materials, pharmaceuticals, food, and environmental samples.</p>
                <ul>
                    <li>ISO 17025 accredited laboratory testing</li>
                    <li>Spectroscopy, chromatography, and elemental trace analysis</li>
                </ul>

                <h2>Product Safety Testing & Certification</h2>
                <p>Evaluating electrical, medical, and consumer products against national and international safety benchmarks.</p>
                <ul>
                    <li>ETL Listed Mark safety certification</li>
                    <li>EMC and wireless radio compliance testing</li>
                </ul>
            </main>
        </body>
        </html>
        """

        contact_html = """
        <html>
        <head><title>Contact Intertek</title></head>
        <body>
            <main>
                <h1>Contact Us</h1>
                <p>General inquiries: +44 20 7396 3400</p>
                <p>Email: global.inquiries@intertek.com</p>
                <p>Hours of Operation: Mon-Fri: 08:30 - 17:30</p>
                <p>Corporate Office: 33 Cavendish Square, London W1G 0PS, United Kingdom</p>
                <a href="https://linkedin.com/company/intertek">LinkedIn</a>
            </main>
        </body>
        </html>
        """

        def mock_fetch_side(url, **kwargs):
            if "about" in url:
                return FetchResult(url=url, status_code=200, html=about_html)
            elif "services" in url:
                return FetchResult(url=url, status_code=200, html=services_html)
            elif "contact" in url:
                return FetchResult(url=url, status_code=200, html=contact_html)
            elif "robots.txt" in url:
                return FetchResult(url=url, status_code=404, html="")
            return FetchResult(url=url, status_code=200, html=home_html)

        mock_fetch.side_effect = mock_fetch_side

        llm_response = {
            "website": {
                "name": "Intertek",
                "domain": "intertek.com",
                "url": "https://www.intertek.com/"
            },
            "about_us": {
                "summary": "Leading Total Quality Assurance provider delivering bespoke Assurance, Testing, Inspection and Certification solutions.",
                "details": "Network of more than 1,000 laboratories and offices in more than 100 countries.",
                "source_url": "https://www.intertek.com/about"
            },
            "contact_us": {
                "phone": ["+44 20 7396 3400"],
                "email": ["global.inquiries@intertek.com"],
                "address": ["33 Cavendish Square, London W1G 0PS, United Kingdom"],
                "working_hours": ["Mon-Fri: 08:30 - 17:30"],
                "social_links": ["https://linkedin.com/company/intertek"],
                "source_url": "https://www.intertek.com/contact"
            },
            "products_services": [
                {
                    "name": "Analytical Laboratory Testing",
                    "type": "service",
                    "summary": "Comprehensive laboratory analysis across materials, pharmaceuticals, food, and environmental samples.",
                    "details": ["ISO 17025 accredited laboratory testing"],
                    "source_url": "https://www.intertek.com/services"
                },
                {
                    "name": "Product Safety Testing & Certification",
                    "type": "service",
                    "summary": "Evaluating electrical, medical, and consumer products against safety benchmarks.",
                    "details": ["ETL Listed Mark safety certification"],
                    "source_url": "https://www.intertek.com/services"
                }
            ],
            "facts": [
                {
                    "category": "SERVICE",
                    "field": "laboratory_testing",
                    "value": "Delivers bespoke Assurance, Testing, Inspection and Certification solutions",
                    "source_quote": "delivering bespoke Assurance, Testing, Inspection and Certification solutions",
                    "source_url": "https://www.intertek.com/about"
                }
            ],
            "summary_markdown": "# Intertek Laboratory Intelligence\nIntertek Total Quality Assurance Dossier."
        }
        mock_llm_generate.return_value = json.dumps(llm_response)

        website = Website.objects.create(domain="intertek.com", root_url="https://www.intertek.com/")
        job = AnalysisJob.objects.create(
            website=website,
            objective="lab_intelligence",
            options={"fast_mode": True}
        )

        engine = WorkflowEngine(str(job.id))
        completed_job = engine.execute()

        assert completed_job.status == WorkflowState.COMPLETED
        result = AnalysisResult.objects.get(job=completed_job)
        structured = result.structured_data

        # Verify exact Requirement schema keys
        for key in ["website", "summary", "company_logo", "about_us", "contact_us", "products_services", "accreditations"]:
            assert key in structured, f"Missing key: {key}"

        # 1. Logo
        assert "logo.svg" in structured["company_logo"]["url"]

        # 2. About Us
        assert "quality assurance" in structured["about_us"]["summary"].lower()
        assert structured["about_us"]["source_url"] == "https://www.intertek.com/about"

        # 3. Contact Us
        hq = structured["contact_us"]["headquarter"]
        assert "+44 20 7396 3400" in hq["phone"]
        assert hq["email"] == "global.inquiries@intertek.com"
        assert "Cavendish Square" in hq["address"]["full_address"]

        # 4. Products / Services
        services = structured["products_services"]
        assert len(services) >= 2
        service_names = [s["name"] for s in services]
        assert "Analytical Laboratory Testing" in service_names
        assert "Product Safety Testing & Certification" in service_names

        # 5. Verify unrequested pages were NOT crawled
        crawled_pages = Page.objects.filter(website=website)
        for page in crawled_pages:
            assert "careers" not in page.url.lower()
            assert "blog" not in page.url.lower()
            assert "press" not in page.url.lower()

