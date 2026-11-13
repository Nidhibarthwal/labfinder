import hashlib
import json
import logging
from typing import Optional, Dict, Any, List
from django.db import transaction
from django.utils import timezone

from apps.analysis.models import (
    Website, AnalysisJob, Page, PageLink, PageAnalysis,
    Evidence, Fact, AnalysisResult, WorkflowState, PageType
)
from apps.crawler.security import (
    validate_url_security, SSRFBlockedException, InvalidURLException, DNSResolutionException
)
from apps.crawler.normalizer import normalize_url, extract_domain, is_same_domain
from apps.crawler.http_client import SafeHttpClient, FetchResult
from apps.crawler.robots_sitemap import RobotsHandler, SitemapHandler
from apps.crawler.discovery import LinkDiscovery, DiscoveredLink
from apps.extractor.cleaner import ContentExtractor, ExtractedContent
from apps.classifier.classifier import PageClassifier
from apps.ai.gateway import ModelRouter, parse_json_safely
from apps.ai.ollama import get_default_llm_provider
from apps.ai.prompts import (
    SYSTEM_FACT_EXTRACTION, SYSTEM_FINAL_SYNTHESIS, SYSTEM_PAGE_CLASSIFICATION,
    SYSTEM_UNIFIED_ANALYSIS, SYSTEM_LAB_INTELLIGENCE,
    format_extraction_prompt, format_classification_prompt, format_synthesis_prompt,
    format_unified_analysis_prompt, format_lab_intelligence_prompt
)
from apps.extractor.deterministic import (
    extract_deterministic_facts, extract_contact_bundle, extract_social_links, format_social_links_dict
)
from apps.analysis.schema import validate_and_normalize_structured_data


from apps.extractor.logo import LogoExtractor
from apps.extractor.sections import ProductServiceExtractor
from apps.evidence.validator import ClaimValidator
from apps.evidence.conflicts import ConflictDetector
from .budgets import ExecutionBudget
from .agent import AgentPlanner, CandidatePage
from .config import TargetExtractionConfig

logger = logging.getLogger(__name__)

