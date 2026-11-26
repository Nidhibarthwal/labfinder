import json
import pytest
from unittest.mock import MagicMock, patch
from apps.analysis.models import Website, AnalysisJob, WorkflowState, AnalysisResult, Page
from apps.workflow.engine import WorkflowEngine
from apps.workflow.config import TargetExtractionConfig
from apps.crawler.http_client import FetchResult
from apps.extractor.logo import LogoExtractor
from apps.extractor.sections import ProductServiceExtractor
from apps.extractor.deterministic import extract_contact_bundle, extract_social_links
from apps.classifier.classifier import PageClassifier, PageRanker


class TestLogoExtractor:

    def test_full_address_and_subfield_parsing(self):
        clean_text = """
        GHAZIABAD TESTING LABORATORIES PVT. LTD.
        OFFICE ADDRESS
        AO-150 Amrit Steel Compound South Side, G.T Road Ind. Area,
        Ghaziabad-201001, UP, India
        PHONE
        +919811054649
        +917668106301
        EMAIL ADDRESS
        info@gtllab.org
        """
        from apps.extractor.deterministic import extract_deterministic_facts
        from apps.analysis.schema import parse_address_dict

        facts = extract_deterministic_facts(clean_text, "https://gtllab.org/contact-us/")
        addr_facts = [f for f in facts if f['field'] == 'address']
        assert len(addr_facts) >= 1
        full_addr = addr_facts[0]['value']
        assert "AO-150 Amrit Steel Compound South Side, G.T Road Ind. Area" in full_addr
        assert "Ghaziabad" in full_addr
        assert "201001" in full_addr

        parsed = parse_address_dict(full_addr)
        assert parsed["country"] == "India"
        assert parsed["state"] == "Uttar Pradesh"
        assert parsed["city"] == "Ghaziabad"
        assert parsed["pin_code"] == "201001"

    def test_address_inference_engine(self):
        from apps.analysis.schema import parse_address_dict

        # Test pattern where country is omitted but state abbreviation UP & 5-digit pin exist
        addr1 = "G-68, G-Block, Noida Sector 63, UP 201301"
        res1 = parse_address_dict(addr1)
        assert res1["full_address"] == "G-68, G-Block, Noida Sector 63, UP 201301"
        assert res1["country"] == "India"
        assert res1["state"] == "Uttar Pradesh"
        assert res1["city"] == "Noida"
        assert res1["pin_code"] == "201301"

        # Test pattern where MP abbreviation is used
        addr2 = "MP Nagar Zone 1, Bhopal 462011, MP"
        res2 = parse_address_dict(addr2)
        assert res2["full_address"] == "MP Nagar Zone 1, Bhopal 462011, MP"
        assert res2["country"] == "India"
        assert res2["state"] == "Madhya Pradesh"
        assert res2["city"] == "Bhopal"
        assert res2["pin_code"] == "462011"

    def test_jsonld_logo_extraction(self):
        html = """
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "MedicalOrganization",
                "name": "Apex Diagnostics Lab",
                "logo": "https://apex-lab.example/images/apex_logo.png"
            }
            </script>
        </head>
        <body><h1>Apex Diagnostics</h1></body>
        </html>
        """
        extractor = LogoExtractor()
        logo = extractor.extract_logo(html, "https://apex-lab.example")
        assert logo["url"] == "https://apex-lab.example/images/apex_logo.png"
        assert logo["alt"] == "Apex Diagnostics Lab"
        assert logo["source_page"] == "https://apex-lab.example"

    def test_header_nav_img_logo_extraction(self):
        html = """
        <html>
        <body>
            <header>
                <div class="site-branding">
                    <a href="/"><img class="custom-logo" src="/assets/branding/main_logo.svg" alt="Apex Lab Brand"></a>
                </div>
            </header>
        </body>
        </html>
        """
        extractor = LogoExtractor()
        logo = extractor.extract_logo(html, "https://apex-lab.example")
        assert logo["url"] == "https://apex-lab.example/assets/branding/main_logo.svg"
        assert logo["alt"] == "Apex Lab Brand"

    def test_itemprop_logo_extraction(self):
        html = """
        <html>
        <body>
            <div itemscope itemtype="http://schema.org/Organization">
                <img itemprop="logo" src="https://apex-lab.example/logo.jpg" alt="Lab Logo">
            </div>
        </body>
        </html>
        """
        extractor = LogoExtractor()
        logo = extractor.extract_logo(html, "https://apex-lab.example")
        assert logo["url"] == "https://apex-lab.example/logo.jpg"

    def test_opengraph_fallback(self):
        html = """
        <html>
        <head>
            <meta property="og:image" content="https://apex-lab.example/og_preview.png">
        </head>
        <body><main><p>Content without explicit logo img</p></main></body>
        </html>
        """
        extractor = LogoExtractor()
        logo = extractor.extract_logo(html, "https://apex-lab.example")
        assert logo["url"] == "https://apex-lab.example/og_preview.png"

    def test_social_icons_ignored(self):
        html = """
        <html>
        <header>
            <div class="social-share">
                <img src="/icons/facebook-logo.png" alt="Facebook">
                <img src="/icons/twitter-icon.png" alt="Twitter">
            </div>
        </header>
        <body>
            <img class="brand-logo" src="/img/lab_actual_logo.png" alt="BioMed Diagnostics">
        </body>
        </html>
        """
        extractor = LogoExtractor()
        logo = extractor.extract_logo(html, "https://biomed.example")
        assert "facebook" not in logo["url"]
        assert "twitter" not in logo["url"]
        assert logo["url"] == "https://biomed.example/img/lab_actual_logo.png"

    def test_missing_logo_returns_none_contract(self):
        html = "<html><body><p>Plain text page with no images</p></body></html>"
        extractor = LogoExtractor()
        logo = extractor.extract_logo(html, "https://plain.example")
        assert logo == {"url": None, "base64": None, "alt": None, "source_page": None}

    def test_data_uri_logo_extraction(self):
        data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        html = f'<html><body><header><img class="logo" src="{data_uri}" alt="Data Logo"></header></body></html>'
        extractor = LogoExtractor()
        logo = extractor.extract_logo(html, "https://data.example")
        assert logo["url"] == data_uri
        assert logo["base64"] == data_uri
        assert logo["alt"] == "Data Logo"

    def test_url_to_base64_conversion(self):
        extractor = LogoExtractor()
        class DummyHttpClient:
            def fetch_binary(self, url):
                return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR', 'image/png'
        
        b64 = extractor.url_to_base64("https://example.com/logo.png", http_client=DummyHttpClient())
        assert b64.startswith("data:image/png;base64,")



