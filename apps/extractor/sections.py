import re
import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# Headings and phrases to ignore as products/services
BOILERPLATE_HEADINGS = {
    'navigation', 'menu', 'footer', 'quick links', 'useful links', 'about us',
    'contact us', 'contact', 'reach us', 'follow us', 'social media', 'newsletter',
    'subscribe', 'privacy policy', 'terms of use', 'terms & conditions', 'copyright',
    'disclaimer', 'sitemap', 'all rights reserved', 'search', 'get in touch',
    'customer support', 'help & support', 'frequently asked questions', 'faq',
    'latest news', 'recent posts', 'leave a comment', 'share this',
    'careers', 'career', 'jobs', 'job openings', 'join our team', 'join us',
    'work with us', 'make a difference', 'cookies', 'cookie policy',
    'our history', 'the story', 'timeline', 'our history timeline',
    'testing', 'service', 'services', 'product', 'products', 'read more',
    'read more »', 'view details', 'learn more', 'know more', 'home',
    'our services', 'our testing services', 'all services', 'what we offer',
    'what we provide', 'our products', 'quality control', 'certified',
    'our major clients', 'major clients', 'our clients', 'clients', 'testimonials',
    'our process', 'why choose us', 'about company', 'who we are',
    'need quality testing of your product?.', 'need quality testing of your product?',
    'need quality testing', 'quality control testing', 'submit your query',
    'get a quote', 'request a quote', 'request quote', 'quick contact',
    'testing requirements', 'send query', 'send message', 'contact us now',
    'call us now', 'enquire now', 'enquire online', 'send enquiry', 'load more',
    'see more', 'view all', 'explore more', 'click here', 'book test', 'book now',
    'total 29 openings', 'we are hiring!', 'we are hiring', 'hiring',
    'name', 'phone', 'email', 'requirements', 'message', 'subject', 'your name',
    'your email', 'your phone', 'your message', 'submit', 'send', 'query',
    'name phone email testing requirements send query', 'captcha', 'enter text',
    'required fields', '450 +', '150 +', '125000 +', '7500 +', 'no comments',
    'uncategorized', 'recent blog', 'latest blog', 'leave a reply',
    'call us at', 'mail us at', 'visit us at', 'get a callback', 'get in touch today',
    'send request', "let's discuss", 'get your free consultation', 'contact number',
    'name email contact number message send', 'name email contact number send',
    'our story', 'our mission', 'vision', 'mission', 'quality policy',
    'independence', 'confidentiality', 'quality', 'speed of service', 'technology',
    'certification', 'certifications', 'projects', 'professional specialists',
    'accurate reports', 'wide range', 'advanced instruments',
    'professional specialists accurate reports', 'wide range advanced instruments',
    'solutions with cutting edge technology', 'cutting edge material testing solutions',
    "let's discuss your next material testing project", "let's discuss your next testing project",
    'ready to get started?', 'ready to get started', 'contact stellar test house',
    'partner with stellar test house today', 'trusted partner for road material testing',
    'vaibhav jain', 'anurag singh'
}

SERVICE_KEYWORDS = {
    'test', 'tests', 'testing', 'diagnostic', 'diagnostics', 'pathology',
    'screening', 'panel', 'profile', 'assay', 'assays', 'biopsy', 'radiology',
    'imaging', 'scan', 'mri', 'ct', 'ultrasound', 'consultation', 'checkup',
    'package', 'service', 'services', 'examination', 'blood', 'genomics',
    'material', 'materials', 'textiles', 'textile', 'geotechnical', 'microbiological',
    'environmental', 'cosmetics', 'pharmaceuticals', 'pharmaceutical', 'pharma',
    'chemical', 'physical', 'biological', 'metallurgical', 'non-destructive',
    'ndt', 'calibration', 'sampling', 'inspection', 'analysis', 'alloys', 'metal',
    'electrical', 'soil', 'water', 'food', 'road', 'leather', 'rubber', 'plastic',
    'polymer', 'coal', 'fuel', 'oil', 'petroleum'
}

PRODUCT_KEYWORDS = {
    'kit', 'kits', 'device', 'devices', 'equipment', 'instrument', 'reagent',
    'reagents', 'analyzer', 'consumables', 'software', 'platform', 'system',
    'app', 'tool', 'product', 'products', 'hardware'
}