class WorkflowEngine:
    """
    Stateful workflow orchestrator executing the bounded, evidence-grounded
    Website Intelligence pipeline.
    """

    def __init__(self, job_id: str):
        self.job = AnalysisJob.objects.select_related('website').get(id=job_id)
        self.website = self.job.website
        self.target_config = TargetExtractionConfig.from_job(self.job)
        self.budget = ExecutionBudget(max_analysed_pages=self.target_config.max_pages)
        self.http_client = SafeHttpClient()
        self.extractor = ContentExtractor()
        self.classifier = PageClassifier()
        self.validator = ClaimValidator()
        self.conflict_detector = ConflictDetector()
        self.model_router = ModelRouter()
        self.llm_provider = get_default_llm_provider()
        self.planner = AgentPlanner(objective=self.job.objective, target_config=self.target_config)
        self.logo_extractor = LogoExtractor()
        self.section_extractor = ProductServiceExtractor()

    def transition(self, new_state: WorkflowState):
        """Updates and persists workflow state."""
        self.job.status = new_state
        self.job.budget_usage = self.budget.to_dict()
        self.job.save(update_fields=['status', 'budget_usage', 'updated_at'])
        logger.info(f"Job {self.job.id} state -> {new_state}")

    def fail(self, error_code: str, error_detail: str):
        """Marks workflow as failed with controlled error details."""
        self.job.status = WorkflowState.FAILED
        self.job.error_code = error_code
        self.job.error_detail = error_detail
        self.job.budget_usage = self.budget.to_dict()
        self.job.save(update_fields=['status', 'error_code', 'error_detail', 'budget_usage', 'updated_at'])
        logger.error(f"Job {self.job.id} FAILED [{error_code}]: {error_detail}")

    def execute(self) -> AnalysisJob:
        """Runs the complete analysis workflow from start to finish."""
        try:
            # Record effective target configuration for transparency and auditability
            opts = dict(self.job.options or {})
            opts['effective_target_config'] = self.target_config.to_dict()
            self.job.options = opts
            self.job.save(update_fields=['options'])

            # 1. State: VALIDATING_URL
            self.transition(WorkflowState.VALIDATING_URL)
            root_url = self.website.root_url
            try:
                validate_url_security(root_url)
            except SSRFBlockedException as e:
                self.fail('SSRF_BLOCKED', str(e))
                return self.job
            except (InvalidURLException, DNSResolutionException) as e:
                self.fail('INVALID_URL', str(e))
                return self.job

            # 2. State: DISCOVERING
            self.transition(WorkflowState.DISCOVERING)
            robots_handler = RobotsHandler(root_url, http_client=self.http_client)
            robots_handler.load()

            # Fetch homepage
            self.budget.http_requests += 1
            home_fetch = self.http_client.fetch(root_url)
            if not home_fetch.is_success:
                self.fail(
                    home_fetch.error_code or 'WEBSITE_UNAVAILABLE',
                    home_fetch.error_message or f"HTTP status {home_fetch.status_code}"
                )
                return self.job

            # Harvest links from homepage
            link_discovery = LinkDiscovery(root_url)
            discovered_links = link_discovery.discover_links(home_fetch.html, root_url)

            # Discover URLs from sitemaps
            sitemap_handler = SitemapHandler(root_url, http_client=self.http_client)
            sitemap_urls = sitemap_handler.discover_urls(robots_handler.sitemaps, max_urls=30)

            # Build candidate list
            candidate_map: Dict[str, CandidatePage] = {}

            # Add homepage itself as candidate
            home_norm = normalize_url(root_url)
            candidate_map[home_norm] = CandidatePage(
                url=root_url,
                normalized_url=home_norm,
                page_type='ABOUT', # Homepage often contains primary about facts
                confidence=0.8,
                location='nav',
                anchor_text='Home'
            )

            # Process discovered links
            for link in discovered_links:
                if link.normalized_url not in candidate_map:
                    p_type, conf = self.classifier.classify_deterministic(
                        url=link.normalized_url,
                        anchor_text=link.anchor_text,
                        title=link.title_attr,
                    )
                    candidate_map[link.normalized_url] = CandidatePage(
                        url=link.url,
                        normalized_url=link.normalized_url,
                        page_type=p_type,
                        confidence=conf,
                        location=link.location,
                        anchor_text=link.anchor_text
                    )

            # Process sitemap URLs
            for sm_url in sitemap_urls:
                if sm_url not in candidate_map:
                    p_type, conf = self.classifier.classify_deterministic(url=sm_url)
                    candidate_map[sm_url] = CandidatePage(
                        url=sm_url,
                        normalized_url=sm_url,
                        page_type=p_type,
                        confidence=conf,
                        location='body'
                    )

            self.budget.discovered_pages = len(candidate_map)

            # 3. State: PLANNING
            self.transition(WorkflowState.PLANNING)
            candidates = list(candidate_map.values())
            attempted_urls: set = set()
            analysed_urls: set = set()
            collected_categories: set = set()
            all_verified_facts: List[Dict[str, Any]] = []
            crawled_pages: List[Dict[str, Any]] = []
            detected_logo: Optional[Dict[str, Any]] = None
            extracted_sections: List[Dict[str, Any]] = []
            contact_bundles: List[Dict[str, Any]] = []

            # Immediate deterministic logo extraction from homepage HTML
            if home_fetch and home_fetch.html:
                init_logo = self.logo_extractor.extract_logo(home_fetch.html, root_url)
                if init_logo and init_logo.get('url'):
                    detected_logo = init_logo

            # Fast Unified Mode: enabled by default for production sub-minute speed
            fast_mode = self.job.options.get('fast_mode', True)

            # 4. Agent Execution Loop
            while not self.budget.is_exhausted():
                self.budget.iterations += 1

                # Agent decides next action
                decision, next_candidate = self.planner.select_next_action(
                    candidates=candidates,
                    analysed_urls=analysed_urls,
                    collected_categories=collected_categories,
                    budget_exhausted=self.budget.is_exhausted(),
                    attempted_urls=attempted_urls,
                )

                if decision == 'FINISH' or not next_candidate:
                    break

                target_url = next_candidate.normalized_url
                attempted_urls.add(target_url)

                # Check robots permission
                if not robots_handler.can_fetch(target_url):
                    logger.info(f"Skipping {target_url}: Disallowed by robots.txt")
                    continue

                # FETCHING
                self.transition(WorkflowState.FETCHING)
                if not self.budget.can_make_http_request():
                    break

                # Check if we already have the raw page in memory (homepage)
                if target_url == home_norm:
                    fetch_res = home_fetch
                else:
                    self.budget.http_requests += 1
                    fetch_res = self.http_client.fetch(target_url)

                if not fetch_res.is_success or not fetch_res.html:
                    logger.warning(f"Failed to fetch candidate {target_url}: {fetch_res.error_code}")
                    continue

                # EXTRACTING
                self.transition(WorkflowState.EXTRACTING)
                content_hash = hashlib.sha256(fetch_res.html.encode('utf-8')).hexdigest()
                extracted = self.extractor.extract(fetch_res.html)

                if extracted.quality_score < 0.1 and extracted.text_length < 80:
                    logger.info(f"Skipping low quality content on {target_url}")
                    continue

                # Fallback logo extraction from page HTML if not found yet
                if not detected_logo:
                    page_logo = self.logo_extractor.extract_logo(fetch_res.html, target_url)
                    if page_logo and page_logo.get('url'):
                        detected_logo = page_logo

                # Extract individual products/services/tests sections from HTML
                page_sections = self.section_extractor.extract_from_html(fetch_res.html, target_url)
                if page_sections:
                    extracted_sections.extend(page_sections)

                # Collect structured contact bundle for this page (from text and raw HTML)
                cb = extract_contact_bundle(extracted.clean_text, target_url, html=fetch_res.html)
                contact_bundles.append(cb)

                # CLASSIFYING
                self.transition(WorkflowState.CLASSIFYING)
                final_page_type, confidence = self.classifier.classify_deterministic(
                    url=target_url,
                    anchor_text=next_candidate.anchor_text,
                    title=extracted.title,
                    h1=" ".join(extracted.headings.get('h1', []))
                )

                # Persist or update Page in DB
                page_obj, _ = Page.objects.update_or_create(
                    website=self.website,
                    normalized_url=target_url,
                    defaults={
                        'url': target_url,
                        'page_type': final_page_type,
                        'title': extracted.title[:500],
                        'http_status': fetch_res.status_code,
                        'content_hash': content_hash,
                        'clean_text': extracted.clean_text,
                        'quality_score': extracted.quality_score,
                        'fetch_method': 'HTTP',
                    }
                )

                # Instant Deterministic Fact Extraction (contacts, phones, social links)
                det_facts = extract_deterministic_facts(extracted.clean_text, target_url)
                for df in det_facts:
                    v, s, e = self.validator.verify_quote(extracted.clean_text, df['source_quote'])
                    if v:
                        df['char_start'] = s
                        df['char_end'] = e
                        all_verified_facts.append(df)
                        collected_categories.add(df.get('category', 'OTHER'))
                        with transaction.atomic():
                            ev = Evidence.objects.create(
                                page=page_obj,
                                quote=df['source_quote'],
                                char_start=s,
                                char_end=e,
                                verified=True
                            )
                            Fact.objects.create(
                                job=self.job,
                                evidence=ev,
                                category=df.get('category', 'OTHER'),
                                field=df.get('field', 'contact'),
                                value=df.get('value', ''),
                                confidence=1.0
                            )

                crawled_pages.append({
                    'url': target_url,
                    'page_type': final_page_type,
                    'title': extracted.title,
                    'clean_text': extracted.clean_text,
                    'page_obj': page_obj,
                })

                analysed_urls.add(target_url)
                self.budget.analysed_pages += 1

                # If NOT fast_mode, execute per-page iterative LLM extraction
                if not fast_mode:
                    self.transition(WorkflowState.ANALYSING)
                    raw_facts = []
                    page_summary = ""
                    model_used = self.model_router.get_model_for_task('extraction')

                    if self.budget.can_make_llm_call() and extracted.clean_text:
                        self.budget.llm_calls += 1
                        extraction_prompt = format_extraction_prompt(
                            page_url=target_url,
                            page_title=extracted.title,
                            clean_text=extracted.clean_text,
                            page_type=final_page_type
                        )

                        try:
                            llm_out = self.llm_provider.generate(
                                prompt=extraction_prompt,
                                system_prompt=SYSTEM_FACT_EXTRACTION,
                                model=model_used,
                                json_mode=True,
                                temperature=0.0,
                                num_predict=150
                            )
                            parsed_out = parse_json_safely(llm_out)
                            page_summary = parsed_out.get('page_summary', '')
                            raw_facts = parsed_out.get('facts', [])
                        except Exception as e:
                            logger.warning(f"LLM extraction failed for {target_url}: {e}")

                    # VALIDATING
                    self.transition(WorkflowState.VALIDATING)
                    verified_facts = self.validator.validate_and_filter_facts(
                        clean_text=extracted.clean_text,
                        raw_facts=raw_facts
                    )

                    with transaction.atomic():
                        page_analysis = PageAnalysis.objects.create(
                            job=self.job,
                            page=page_obj,
                            summary=page_summary,
                            raw_output={'facts_count': len(verified_facts)},
                            model_used=model_used
                        )

                        for vf in verified_facts:
                            vf['source_url'] = target_url
                            all_verified_facts.append(vf)
                            collected_categories.add(vf.get('category', 'OTHER'))

                            ev = Evidence.objects.create(
                                page=page_obj,
                                quote=vf.get('source_quote', ''),
                                char_start=vf.get('char_start', -1),
                                char_end=vf.get('char_end', -1),
                                verified=True
                            )

                            Fact.objects.create(
                                job=self.job,
                                evidence=ev,
                                category=vf.get('category', 'OTHER'),
                                field=vf.get('field', 'general'),
                                value=vf.get('value', ''),
                                confidence=1.0
                            )

            # FAST UNIFIED ANALYSIS PASS (Single LLM Call for All Pages)
            synthesis_model = self.model_router.get_model_for_task('synthesis')
            final_structured = {}
            summary_markdown = ""
            is_lab_mode = (self.job.objective == 'lab_intelligence')

            if is_lab_mode:
                self.transition(WorkflowState.ANALYSING)
                parsed_out = {}
                if self.budget.can_make_llm_call() and crawled_pages:
                    self.budget.llm_calls += 1
                    lab_prompt = format_lab_intelligence_prompt(
                        domain=self.website.domain,
                        pages_data=crawled_pages,
                        structured_sections=extracted_sections
                    )
                    try:
                        llm_out = self.llm_provider.generate(
                            prompt=lab_prompt,
                            system_prompt=SYSTEM_LAB_INTELLIGENCE,
                            model=synthesis_model,
                            json_mode=True,
                            temperature=0.0,
                            num_predict=380
                        )
                        parsed_out = parse_json_safely(llm_out)
                    except Exception as e:
                        logger.warning(f"Lab intelligence LLM pass failed: {e}")
                        parsed_out = {}

                self.transition(WorkflowState.VALIDATING)
                # 1. Company Logo
                final_logo = detected_logo or {
                    "url": None,
                    "base64": None,
                    "alt": None,
                    "source_page": None
                }
                if final_logo.get('url') and not final_logo.get('base64'):
                    final_logo['base64'] = self.logo_extractor.url_to_base64(
                        final_logo['url'],
                        http_client=self.http_client
                    )


                # 2. About Us & Top Summary
                top_summary = parsed_out.get('summary') if isinstance(parsed_out.get('summary'), str) else ""

                llm_about = parsed_out.get('about_us') if isinstance(parsed_out.get('about_us'), dict) else {}
                about_summary = llm_about.get('summary') if isinstance(llm_about.get('summary'), str) else ""
                about_source = llm_about.get('source_url')

                about_page = next((p for p in crawled_pages if p['page_type'] == 'ABOUT' and p['url'] != home_norm), None)
                if not about_page:
                    about_page = next((p for p in crawled_pages if p['page_type'] == 'ABOUT'), None)
                if not about_page and crawled_pages:
                    about_page = crawled_pages[0]

                if not about_source and about_page:
                    about_source = about_page['url']

                import re as _re
                def _is_invalid_summary(s: str, title: str = "") -> bool:
                    if not s or not s.strip():
                        return True
                    s_clean = s.strip()
                    if s_clean.startswith("About Us -") or s_clean.startswith("About Us |") or s_clean.startswith("About Us:") or s_clean == "About Us":
                        return True
                    if title and s_clean.lower() == title.lower():
                        return True
                    if len(s_clean.split()) < 12:
                        return True
                    return False

                about_title = about_page.get('title', '') if about_page else ''
                if _is_invalid_summary(about_summary, about_title):
                    about_summary = ""

                if _is_invalid_summary(top_summary):
                    top_summary = ""

                if about_page and about_page.get('clean_text'):
                    raw_lines = about_page['clean_text'].split('\n')
                    prose_sentences = []
                    for line in raw_lines:
                        line_str = line.strip()
                        if len(line_str) > 30 and not line_str.startswith(('Home', 'Contact', 'Services', 'Copyright', 'All Rights Reserved')):
                            for s in _re.split(r'(?<=[.!?])\s+', line_str):
                                s_tr = s.strip()
                                if len(s_tr) > 20:
                                    prose_sentences.append(s_tr)

                    if prose_sentences:
                        if not about_summary:
                            about_summary = " ".join(prose_sentences[:5])
                        if not top_summary:
                            top_summary = " ".join(prose_sentences[:7])

                final_about = {
                    "summary": about_summary if about_summary else (top_summary[:300] if top_summary else ""),
                    "source_url": about_source if about_source else (about_page['url'] if about_page else self.website.root_url)
                }



                # 3. Contact Us
                merged_phones = []
                merged_emails = []
                merged_addresses = []
                merged_socials = []
                contact_source_url = None

                contact_page = next((p for p in crawled_pages if p['page_type'] == 'CONTACT'), None)
                if contact_page:
                    contact_source_url = contact_page['url']

                def _safe_list(val):
                    if val is None:
                        return []
                    if isinstance(val, list):
                        return val
                    if isinstance(val, (str, int, float)):
                        return [str(val)]
                    return []

                for cb in contact_bundles:
                    for p in _safe_list(cb.get('phone')):
                        if p not in merged_phones:
                            merged_phones.append(p)
                    for e in _safe_list(cb.get('email')):
                        if e not in merged_emails:
                            merged_emails.append(e)
                    for a in _safe_list(cb.get('address')):
                        if a not in merged_addresses:
                            merged_addresses.append(a)
                    for s in _safe_list(cb.get('social_links')):
                        if s not in merged_socials:
                            merged_socials.append(s)
                    if not contact_source_url and cb.get('source_url'):
                        contact_source_url = cb.get('source_url')

                llm_contact = parsed_out.get('contact_us') if isinstance(parsed_out.get('contact_us'), dict) else {}
                llm_hq = llm_contact.get('headquarter') if isinstance(llm_contact.get('headquarter'), dict) else llm_contact

                for p in _safe_list(llm_hq.get('phone')):
                    p_str = str(p).strip()
                    import re as _re
                    digits = _re.sub(r'\D', '', p_str)
                    if 7 <= len(digits) <= 15 and p_str not in merged_phones:
                        merged_phones.append(p_str)

                for e in _safe_list(llm_hq.get('email')):
                    e_str = str(e).strip()
                    import re as _re
                    if _re.search(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', e_str) and e_str not in merged_emails:
                        merged_emails.append(e_str)

                llm_addr_val = llm_hq.get('address')
                if isinstance(llm_addr_val, list):
                    for a in llm_addr_val:
                        a_str = str(a).strip() if isinstance(a, (str, dict)) else ""
                        if 12 <= len(a_str) <= 250 and a_str not in merged_addresses:
                            merged_addresses.append(a_str)
                elif isinstance(llm_addr_val, (str, dict)):
                    a_str = str(llm_addr_val).strip()
                    if 12 <= len(a_str) <= 250 and a_str not in merged_addresses:
                        merged_addresses.append(a_str)

                for s in _safe_list(llm_contact.get('social_links')):
                    s_str = str(s).strip()
                    for cleaned_s in extract_social_links(clean_text=s_str):
                        if cleaned_s not in merged_socials:
                            merged_socials.append(cleaned_s)

                if not contact_source_url and llm_contact.get('source_url'):
                    contact_source_url = llm_contact.get('source_url')

                final_socials = format_social_links_dict(merged_socials)

                hq_primary_addr = merged_addresses[0] if merged_addresses else ""
                hq_email_single = merged_emails[0] if merged_emails else ""

                final_headquarter = {
                    "phone": merged_phones,
                    "email": hq_email_single,
                    "address": hq_primary_addr,
                    "source_url": contact_source_url or (self.website.root_url + "contact")
                }

                branches_dict = llm_contact.get('branches') if isinstance(llm_contact.get('branches'), dict) else {}

                final_contact = {
                    "headquarter": final_headquarter,
                    "branches": branches_dict,
                    "social_links": final_socials
                }


                # 4. Products / Services
                raw_items = []
                if extracted_sections:
                    raw_items.extend(extracted_sections)

                llm_items = parsed_out.get('products_services', [])
                if isinstance(llm_items, list):
                    for it in llm_items:
                        if isinstance(it, dict) and it.get('name'):
                            stype = it.get('type')
                            if stype not in ['product', 'service', 'unknown']:
                                stype = 'service'
                            raw_items.append({
                                'name': it.get('name'),
                                'type': stype,
                                'summary': it.get('summary'),
                                'source_url': it.get('source_url') or self.website.root_url
                            })

                final_products_services = ProductServiceExtractor.deduplicate(raw_items)

                # Enrich products_services with AI-driven or real analyzed prose from crawled_pages
                import re as _re
                from apps.ai.prompts import SYSTEM_SERVICE_SUMMARIZATION, format_service_summary_prompt
                for item in final_products_services:
                    item_name = str(item.get('name', '')).strip()
                    item_url = str(item.get('source_url', '')).strip()
                    curr_summary = str(item.get('summary', '')).strip()

                    # Only enrich if summary is missing, short, or generic
                    if not curr_summary or len(curr_summary) < 25 or curr_summary.startswith("Comprehensive testing"):
                        matched_page = next((p for p in crawled_pages if p['url'] == item_url), None)
                        if not matched_page and item_name:
                            norm_name = _re.sub(r'[^a-z0-9]', '', item_name.lower())
                            matched_page = next((p for p in crawled_pages if norm_name in _re.sub(r'[^a-z0-9]', '', p['url'].lower()) or (p.get('title') and norm_name in _re.sub(r'[^a-z0-9]', '', p['title'].lower()))), None)

                        if matched_page and matched_page.get('clean_text'):
                            ai_generated = False
                            if self.budget.can_make_llm_call() and len(matched_page['clean_text']) > 50:
                                self.budget.llm_calls += 1
                                try:
                                    service_prompt = format_service_summary_prompt(item_name, matched_page['clean_text'])
                                    ai_out = self.llm_provider.generate(
                                        prompt=service_prompt,
                                        system_prompt=SYSTEM_SERVICE_SUMMARIZATION,
                                        model=synthesis_model,
                                        json_mode=False,
                                        temperature=0.0,
                                        num_predict=120
                                    )
                                    if ai_out and len(ai_out.strip()) > 25:
                                        item['summary'] = ai_out.strip()
                                        ai_generated = True
                                except Exception as err:
                                    logger.warning(f"AI service summarization failed for {item_name}: {err}")

                            if not ai_generated:
                                raw_lines = matched_page['clean_text'].split('\n')
                                prose_sentences = []
                                for line in raw_lines:
                                    line_str = line.strip()
                                    if len(line_str) > 30 and not line_str.startswith(('Home', 'Contact', 'Services', 'Copyright', 'All Rights Reserved', 'Get Your', 'Looking for', 'Submit Your', 'A Certified', 'ISO:', 'NABL', 'Electrical |')):
                                        for s in _re.split(r'(?<=[.!?])\s+', line_str):
                                            s_tr = s.strip()
                                            if len(s_tr) > 25 and not _re.match(r'^(?:Home|Contact|Services|Copyright|All Rights|Name|Phone|Email|Submit|Send|Search|A Certified|ISO|NABL|Electrical)\b', s_tr, _re.I):
                                                prose_sentences.append(s_tr)

                                if prose_sentences:
                                    real_summary = " ".join(prose_sentences[:3]).strip()
                                    if real_summary:
                                        item['summary'] = real_summary[:500]
                                        if not item.get('source_url') or item['source_url'] == self.website.root_url:
                                            item['source_url'] = matched_page['url']

                # 5. Accreditations
                llm_acc = parsed_out.get('accreditations')
                acc_list = []
                if isinstance(llm_acc, list):
                    acc_list = llm_acc

                if not acc_list:
                    all_text = " ".join([p.get('clean_text', '') for p in crawled_pages])
                    if "NABL" in all_text:
                        acc_list.append({"name": "NABL Accredited", "full_name": "National Accreditation Board for Testing and Calibration Laboratories", "accreditation_type": "Laboratory Accreditation", "status": "Active"})
                    if "BIS" in all_text:
                        acc_list.append({"name": "BIS Approved", "full_name": "Bureau of Indian Standards", "accreditation_type": "Regulatory Approval", "status": "Active"})
                    if "ISO 9001" in all_text or "9001:2015" in all_text:
                        acc_list.append({"name": "ISO 9001:2015", "full_name": "Quality Management System", "accreditation_type": "Management System", "status": "Active"})
                    if "ISO 14001" in all_text:
                        acc_list.append({"name": "ISO 14001:2015", "full_name": "Environmental Management System", "accreditation_type": "Management System", "status": "Active"})
                    if "ISO 45001" in all_text:
                        acc_list.append({"name": "ISO 45001:2018", "full_name": "Occupational Health and Safety Management System", "accreditation_type": "Management System", "status": "Active"})
                    if "NAAC" in all_text:
                        acc_list.append({"name": "NAAC", "full_name": "National Assessment and Accreditation Council", "accreditation_type": "Institutional", "status": "Active"})

                # 6. Evidence Grounding for Raw Facts
                raw_facts = parsed_out.get('facts', [])
                if isinstance(raw_facts, list):
                    for rf in raw_facts:
                        fact_quote = (rf.get('source_quote', '') or rf.get('value', '')).strip()
                        if not fact_quote or len(fact_quote) < 4:
                            continue

                        matched_page = None
                        matched_start, matched_end = -1, -1
                        claimed_url = rf.get('source_url', '')
                        target_p = next((p for p in crawled_pages if p['url'] == claimed_url), None)
                        if target_p:
                            v, s, e = self.validator.verify_quote(target_p['clean_text'], fact_quote)
                            if v:
                                matched_page = target_p
                                matched_start, matched_end = s, e

                        if not matched_page:
                            for p in crawled_pages:
                                v, s, e = self.validator.verify_quote(p['clean_text'], fact_quote)
                                if v:
                                    matched_page = p
                                    matched_start, matched_end = s, e
                                    break

                        if matched_page:
                            rf['source_url'] = matched_page['url']
                            rf['char_start'] = matched_start
                            rf['char_end'] = matched_end
                            all_verified_facts.append(rf)
                            collected_categories.add(rf.get('category', 'SERVICE'))

                            with transaction.atomic():
                                ev = Evidence.objects.create(
                                    page=matched_page['page_obj'],
                                    quote=fact_quote,
                                    char_start=matched_start,
                                    char_end=matched_end,
                                    verified=True
                                )
                                Fact.objects.create(
                                    job=self.job,
                                    evidence=ev,
                                    category=rf.get('category', 'SERVICE'),
                                    field=rf.get('field', 'service'),
                                    value=rf.get('value', ''),
                                    confidence=1.0
                                )

                # Save PageAnalysis records
                for p in crawled_pages:
                    p_facts = [f for f in all_verified_facts if f.get('source_url') == p['url']]
                    PageAnalysis.objects.create(
                        job=self.job,
                        page=p['page_obj'],
                        summary=final_about.get('summary') or f"Analysis for {p['url']}",
                        raw_output={'facts_count': len(p_facts)},
                        model_used=synthesis_model
                    )

                # Assemble strict Requirement schema
                final_structured = {
                    "website": self.website.root_url,
                    "summary": top_summary,
                    "company_logo": final_logo,
                    "about_us": final_about,
                    "contact_us": final_contact,
                    "products_services": final_products_services,
                    "accreditations": acc_list,
                }

                summary_markdown = parsed_out.get('summary_markdown', '') or self._generate_lab_markdown_report(final_structured)


            elif fast_mode and crawled_pages:
                self.transition(WorkflowState.ANALYSING)
                if self.budget.can_make_llm_call():
                    self.budget.llm_calls += 1
                    unified_prompt = format_unified_analysis_prompt(
                        domain=self.website.domain,
                        pages_data=crawled_pages,
                        target_page_types=self.target_config.target_page_types
                    )
                    try:
                        llm_out = self.llm_provider.generate(
                            prompt=unified_prompt,
                            system_prompt=SYSTEM_UNIFIED_ANALYSIS,
                            model=synthesis_model,
                            json_mode=True,
                            temperature=0.0,
                            num_predict=260
                        )
                        parsed_out = parse_json_safely(llm_out)
                        final_structured = parsed_out
                        summary_markdown = parsed_out.get('summary_markdown', '')
                        raw_facts = parsed_out.get('facts', [])
                    except Exception as e:
                        logger.warning(f"Unified LLM pass failed: {e}")
                        parsed_out = {}
                        raw_facts = []

                    self.transition(WorkflowState.VALIDATING)
                    # Ground facts against actual crawled page texts
                    for rf in raw_facts:
                        fact_quote = (rf.get('source_quote', '') or rf.get('value', '')).strip()
                        if not fact_quote or len(fact_quote) < 4:
                            continue

                        matched_page = None
                        matched_start, matched_end = -1, -1

                        # Test preferred target page first
                        claimed_url = rf.get('source_url', '')
                        target_p = next((p for p in crawled_pages if p['url'] == claimed_url), None)
                        if target_p:
                            v, s, e = self.validator.verify_quote(target_p['clean_text'], fact_quote)
                            if v:
                                matched_page = target_p
                                matched_start, matched_end = s, e

                        # If not matched on claimed url, search across other crawled pages
                        if not matched_page:
                            for p in crawled_pages:
                                v, s, e = self.validator.verify_quote(p['clean_text'], fact_quote)
                                if v:
                                    matched_page = p
                                    matched_start, matched_end = s, e
                                    break

                        if matched_page:
                            rf['source_url'] = matched_page['url']
                            rf['char_start'] = matched_start
                            rf['char_end'] = matched_end
                            all_verified_facts.append(rf)
                            collected_categories.add(rf.get('category', 'OTHER'))

                            with transaction.atomic():
                                ev = Evidence.objects.create(
                                    page=matched_page['page_obj'],
                                    quote=fact_quote,
                                    char_start=matched_start,
                                    char_end=matched_end,
                                    verified=True
                                )
                                Fact.objects.create(
                                    job=self.job,
                                    evidence=ev,
                                    category=rf.get('category', 'OTHER'),
                                    field=rf.get('field', 'general'),
                                    value=rf.get('value', ''),
                                    confidence=1.0
                                )

                    # Save PageAnalysis records for transparency
                    overview_summary = parsed_out.get('company_overview', '')
                    for p in crawled_pages:
                        p_facts = [f for f in all_verified_facts if f.get('source_url') == p['url']]
                        PageAnalysis.objects.create(
                            job=self.job,
                            page=p['page_obj'],
                            summary=overview_summary,
                            raw_output={'facts_count': len(p_facts)},
                            model_used=synthesis_model
                        )

            # 5. State: AGGREGATING
            self.transition(WorkflowState.AGGREGATING)
            conflicts = self.conflict_detector.detect_conflicts(all_verified_facts)

            # 6. State: FINAL_VALIDATION & SYNTHESIS
            self.transition(WorkflowState.FINAL_VALIDATION)

            # If not fast_mode and not is_lab_mode, synthesize from aggregated facts
            if not fast_mode and not is_lab_mode and self.budget.can_make_llm_call() and all_verified_facts:
                self.budget.llm_calls += 1
                synthesis_prompt = format_synthesis_prompt(
                    domain=self.website.domain,
                    validated_facts=all_verified_facts,
                    target_page_types=self.target_config.target_page_types
                )
                try:
                    synthesis_raw = self.llm_provider.generate(
                        prompt=synthesis_prompt,
                        system_prompt=SYSTEM_FINAL_SYNTHESIS,
                        model=synthesis_model,
                        json_mode=True,
                        temperature=0.1,
                        num_predict=350
                    )
                    final_structured = parse_json_safely(synthesis_raw)
                    summary_markdown = final_structured.get('summary_markdown', '')
                except Exception as e:
                    logger.warning(f"Synthesis LLM call failed: {e}. Falling back to deterministic assembly.")

            # Fallback deterministic synthesis if markdown is empty
            if not summary_markdown:
                if is_lab_mode:
                    summary_markdown = self._generate_lab_markdown_report(final_structured)
                else:
                    summary_markdown = self._generate_deterministic_synthesis(all_verified_facts, conflicts)

            # Ensure conflicts reflect verified contradictions (prevent LLM hallucinations in conflicts)
            if not conflicts and isinstance(final_structured, dict) and 'conflicts' in final_structured:
                final_structured['conflicts'] = []

            sources_list = list(set([p['url'] for p in crawled_pages] + [f.get('source_url', '') for f in all_verified_facts if f.get('source_url')]))

            # Always run canonical schema validation and normalization
            final_structured = validate_and_normalize_structured_data(
                final_structured,
                root_url=self.website.root_url,
                objective=self.job.objective,
                pages_analyzed=len(crawled_pages)
            )

            # Persist Final AnalysisResult
            AnalysisResult.objects.update_or_create(
                job=self.job,
                defaults={
                    'summary_markdown': summary_markdown,
                    'structured_data': final_structured,
                    'conflicts': conflicts,
                    'missing_fields': [],
                    'sources': sources_list,
                }
            )



            # 7. State: COMPLETED
            self.transition(WorkflowState.COMPLETED)
            return self.job

        except Exception as e:
            logger.exception(f"Unexpected fatal error in workflow engine for job {self.job.id}: {e}")
            self.fail('INTERNAL_ERROR', str(e))
            return self.job

    def _generate_deterministic_synthesis(
        self, facts: List[Dict[str, Any]], conflicts: List[Dict[str, Any]]
    ) -> str:
        """Deterministic fallback synthesis guaranteeing zero hallucination."""
        lines = [f"# Intelligence Summary for {self.website.domain}\n"]
        
        # Group by category
        by_cat: Dict[str, List[Dict[str, Any]]] = {}
        for f in facts:
            cat = f.get('category', 'OTHER')
            if cat not in by_cat:
                by_cat[cat] = []
            by_cat[cat].append(f)

        for cat, fact_items in by_cat.items():
            lines.append(f"## {cat.title()}")
            for item in fact_items:
                quote = item.get('source_quote', '')
                quote_str = f" *(Quote: \"{quote}\")*" if quote else ""
                lines.append(f"- **{item.get('field', 'Fact')}:** {item.get('value', '')}{quote_str}")
            lines.append("")

        if conflicts:
            lines.append("## Identified Contradictions & Conflicts")
            for c in conflicts:
                lines.append(f"- **{c.get('field')}:** {c.get('description')}")
            lines.append("")

        return "\n".join(lines)

    def _generate_lab_markdown_report(self, data: Dict[str, Any]) -> str:
        """Generates a professional markdown report for laboratory intelligence."""
        lines = [f"# Laboratory Intelligence Dossier: {self.website.domain}\n"]

        # Logo & Basic Info
        logo = data.get('company_logo') or {}
        logo_src = logo.get('base64') or logo.get('url')
        if logo_src:
            lines.append(f"![Company Logo]({logo_src})\n")


        # About Us
        about = data.get('about_us') or {}
        lines.append("## About the Laboratory")
        if about.get('summary'):
            lines.append(f"{about['summary']}\n")
        if about.get('details'):
            lines.append(f"**Key Details & Accreditations:** {about['details']}\n")
        if about.get('source_url'):
            lines.append(f"*Source: {about['source_url']}*\n")
        if not about.get('summary') and not about.get('details'):
            lines.append("No explicit About Us information was identified on analyzed pages.\n")

        # Diagnostic Tests & Services
        services = data.get('products_services') or []
        lines.append(f"## Diagnostic Tests, Services & Health Packages ({len(services)})")
        if services:
            for item in services:
                name = item.get('name', 'Unnamed Service')
                stype = str(item.get('type', 'service')).title()
                summary = item.get('summary', '')
                details = item.get('details', [])
                source = item.get('source_url', '')

                lines.append(f"### {name} `[{stype}]`")
                if summary:
                    lines.append(f"{summary}")
                if details:
                    for d in details:
                        lines.append(f"- {d}")
                if source:
                    lines.append(f"*Source: {source}*")
                lines.append("")
        else:
            lines.append("No individual tests or services were identified on analyzed pages.\n")

        # Contact & Branches
        contact = data.get('contact_us') or {}
        lines.append("## Contact & Facility Locations")
        if contact.get('phone'):
            lines.append(f"- **Phone:** {', '.join(contact['phone'])}")
        if contact.get('email'):
            lines.append(f"- **Email:** {', '.join(contact['email'])}")
        if contact.get('working_hours'):
            lines.append(f"- **Operating Hours:** {', '.join(contact['working_hours'])}")
        if contact.get('address'):
            lines.append("- **Addresses / Centers:**")
            for addr in contact['address']:
                lines.append(f"  - {addr}")
        if contact.get('social_links'):
            lines.append("- **Official Social Channels:**")
            for sl in contact['social_links']:
                platform = "Social Profile"
                sl_low = sl.lower()
                if "linkedin.com" in sl_low:
                    platform = "LinkedIn"
                elif "twitter.com" in sl_low or "x.com" in sl_low:
                    platform = "Twitter / X"
                elif "facebook.com" in sl_low or "fb.com" in sl_low:
                    platform = "Facebook"
                elif "instagram.com" in sl_low:
                    platform = "Instagram"
                elif "youtube.com" in sl_low:
                    platform = "YouTube"
                elif "github.com" in sl_low:
                    platform = "GitHub"
                elif "threads.net" in sl_low:
                    platform = "Threads"
                elif "pinterest.com" in sl_low:
                    platform = "Pinterest"
                lines.append(f"  - **{platform}:** [{sl}]({sl})")
        if contact.get('source_url'):
            lines.append(f"\n*Source: {contact['source_url']}*")
        lines.append("")

        return "\n".join(lines)