class TestProductServiceExtractor:

    def test_stellar_test_house_noise_filtering(self):
        from apps.analysis.schema import validate_and_normalize_structured_data
        raw_data = {
            "products_services": [
                {
                    "name": "Call Us At",
                    "summary": "+91 9811129125 +91 120 4277668/69",
                    "source_url": "https://stellartesthouse.com/contact-us"
                },
                {
                    "name": "Mail Us At",
                    "summary": "info@stellartesthouse.com",
                    "source_url": "https://stellartesthouse.com/contact-us"
                },
                {
                    "name": "Visit Us At",
                    "summary": "G-68, G-Block, Noida Sector 63, Uttar Pradesh 201301",
                    "source_url": "https://stellartesthouse.com/contact-us"
                },
                {
                    "name": "Get a Callback",
                    "summary": "Contact form callback request",
                    "source_url": "https://stellartesthouse.com/contact-us"
                },
                {
                    "name": "Our Story",
                    "summary": "History of the testing lab",
                    "source_url": "https://stellartesthouse.com/about-us"
                },
                {
                    "name": "QUALITY POLICY",
                    "summary": "Quality standards overview",
                    "source_url": "https://stellartesthouse.com/about-us"
                },
                {
                    "name": "Independence",
                    "summary": "Core value of impartiality",
                    "source_url": "https://stellartesthouse.com/about-us"
                },
                {
                    "name": "Vaibhav Jain",
                    "summary": "Customer review comment",
                    "source_url": "https://stellartesthouse.com"
                },
                {
                    "name": "Road Material Testing",
                    "summary": "Comprehensive road, bitumen, and aggregate testing services.",
                    "source_url": "https://stellartesthouse.com/road-material-testing"
                },
                {
                    "name": "Soil Testing Laboratory",
                    "summary": "Geotechnical and soil analysis for foundation stability.",
                    "source_url": "https://stellartesthouse.com/soil-testing"
                }
            ]
        }
        res = validate_and_normalize_structured_data(raw_data)
        ps = res["products_services"]
        names = [item["name"] for item in ps]

        assert "Call Us At" not in names
        assert "Mail Us At" not in names
        assert "Visit Us At" not in names
        assert "Get a Callback" not in names
        assert "Our Story" not in names
        assert "QUALITY POLICY" not in names
        assert "Independence" not in names
        assert "Vaibhav Jain" not in names

        assert "Road Material Testing" in names
        assert "Soil Testing Laboratory" in names
        assert len(ps) == 2

    def test_service_intro_summary_filtering(self):
        from apps.analysis.schema import validate_and_normalize_structured_data
        raw_data = {
            "products_services": [
                {
                    "name": "Electrical Testing",
                    "summary": "Ghaziabad Testing Laboratories Pvt. Welcome to Ghaziabad Testing Laboratories Pvt. Ltd, a leading third-party quality control testing laboratory that has been providing a wide range of testing services to clients in India since 2002.",
                    "source_url": "https://gtllab.org/about-us"
                },
                {
                    "name": "Food & Water Testing",
                    "summary": "Microbial testing | Pesticide residue testing | Food safety testing | Heavy metal testing | Water quality testing",
                    "source_url": "https://gtllab.org/about-us"
                }
            ]
        }
        res = validate_and_normalize_structured_data(raw_data)
        ps = res["products_services"]
        assert len(ps) == 2
        # Electrical testing generic intro summary stripped
        assert ps[0]["name"] == "Electrical Testing"
        assert ps[0]["summary"] == ""
        # Food & Water testing genuine service details preserved
        assert ps[1]["name"] == "Food & Water Testing"
        assert "Microbial testing" in ps[1]["summary"]

    def test_heading_based_extraction(self):
        html = """
        <html>
        <body>
            <main>
                <h2>Comprehensive Metabolic Panel (CMP)</h2>
                <p>A critical blood test evaluating organ function, blood sugar, and electrolytes.</p>
                <ul>
                    <li>14 Individual Biomarkers</li>
                    <li>Turnaround time: 24 hours</li>
                    <li>Specimen: Serum (fasting 10-12 hours)</li>
                </ul>

                <h2>Lipid Profile Test</h2>
                <p>Measures cholesterol and triglyceride levels to assess cardiovascular risk.</p>
                <ul>
                    <li>Parameters: Total, HDL, LDL, VLDL</li>
                    <li>Specimen: 3ml whole blood</li>
                </ul>
            </main>
        </body>
        </html>
        """
        extractor = ProductServiceExtractor()
        items = extractor.extract_from_html(html, "https://apex-lab.example/tests")
        assert len(items) == 2

        cmp_item = items[0]
        assert "Comprehensive Metabolic Panel" in cmp_item["name"]
        assert cmp_item["type"] == "service"
        assert "blood test" in cmp_item["summary"].lower()
        assert len(cmp_item["details"]) == 3
        assert "Turnaround time: 24 hours" in cmp_item["details"]

        lipid_item = items[1]
        assert "Lipid Profile" in lipid_item["name"]
        assert lipid_item["type"] == "service"
        assert len(lipid_item["details"]) == 2

    def test_card_container_extraction(self):
        html = """
        <html>
        <body>
            <div class="test-card">
                <h3>RT-PCR Molecular Assay Kit</h3>
                <p>High sensitivity in-vitro diagnostic reagent kit for infectious pathogen detection.</p>
                <ul>
                    <li>Sensitivity: 99.4%</li>
                    <li>Format: 96 tests/pack</li>
                </ul>
            </div>
        </body>
        </html>
        """
        extractor = ProductServiceExtractor()
        items = extractor.extract_from_html(html, "https://apex-lab.example/products")
        assert len(items) == 1
        assert "RT-PCR Molecular Assay Kit" in items[0]["name"]
        assert items[0]["type"] == "product"
        assert any("96 tests/pack" in d for d in items[0]["details"])

    def test_deduplication(self):
        items = [
            {"name": "Complete Blood Count (CBC)", "type": "service", "summary": "Full CBC"},
            {"name": "complete blood count (cbc)", "type": "service", "summary": "Duplicate CBC"},
            {"name": "Thyroid Profile (T3, T4, TSH)", "type": "service", "summary": "Thyroid panel"}
        ]
        unique = ProductServiceExtractor.deduplicate(items)
        assert len(unique) == 2
        assert unique[0]["name"] == "Complete Blood Count (CBC)"
        assert unique[1]["name"] == "Thyroid Profile (T3, T4, TSH)"

    def test_empty_html_handling(self):
        extractor = ProductServiceExtractor()
        assert extractor.extract_from_html("", "https://example.com") == []
        assert extractor.extract_from_html(None, "https://example.com") == []