class ProductServiceExtractor:
    """
    Deterministically segments and extracts structured products, tests,
    and services from HTML content and heading structures.
    """

    def _is_boilerplate(self, text: str) -> bool:
        if not text or not text.strip():
            return True
        t_low = re.sub(r'\s+', ' ', text.lower().strip())
        t_clean = re.sub(r'[^a-z0-9\s]', '', t_low).strip()

        if t_low in BOILERPLATE_HEADINGS or t_clean in BOILERPLATE_HEADINGS:
            return True

        # Single word non-services / form inputs / policy headings
        if t_clean in {
            'name', 'phone', 'email', 'requirements', 'message', 'subject', 'query',
            'submit', 'send', 'captcha', 'reset', 'clear', 'search', 'home', 'overview',
            'details', 'info', 'location', 'locations', 'address', 'city', 'state',
            'country', 'zip', 'pincode', 'title', 'type', 'status', 'back', 'next',
            'previous', 'close', 'open', 'menu', 'navigation', 'footer', 'header',
            'hiring', 'careers', 'vacancies', 'openings', 'jobs', 'vision', 'mission',
            'quality', 'technology', 'projects', 'certifications', 'certification',
            'independence', 'confidentiality', 'values', 'aim', 'goal', 'goals'
        }:
            return True

        # Generic section phrases / CTA text / Contact & Company headers
        boilerplate_phrases = [
            'navigation', 'quick links', 'useful links', 'about us', 'contact us',
            'follow us', 'social media', 'newsletter', 'privacy policy', 'terms of use',
            'terms & conditions', 'all rights reserved', 'customer support',
            'frequently asked questions', 'recent posts', 'leave a comment', 'no comments',
            'job openings', 'join our team', 'work with us', 'cookie policy',
            'our testing services', 'what we offer', 'what we provide', 'all services',
            'our major clients', 'submit your query', 'send query', 'enquire now',
            'call us now', 'call us at', 'mail us at', 'visit us at', 'get a callback',
            'get in touch', 'send request', "let's discuss", 'free consultation',
            'contact number', 'our story', 'our mission', 'quality policy',
            'speed of service', 'professional specialists', 'accurate reports',
            'wide range', 'advanced instruments', 'cutting edge', 'ready to get started',
            'contact stellar', 'partner with', 'trusted partner', 'vaibhav jain',
            'anurag singh', 'load more', 'we are hiring', 'total openings', 'openings',
            'get a quote', 'request a quote', 'need quality testing', 'read more',
            'testing requirements', 'our products', 'client testimonials', 'our process',
            'why choose us', 'corporate overview', 'company profile', 'serving since',
            'visit us on', 'indiamart', 'lab near you', 'news & blog', 'download brochure',
            'brochure', 'iso 9001', 'iso 14001', 'iso 45001', 'nabl', 'bis approved',
            'office address', 'email address', 'working hours', 'phone number',
            'contact info', 'contact information', 'our location', 'head office',
            'registered office', 'we look forward', 'trusted experts', 'welcome to',
            'ghaziabad testing laboratories', 'about our company', 'who we are',
            'look forward to seeing you'
        ]
        if any(phrase in t_low for phrase in boilerplate_phrases):
            return True

        # Accreditation titles like "ISO: 9001: 2015"
        if t_low.startswith('iso:') or t_clean.startswith('iso 9001'):
            return True

        # Stat numbers (e.g. "450 +", "125000 +")
        if re.match(r'^\d+[\s\+\%\,]*$', t_low) or re.match(r'^\d+\s*(?:plus|\+|\%)\s*$', t_low):
            return True

        # Date / blog post comment line (e.g. "June 21, 2024 No Comments")
        if 'no comments' in t_low or re.search(r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b', t_low):
            return True

        # Combined form field string (e.g. "Name Phone Email Testing Requirements Send Query")
        if 'name' in t_low and 'phone' in t_low and 'email' in t_low:
            return True

        # If name is too long to be a service title (e.g. sentence header)
        if len(t_low.split()) > 7:
            return True

        # If name is a question or generic promo / CTA sentence
        if t_low.startswith((
            'call us', 'mail us', 'visit us', 'get a callback', 'get in touch', 'let\'s ',
            'partner with', 'ready to ', 'the importance', 'understanding the',
            'building a', 'how ', 'why ', 'a certified', 'get a quote', 'next page',
            'previous page', 'need quality', 'we are the', 'we look forward'
        )):
            return True

        return False

    def extract_from_html(self, html: str, page_url: str) -> List[Dict[str, Any]]:
        if not html or not html.strip():
            return []

        soup = BeautifulSoup(html, 'html.parser')

        # Do not decompose header/footer/nav as service cards may be in grid components
        for tag in soup.find_all(['script', 'style', 'noscript', 'svg', 'canvas', 'iframe', 'dialog']):
            tag.decompose()

        items: List[Dict[str, Any]] = []
        seen_names = set()

        # Target content root
        content_root = soup.find(['main', 'article']) or soup.body or soup

        # 0. Grid Link Extraction (for index/list pages like /services, /products)
        from urllib.parse import urljoin
        grid_links = content_root.find_all('a', href=True)
        for a_tag in grid_links:
            href = a_tag.get('href', '').strip()
            if not href:
                continue
            full_url = urljoin(page_url, href)

            a_text = a_tag.get_text(separator=' ', strip=True)
            a_text = re.sub(r'^(?:Testing|Service|Product)\s+', '', a_text, flags=re.I).strip()
            a_text = re.sub(r'\s*Read\s*More\s*»?$', '', a_text, flags=re.I).strip()

            if not a_text or len(a_text) < 4 or len(a_text) > 80:
                continue

            a_lower = a_text.lower()
            if self._is_boilerplate(a_text):
                continue

            href_lower = href.lower()
            is_detail_link = any(k in href_lower for k in ['/service/', '/product/', '/testing/', '/test/'])

            if is_detail_link and a_lower not in seen_names:
                seen_names.add(a_lower)
                items.append({
                    'name': a_text,
                    'type': self._classify_type(a_text, "", full_url),
                    'summary': "",
                    'source_url': full_url
                })

        # 1. Inspect cards / containers specifically tagged as products/services/tests
        card_selectors = [
            {'class': re.compile(r'(?:product|service|test|package|diagnostic|themestek|elementor|pf-box|ts-box|grid-item|card-item)[-_]?(?:card|item|box|block|listing|title|content|wrapper)?', re.I)},
            {'class': re.compile(r'pricing[-_]?table', re.I)},
            {'class': re.compile(r'menu-item-object-ts-service', re.I)}
        ]
        cards = []
        for selector in card_selectors:
            cards.extend(content_root.find_all('div', attrs=selector))
            cards.extend(content_root.find_all('article', attrs=selector))
            cards.extend(content_root.find_all('li', attrs=selector))

        if cards:
            for card in cards:
                item = self._extract_card_item(card, page_url)
                if item and item['name'].lower() not in seen_names:
                    seen_names.add(item['name'].lower())
                    items.append(item)

        # 2. Heading-based segmentation
        heading_tags = content_root.find_all(['h2', 'h3', 'h4'])
        for h in heading_tags:
            h_text = h.get_text(separator=' ', strip=True)
            h_text = re.sub(r'^(?:Testing|Service|Product)\s+', '', h_text, flags=re.I).strip()
            if not h_text or len(h_text) < 3 or len(h_text) > 120:
                continue

            h_lower = h_text.lower()
            if self._is_boilerplate(h_text):
                continue

            if h_lower in seen_names:
                continue

            content_paragraphs = []
            details_list = []

            curr = h.next_sibling
            while curr:
                if isinstance(curr, Tag):
                    if curr.name in ['h1', 'h2', 'h3', 'h4']:
                        break
                    if curr.name in ['ul', 'ol', 'dl']:
                        for li in curr.find_all(['li', 'dd']):
                            li_text = li.get_text(separator=' ', strip=True)
                            if li_text and len(li_text) > 2 and len(li_text) < 300:
                                details_list.append(li_text)
                    else:
                        p_text = curr.get_text(separator=' ', strip=True)
                        p_low = p_text.lower()
                        if p_text and len(p_text) > 10 and not any(intro in p_low for intro in ['welcome to', 'leading third-party', 'quality control testing laboratory', 'providing a wide range of testing services', 'established in', 'since 2002']):
                            content_paragraphs.append(p_text)
                curr = curr.next_sibling

            body_summary = " ".join(content_paragraphs).strip()
            if not body_summary and details_list:
                body_summary = "; ".join(details_list[:2])

            if body_summary or details_list:
                item_type = self._classify_type(h_text, body_summary, page_url)
                seen_names.add(h_lower)
                items.append({
                    'name': h_text,
                    'type': item_type,
                    'summary': body_summary[:500] if body_summary else "",
                    'details': details_list[:10],
                    'source_url': page_url,
                })

        return items

    def _extract_card_item(self, card: Tag, page_url: str) -> Optional[Dict[str, Any]]:
        """Extracts product/service from a distinct card container."""
        title_el = card.find(['h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'a']) or card
        if not title_el:
            return None

        title_text = title_el.get_text(separator=' ', strip=True)
        title_text = re.sub(r'^(?:Testing|Service|Product)\s+', '', title_text, flags=re.I).strip()
        if not title_text or len(title_text) < 3 or len(title_text) > 120:
            return None

        if self._is_boilerplate(title_text):
            return None

        intro_phrases = ['welcome to', 'leading third-party', 'quality control testing laboratory', 'providing a wide range of testing services', 'established in', 'since 2002']
        paras = [
            p.get_text(separator=' ', strip=True) for p in card.find_all('p')
            if p.get_text(strip=True) and not any(intro in p.get_text(strip=True).lower() for intro in intro_phrases)
        ]
        summary_text = " ".join(paras).strip()

        details = []
        for li in card.find_all('li'):
            li_t = li.get_text(separator=' ', strip=True)
            if li_t and len(li_t) > 2 and len(li_t) < 300:
                details.append(li_t)

        item_type = self._classify_type(title_text, summary_text, page_url)

        return {
            'name': title_text,
            'type': item_type,
            'summary': summary_text[:500] if summary_text else "",
            'details': details[:10],
            'source_url': page_url,
        }

    def _classify_type(self, title: str, text: str, url: str = "") -> str:
        """Determines if the item is a 'service', 'product', or 'unknown'."""
        combined = f"{title} {text} {url}".lower()

        # If URL is in /service/ or /services/ or /testing/, default to service
        url_lower = url.lower()
        if any(k in url_lower for k in ['/service/', '/services/', '/testing/', '/test/']):
            title_lower = title.lower()
            if any(re.search(rf'\b{re.escape(w)}\b', title_lower) for w in ('kit', 'kits', 'reagent', 'reagents', 'analyzer', 'analyzers', 'device', 'devices', 'equipment', 'instrument', 'consumables')):
                return 'product'
            return 'service'

        is_service = any(re.search(rf'\b{re.escape(w)}\b', combined) for w in SERVICE_KEYWORDS)
        is_product = any(re.search(rf'\b{re.escape(w)}\b', combined) for w in PRODUCT_KEYWORDS)

        if is_service and not is_product:
            return 'service'
        elif is_product and not is_service:
            title_lower = title.lower()
            if any(w in title_lower for w in ('testing', 'analysis', 'inspection', 'laboratory', 'food', 'water', 'chemical', 'material', 'soil', 'metal', 'leather', 'pharma', 'road', 'electrical')):
                return 'service'
            return 'product'
        elif is_service and is_product:
            title_lower = title.lower()
            if any(re.search(rf'\b{re.escape(w)}\b', title_lower) for w in ('kit', 'kits', 'reagent', 'reagents', 'analyzer', 'analyzers', 'device', 'devices', 'equipment', 'instrument', 'consumables')):
                return 'product'
            return 'service'

        return 'service' if ('test' in combined or 'service' in combined or 'analysis' in combined) else 'service'

    @staticmethod
    def deduplicate(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicates list of product/service dicts by normalized name."""
        unique_map: Dict[str, Dict[str, Any]] = {}
        extractor = ProductServiceExtractor()

        for it in items:
            name = str(it.get('name', '')).strip()
            if not name:
                continue

            if extractor._is_boilerplate(name):
                continue

            norm = re.sub(r'\s+', ' ', name.lower())

            # Default type to service if it's a valid service name
            if it.get('type') in (None, 'unknown'):
                it['type'] = extractor._classify_type(name, it.get('summary', ''), it.get('source_url', ''))

            if norm not in unique_map:
                unique_map[norm] = dict(it)
            else:
                existing = unique_map[norm]
                new_summary = str(it.get('summary', '')).strip()
                existing_summary = str(existing.get('summary', '')).strip()
                if len(new_summary) > len(existing_summary) and not new_summary.startswith("Comprehensive testing"):
                    unique_map[norm]['summary'] = new_summary
                    if it.get('source_url'):
                        unique_map[norm]['source_url'] = it.get('source_url')

        return list(unique_map.values())