class TestDeterministicContactBundle:

    def test_extract_contact_bundle(self):
        text = """
        Contact Apex Diagnostics
        Main Lab: +1 (555) 234-5678, Helpline: +1 800-987-6543
        Email inquiries: support@apex-diagnostics.com, billing@apex-diagnostics.com
        Central Pathology Lab: 742 Evergreen Terrace, Medical District, Springfield 123456
        Hours of Operation: Mon-Fri: 07:00 - 20:00, Sat: 08:00 - 14:00
        Follow us: https://linkedin.com/company/apex-diagnostics
        """
        bundle = extract_contact_bundle(text, "https://apex-diagnostics.com/contact")
        assert len(bundle["phone"]) >= 1
        assert "support@apex-diagnostics.com" in bundle["email"]
        assert len(bundle["address"]) >= 1
        assert len(bundle["working_hours"]) >= 1
        assert "https://linkedin.com/company/apex-diagnostics" in bundle["social_links"]
        assert bundle["source_url"] == "https://apex-diagnostics.com/contact"

    def test_empty_contact_bundle_schema(self):
        bundle = extract_contact_bundle("Welcome to our portal with no contact data.", "https://example.com")
        assert bundle == {
            "phone": [],
            "email": [],
            "address": [],
            "working_hours": [],
            "social_links": [],
            "source_url": None
        }

    def test_extract_social_links_from_html_footer_and_nav(self):
        html = """
        <html>
        <body>
            <header>
                <a href="https://twitter.com/ApexDiagnostics?ref=header">Twitter</a>
            </header>
            <footer>
                <a href="https://www.linkedin.com/company/apex-diagnostics/">LinkedIn</a>
                <a href="https://facebook.com/ApexDiagnosticsOfficial?utm_source=footer">Facebook</a>
                <a href="https://instagram.com/apex_diagnostics">Instagram</a>
                <a href="https://www.youtube.com/@ApexDiagnostics">YouTube</a>
                <a href="https://github.com/apex-diagnostics">GitHub</a>
            </footer>
        </body>
        </html>
        """
        socials = extract_social_links(clean_text="", html=html)
        assert "https://twitter.com/ApexDiagnostics" in socials
        assert "https://linkedin.com/company/apex-diagnostics" in socials
        assert "https://facebook.com/ApexDiagnosticsOfficial" in socials
        assert "https://instagram.com/apex_diagnostics" in socials
        assert "https://youtube.com/@ApexDiagnostics" in socials
        assert "https://github.com/apex-diagnostics" in socials

    def test_extract_social_links_from_json_ld_sameas(self):
        html = """
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": "Apex Diagnostics",
                "sameAs": [
                    "https://www.linkedin.com/company/apex-diagnostics",
                    "https://x.com/ApexDiagnostics",
                    "https://www.youtube.com/channel/UC1234567890"
                ]
            }
            </script>
        </head>
        <body><p>Hello</p></body>
        </html>
        """
        socials = extract_social_links(clean_text="", html=html)
        assert "https://linkedin.com/company/apex-diagnostics" in socials
        assert "https://x.com/ApexDiagnostics" in socials
        assert "https://youtube.com/channel/UC1234567890" in socials

    def test_extract_social_links_filters_out_share_buttons(self):
        html = """
        <html>
        <body>
            <!-- Share and intent buttons must NOT be captured as company profiles -->
            <a href="https://www.facebook.com/sharer/sharer.php?u=https://example.com/page">Share on Facebook</a>
            <a href="https://twitter.com/intent/tweet?text=Check+this+out">Tweet this</a>
            <a href="https://www.linkedin.com/shareArticle?mini=true&url=https://example.com">Share on LinkedIn</a>
            <a href="https://linkedin.com">Generic Home</a>
            <!-- Valid official profile -->
            <a href="https://www.linkedin.com/company/real-company">Real Profile</a>
        </body>
        </html>
        """
        socials = extract_social_links(clean_text="", html=html)
        assert len(socials) == 1
        assert socials[0] == "https://linkedin.com/company/real-company"

    def test_extract_contact_bundle_with_html_incorporates_socials(self):
        html = """
        <html>
        <body>
            <footer>
                <a href="https://www.linkedin.com/company/integrated-lab">LinkedIn</a>
                <a href="https://twitter.com/integrated_lab">Twitter</a>
            </footer>
        </body>
        </html>
        """
        clean_text = "Call us: +1 555-111-2222. Email: lab@integrated.example"
        bundle = extract_contact_bundle(clean_text, "https://integrated.example/contact", html=html)
        assert len(bundle["phone"]) == 1
        assert len(bundle["email"]) == 1
        assert "https://linkedin.com/company/integrated-lab" in bundle["social_links"]
        assert "https://twitter.com/integrated_lab" in bundle["social_links"]


class TestLabClassifierAndConfig:

    def test_lab_path_classification(self):
        classifier = PageClassifier()
        p_type, conf = classifier.classify_deterministic(url="https://lab.example/diagnostic-tests")
        assert p_type == "SERVICE"
        assert conf >= 0.85

        p_type2, conf2 = classifier.classify_deterministic(url="https://lab.example/test-menu")
        assert p_type2 == "SERVICE"

        p_type3, conf3 = classifier.classify_deterministic(url="https://lab.example/diagnostic-kits")
        assert p_type3 == "PRODUCT"

    def test_lab_intelligence_profile_config(self):
        website = Website(domain="apex-lab.example", root_url="https://apex-lab.example")
        job = AnalysisJob(website=website, objective="lab_intelligence")
        config = TargetExtractionConfig.from_job(job)

        assert "SERVICE" in config.target_page_types
        assert "PRODUCT" in config.target_page_types
        assert "ABOUT" in config.target_page_types
        assert "CONTACT" in config.target_page_types
        assert config.max_pages >= 4
        assert config.min_pages == 2

    def test_lab_intelligence_ranker_priorities(self):
        ranker = PageRanker()
        assert ranker.OBJECTIVE_PRIORITIES["lab_intelligence"]["SERVICE"] == 95
        assert ranker.OBJECTIVE_PRIORITIES["lab_intelligence"]["PRODUCT"] == 95
        assert ranker.OBJECTIVE_PRIORITIES["lab_intelligence"]["ABOUT"] == 100
        assert ranker.OBJECTIVE_PRIORITIES["lab_intelligence"]["CONTACT"] == 100


@pytest.mark.django_db
class TestLabWorkflowExecution:

    @patch('apps.ai.ollama.OllamaProvider.generate')
    @patch('apps.workflow.engine.SafeHttpClient.fetch')
    @patch('apps.workflow.engine.validate_url_security')
    def test_lab_intelligence_end_to_end_contract(self, mock_validate, mock_fetch, mock_llm_generate):
        mock_validate.return_value = ("apex-diagnostics.example", "93.184.216.34")

        home_html = """
        <html>
        <head>
            <title>Apex Diagnostics | Clinical Reference Laboratory</title>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "MedicalOrganization",
                "name": "Apex Diagnostics",
                "logo": "https://apex-diagnostics.example/static/logo.png"
            }
            </script>
        </head>
        <body>
            <header>
                <nav>
                    <a href="/about-us">About Us</a>
                    <a href="/test-menu">Test Menu & Pathology</a>
                    <a href="/contact">Contact & Locations</a>
                </nav>
            </header>
            <main>
                <h1>World-Class Pathology & Molecular Diagnostics</h1>
                <p>Apex Diagnostics delivers CAP and ISO accredited medical lab testing across 500+ diagnostic assays.</p>
            </main>
        </body>
        </html>
        """

        about_html = """
        <html>
        <head><title>About Us | Apex Diagnostics</title></head>
        <body>
            <main>
                <h1>About Apex Diagnostics</h1>
                <p>Established in 2012, Apex Diagnostics is a premier clinical testing laboratory accredited by NABL, CAP, and ISO 15189.</p>
                <p>Our medical directorship comprises 15 board-certified pathologists delivering 99.9% analytical accuracy.</p>
            </main>
        </body>
        </html>
        """

        service_html = """
        <html>
        <head><title>Diagnostic Test Menu | Apex Diagnostics</title></head>
        <body>
            <main>
                <h1>Diagnostic Services Menu</h1>
                <div class="test-card">
                    <h2>Complete Hemogram with Platelet Count</h2>
                    <p>Quantitative automated measurement of red cells, white cells, hemoglobin, and platelets.</p>
                    <ul>
                        <li>Turnaround time: 6 hours</li>
                        <li>Specimen: 2ml EDTA Whole Blood</li>
                        <li>Method: Automated 5-Part Cell Counter</li>
                    </ul>
                </div>
                <div class="test-card">
                    <h2>High Sensitivity Troponin-I Panel</h2>
                    <p>Rapid myocardial biomarker assay for cardiac injury risk evaluation.</p>
                    <ul>
                        <li>Turnaround time: 2 hours</li>
                        <li>Method: Chemiluminescent Microparticle Immunoassay</li>
                    </ul>
                </div>
            </main>
        </body>
        </html>
        """

        contact_html = """
        <html>
        <head><title>Contact Centers | Apex Diagnostics</title></head>
        <body>
            <main>
                <h1>Apex Diagnostics Facility Locations</h1>
                <p>Helpline: +1-800-555-0199 | Reception: +1-555-0123</p>
                <p>Inquiries: info@apex-diagnostics.example</p>
                <p>Working hours: Mon-Sat: 07:00 - 20:00, Sun: 08:00 - 12:00</p>
                <p>Central Pathology Lab: 450 Health Sciences Parkway, Suite 100, Cityville 90210</p>
                <a href="https://linkedin.com/company/apex-diagnostics">LinkedIn Profile</a>
            </main>
        </body>
        </html>
        """

        def mock_fetch_side(url, **kwargs):
            if "about-us" in url:
                return FetchResult(url=url, status_code=200, html=about_html)
            elif "test-menu" in url:
                return FetchResult(url=url, status_code=200, html=service_html)
            elif "contact" in url:
                return FetchResult(url=url, status_code=200, html=contact_html)
            elif "robots.txt" in url:
                return FetchResult(url=url, status_code=404, html="")
            return FetchResult(url=url, status_code=200, html=home_html)

        mock_fetch.side_effect = mock_fetch_side

        # Mock LLM returning grounded lab intelligence synthesis
        llm_response_json = {
            "website": {
                "name": "Apex Diagnostics",
                "domain": "apex-diagnostics.example",
                "url": "https://apex-diagnostics.example"
            },
            "about_us": {
                "summary": "Premier clinical testing laboratory delivering CAP and ISO accredited medical lab testing across 500+ diagnostic assays.",
                "details": "Accredited by NABL, CAP, and ISO 15189 with 15 board-certified pathologists.",
                "source_url": "https://apex-diagnostics.example/about-us"
            },
            "contact_us": {
                "phone": ["+1-800-555-0199", "+1-555-0123"],
                "email": ["info@apex-diagnostics.example"],
                "address": ["450 Health Sciences Parkway, Suite 100, Cityville 90210"],
                "working_hours": ["Mon-Sat: 07:00 - 20:00", "Sun: 08:00 - 12:00"],
                "social_links": ["https://linkedin.com/company/apex-diagnostics"],
                "source_url": "https://apex-diagnostics.example/contact"
            },
            "products_services": [
                {
                    "name": "Complete Hemogram with Platelet Count",
                    "type": "service",
                    "summary": "Quantitative automated measurement of red cells, white cells, hemoglobin, and platelets.",
                    "details": ["Turnaround time: 6 hours", "Specimen: 2ml EDTA Whole Blood"],
                    "source_url": "https://apex-diagnostics.example/test-menu"
                },
                {
                    "name": "High Sensitivity Troponin-I Panel",
                    "type": "service",
                    "summary": "Rapid myocardial biomarker assay for cardiac injury risk evaluation.",
                    "details": ["Turnaround time: 2 hours"],
                    "source_url": "https://apex-diagnostics.example/test-menu"
                }
            ],
            "facts": [
                {
                    "category": "SERVICE",
                    "field": "accreditation",
                    "value": "Accredited by NABL, CAP, and ISO 15189",
                    "source_quote": "accredited by NABL, CAP, and ISO 15189",
                    "source_url": "https://apex-diagnostics.example/about-us"
                }
            ],
            "summary_markdown": "# Apex Diagnostics Dossier\nComprehensive laboratory intelligence report."
        }
        mock_llm_generate.return_value = json.dumps(llm_response_json)

        # Create Website and Job
        website = Website.objects.create(
            domain="apex-diagnostics.example",
            root_url="https://apex-diagnostics.example"
        )
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

        # Verify Strict Canonical Top-Level Keys
        required_keys = ["website", "summary", "company_logo", "about_us", "contact_us", "products_services", "accreditations"]
        for k in required_keys:
            assert k in structured, f"Missing required top-level key: {k}"

        # 1. Company Logo Contract
        assert structured["company_logo"]["url"] == "https://apex-diagnostics.example/static/logo.png"
        assert structured["company_logo"]["alt"] == "Apex Diagnostics"
        assert structured["company_logo"]["source_page"] == "https://apex-diagnostics.example"

        # 2. About Us Contract
        assert "clinical testing laboratory" in structured["about_us"]["summary"].lower()
        assert structured["about_us"]["source_url"] == "https://apex-diagnostics.example/about-us"

        # 3. Contact Us Contract
        hq = structured["contact_us"]["headquarter"]
        assert "+1-800-555-0199" in hq["phone"]
        assert hq["email"] == "info@apex-diagnostics.example"
        assert "450 Health Sciences" in hq["address"]["full_address"]
        assert structured["contact_us"]["social_links"]["linkedin"] == "https://linkedin.com/company/apex-diagnostics"

        # 4. Products / Services Contract
        services = structured["products_services"]
        assert len(services) >= 2
        service_names = [s["name"] for s in services]
        assert "Complete Hemogram with Platelet Count" in service_names
        assert "High Sensitivity Troponin-I Panel" in service_names

        # 5. Accreditations Contract
        assert isinstance(structured["accreditations"], list)

    @patch('apps.ai.ollama.OllamaProvider.generate')
    @patch('apps.workflow.engine.SafeHttpClient.fetch')
    @patch('apps.workflow.engine.validate_url_security')
    def test_missing_data_returns_nulls_without_hallucination(self, mock_validate, mock_fetch, mock_llm_generate):
        mock_validate.return_value = ("barebones-lab.example", "93.184.216.34")

        bare_html = """
        <html>
        <body>
            <h1>Minimal Lab Page</h1>
            <p>We are a research facility with ongoing projects.</p>
        </body>
        </html>
        """
        mock_fetch.return_value = FetchResult(url="https://barebones-lab.example", status_code=200, html=bare_html)
        mock_llm_generate.return_value = json.dumps({
            "about_us": {"summary": None, "source_url": None},
            "contact_us": {"phone": [], "email": [], "address": [], "working_hours": [], "social_links": [], "source_url": None},
            "products_services": [],
            "facts": []
        })

        website = Website.objects.create(
            domain="barebones-lab.example",
            root_url="https://barebones-lab.example"
        )
        job = AnalysisJob.objects.create(
            website=website,
            objective="lab_intelligence",
            options={"fast_mode": True}
        )

        engine = WorkflowEngine(str(job.id))
        completed_job = engine.execute()

        assert completed_job.status == WorkflowState.COMPLETED
        structured = AnalysisResult.objects.get(job=completed_job).structured_data

        # Must NOT hallucinate missing data
        assert structured["company_logo"] == {"url": None, "base64": None, "alt": None, "source_page": None}

        assert structured["contact_us"]["headquarter"]["phone"] == []
        assert structured["contact_us"]["headquarter"]["email"] == ""
        assert structured["contact_us"]["headquarter"]["address"]["full_address"] == ""
        assert structured["products_services"] == []
        assert structured["accreditations"] == []

    @patch('apps.ai.ollama.OllamaProvider.generate')
    @patch('apps.workflow.engine.SafeHttpClient.fetch')
    @patch('apps.workflow.engine.validate_url_security')
    def test_llm_null_contact_fields_handled_gracefully(self, mock_validate, mock_fetch, mock_llm_generate):
        mock_validate.return_value = ("null-fields-lab.example", "93.184.216.34")

        bare_html = "<html><body><h1>Minimal</h1><p>Minimal content.</p></body></html>"
        mock_fetch.return_value = FetchResult(url="https://null-fields-lab.example", status_code=200, html=bare_html)
        mock_llm_generate.return_value = json.dumps({
            "about_us": None,
            "contact_us": {
                "phone": None,
                "email": None,
                "address": None,
                "working_hours": None,
                "social_links": None,
                "source_url": None
            },
            "products_services": None,
            "facts": None
        })

        website = Website.objects.create(
            domain="null-fields-lab.example",
            root_url="https://null-fields-lab.example"
        )
        job = AnalysisJob.objects.create(
            website=website,
            objective="lab_intelligence",
            options={"fast_mode": True}
        )

        engine = WorkflowEngine(str(job.id))
        completed_job = engine.execute()

        assert completed_job.status == WorkflowState.COMPLETED
        structured = AnalysisResult.objects.get(job=completed_job).structured_data
        assert structured["contact_us"]["headquarter"]["phone"] == []
        assert structured["contact_us"]["headquarter"]["email"] == ""
        assert structured["contact_us"]["headquarter"]["address"]["full_address"] == ""
        assert isinstance(structured["contact_us"]["social_links"], dict)
        assert structured["contact_us"]["social_links"]["twitter"] == ""



