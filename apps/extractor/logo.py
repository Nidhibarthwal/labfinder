import re
import json
import base64
import mimetypes
import logging
from typing import Dict, Optional, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Social/tracking icons to explicitly exclude from logo candidates
EXCLUDED_ICON_KEYWORDS = [
    'twitter', 'facebook', 'linkedin', 'instagram', 'youtube', 'github',
    'whatsapp', 'pinterest', 'tiktok', 'telegram', 'rss', 'share', 'avatar',
    'user', 'author', 'payment', 'visa', 'mastercard', 'paypal', 'cart'
]

class LogoExtractor:
    """
    Deterministic Company Logo Extractor.
    Inspects HTML for logos in priority order without making LLM calls:
    1. Schema.org JSON-LD (Organization, MedicalOrganization, MedicalBusiness, DiagnosticLab, WebSite)
    2. Header / Nav elements containing logo images
    3. Elements with itemprop="logo" or class/id matching "logo"
    4. General <img> matching logo in src/alt (excluding social icons)
    5. OpenGraph / Twitter metadata (og:logo, og:image if branded)
    6. Favicon fallback (as last resort)
    """

    def url_to_base64(self, logo_url: Optional[str], http_client: Optional[Any] = None) -> Optional[str]:
        """
        Converts a logo URL to a Base64 data URI (data:image/...;base64,...).
        If logo_url is already a data URI, it is returned directly.
        If logo_url is HTTP/HTTPS, fetches binary data and encodes to base64.
        """
        if not logo_url:
            return None

        url_str = str(logo_url).strip()
        if url_str.startswith('data:'):
            return url_str

        parsed = urlparse(url_str)
        if parsed.scheme not in ('http', 'https'):
            return None

        image_bytes, content_type = None, None

        if http_client and hasattr(http_client, 'fetch_binary'):
            image_bytes, content_type = http_client.fetch_binary(url_str)
        else:
            try:
                import httpx
                resp = httpx.get(url_str, timeout=5.0, headers={'User-Agent': 'Mozilla/5.0'})
                if resp.status_code == 200:
                    image_bytes = resp.content
                    content_type = resp.headers.get('content-type', '')
            except Exception as e:
                logger.warning(f"Direct logo base64 conversion fetch failed for {url_str}: {e}")
                return None

        if not image_bytes:
            return None

        # Determine MIME type
        mime_type = content_type.split(';')[0].strip() if content_type else ''
        if not mime_type or mime_type in ('application/octet-stream', 'text/plain', 'text/html'):
            mime_guess, _ = mimetypes.guess_type(url_str)
            if mime_guess:
                mime_type = mime_guess

        if not mime_type or not mime_type.startswith('image/'):
            # Detect from magic header bytes
            if image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                mime_type = 'image/png'
            elif image_bytes.startswith(b'\xff\xd8\xff'):
                mime_type = 'image/jpeg'
            elif image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'):
                mime_type = 'image/gif'
            elif image_bytes.startswith(b'RIFF') and len(image_bytes) > 12 and image_bytes[8:12] == b'WEBP':
                mime_type = 'image/webp'
            elif b'<svg' in image_bytes[:500].lower():
                mime_type = 'image/svg+xml'
            else:
                mime_type = 'image/png'

        b64_encoded = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:{mime_type};base64,{b64_encoded}"

    def _format_logo_result(
        self,
        raw_result: Optional[Dict[str, Optional[str]]],
        fetch_base64: bool = False,
        http_client: Optional[Any] = None
    ) -> Dict[str, Optional[str]]:
        if not raw_result or not raw_result.get('url'):
            return {"url": None, "base64": None, "alt": None, "source_page": None}

        url = raw_result['url']
        alt = raw_result.get('alt')
        source_page = raw_result.get('source_page')

        b64_val = raw_result.get('base64') or (url if url.startswith('data:') else None)

        if fetch_base64 and not b64_val:
            b64_val = self.url_to_base64(url, http_client=http_client)

        return {
            "url": url,
            "base64": b64_val,
            "alt": alt,
            "source_page": source_page
        }

    def extract_logo(
        self,
        html: str,
        page_url: str,
        fetch_base64: bool = False,
        http_client: Optional[Any] = None
    ) -> Dict[str, Optional[str]]:
        """
        Extracts canonical company logo from HTML.
        Returns:
            {
                "url": canonical_logo_url or None,
                "base64": base64_data_uri or None,
                "alt": alt_text or None,
                "source_page": page_url or None
            }
        """
        if not html or not html.strip():
            return {"url": None, "base64": None, "alt": None, "source_page": None}

        soup = BeautifulSoup(html, 'html.parser')

        # 1. Schema.org JSON-LD structured data
        schema_logo = self._extract_from_json_ld(soup, page_url)
        if schema_logo and schema_logo.get('url'):
            return self._format_logo_result(schema_logo, fetch_base64, http_client)

        # 2. Header / Navbar inspection (Highest visual precision)
        header_logo = self._extract_from_header_nav(soup, page_url)
        if header_logo and header_logo.get('url'):
            return self._format_logo_result(header_logo, fetch_base64, http_client)

        # 3. Explicit logo attributes (itemprop="logo" or class/id logo)
        attr_logo = self._extract_from_logo_attributes(soup, page_url)
        if attr_logo and attr_logo.get('url'):
            return self._format_logo_result(attr_logo, fetch_base64, http_client)

        # 4. General <img> tags with "logo" in src or alt
        img_logo = self._extract_from_general_images(soup, page_url)
        if img_logo and img_logo.get('url'):
            return self._format_logo_result(img_logo, fetch_base64, http_client)

        # 5. OpenGraph metadata
        og_logo = self._extract_from_meta_tags(soup, page_url)
        if og_logo and og_logo.get('url'):
            return self._format_logo_result(og_logo, fetch_base64, http_client)

        # 6. Favicon fallback
        favicon = self._extract_favicon_fallback(soup, page_url)
        if favicon and favicon.get('url'):
            return self._format_logo_result(favicon, fetch_base64, http_client)

        return {"url": None, "base64": None, "alt": None, "source_page": None}

    def _is_valid_image_url(self, url: str) -> bool:
        """Validates that candidate URL is HTTP/HTTPS or a data URI and not empty."""
        if not url:
            return False
        url_str = str(url).strip()
        if url_str.startswith('data:'):
            return True
        if url_str.startswith('javascript:'):
            return False
        parsed = urlparse(url_str)
        return parsed.scheme in ('http', 'https') and bool(parsed.netloc)

    def _is_excluded(self, text: str) -> bool:
        """Checks if text mentions social media, tracking, or other non-company icons."""
        lower = text.lower()
        return any(ex in lower for ex in EXCLUDED_ICON_KEYWORDS)

    def _clean_img_url(self, src: str, page_url: str) -> Optional[str]:
        """Resolves relative URL and extracts from srcset if needed."""
        if not src:
            return None
        src_str = str(src).strip()
        if src_str.startswith('data:'):
            return src_str
        # Handle srcset format (e.g. "image.png 1x, image-2x.png 2x")
        first_src = src_str.split(',')[0].strip().split(' ')[0].strip()
        joined = urljoin(page_url, first_src)
        return joined if self._is_valid_image_url(joined) else None



    def _extract_from_json_ld(self, soup: BeautifulSoup, page_url: str) -> Optional[Dict[str, Optional[str]]]:
        """Parses Schema.org JSON-LD scripts for Organization logo."""
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                if not script.string:
                    continue
                data = json.loads(script.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    # Check @graph if present
                    sub_items = item.get('@graph', [item]) if isinstance(item.get('@graph'), list) else [item]
                    for sub in sub_items:
                        if not isinstance(sub, dict):
                            continue
                        type_val = str(sub.get('@type', '')).lower()
                        if any(t in type_val for t in ('organization', 'business', 'lab', 'website', 'medical')):
                            logo_val = sub.get('logo') or sub.get('image')
                            if isinstance(logo_val, dict):
                                logo_url = logo_val.get('url') or logo_val.get('contentUrl')
                            elif isinstance(logo_val, str):
                                logo_url = logo_val
                            else:
                                logo_url = None

                            if logo_url and not self._is_excluded(logo_url):
                                clean_url = self._clean_img_url(logo_url, page_url)
                                if clean_url:
                                    alt = sub.get('name') or sub.get('legalName') or 'Company Logo'
                                    return {
                                        'url': clean_url,
                                        'alt': str(alt),
                                        'source_page': page_url
                                    }
            except Exception:
                continue
        return None

    def _extract_from_header_nav(self, soup: BeautifulSoup, page_url: str) -> Optional[Dict[str, Optional[str]]]:
        """Looks for logo inside <header> or <nav> structures."""
        header_containers = soup.find_all(['header', 'nav'])
        header_containers += soup.find_all(attrs={'class': re.compile(r'header|navbar|top-bar|site-branding', re.I)})

        for container in header_containers:
            for img in container.find_all(['img', 'source']):
                src = img.get('src') or img.get('srcset') or img.get('data-src')
                alt = img.get('alt', '')
                class_id = f"{img.get('class', '')} {img.get('id', '')}"

                # Test if candidate signals indicate logo
                is_logo_signal = (
                    'logo' in class_id.lower() or
                    'logo' in alt.lower() or
                    'logo' in str(src).lower() or
                    'brand' in class_id.lower()
                )

                if is_logo_signal and not self._is_excluded(f"{src} {alt} {class_id}"):
                    clean_url = self._clean_img_url(src, page_url)
                    if clean_url:
                        return {
                            'url': clean_url,
                            'alt': alt.strip() or 'Company Logo',
                            'source_page': page_url
                        }
        return None

    def _extract_from_logo_attributes(self, soup: BeautifulSoup, page_url: str) -> Optional[Dict[str, Optional[str]]]:
        """Inspects elements with itemprop="logo" or class/id matching logo."""
        # 1. itemprop="logo"
        for el in soup.find_all(attrs={'itemprop': re.compile(r'logo', re.I)}):
            src = el.get('src') or el.get('href') or el.get('content')
            if src and not self._is_excluded(src):
                clean_url = self._clean_img_url(src, page_url)
                if clean_url:
                    alt = el.get('alt', '') or 'Company Logo'
                    return {'url': clean_url, 'alt': alt.strip(), 'source_page': page_url}

        # 2. class or id matching exact logo patterns
        for img in soup.find_all(['img', 'source']):
            class_str = " ".join(img.get('class', [])) if isinstance(img.get('class'), list) else str(img.get('class', ''))
            id_str = str(img.get('id', ''))
            attrs_combined = f"{class_str} {id_str}".lower()

            if re.search(r'\b(site[-_]?logo|main[-_]?logo|company[-_]?logo|header[-_]?logo|logo)\b', attrs_combined):
                src = img.get('src') or img.get('srcset') or img.get('data-src')
                alt = img.get('alt', '')
                if src and not self._is_excluded(f"{src} {attrs_combined}"):
                    clean_url = self._clean_img_url(src, page_url)
                    if clean_url:
                        return {'url': clean_url, 'alt': alt.strip() or 'Company Logo', 'source_page': page_url}

        return None

    def _extract_from_general_images(self, soup: BeautifulSoup, page_url: str) -> Optional[Dict[str, Optional[str]]]:
        """Scans any img whose src or alt explicitly contains 'logo'."""
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('srcset') or img.get('data-src')
            alt = img.get('alt', '')
            if not src:
                continue

            src_str = str(src).lower()
            alt_str = alt.lower()

            if ('logo' in src_str or 'logo' in alt_str) and not self._is_excluded(f"{src_str} {alt_str}"):
                clean_url = self._clean_img_url(src, page_url)
                if clean_url:
                    return {'url': clean_url, 'alt': alt.strip() or 'Company Logo', 'source_page': page_url}

        return None

    def _extract_from_meta_tags(self, soup: BeautifulSoup, page_url: str) -> Optional[Dict[str, Optional[str]]]:
        """Inspects meta tags for logo or brand images."""
        # Check og:logo first
        og_logo_tag = soup.find('meta', property='og:logo') or soup.find('meta', attrs={'name': 'og:logo'})
        if og_logo_tag and og_logo_tag.get('content'):
            clean_url = self._clean_img_url(og_logo_tag['content'], page_url)
            if clean_url:
                return {'url': clean_url, 'alt': 'Company Logo', 'source_page': page_url}

        # Check og:image
        og_img = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'og:image'})
        if og_img and og_img.get('content'):
            content = og_img['content']
            if not self._is_excluded(content):
                clean_url = self._clean_img_url(content, page_url)
                if clean_url:
                    return {'url': clean_url, 'alt': 'Company Logo', 'source_page': page_url}

        return None

    def _extract_favicon_fallback(self, soup: BeautifulSoup, page_url: str) -> Optional[Dict[str, Optional[str]]]:
        """Fallback to favicon if no other logo image is found."""
        favicon_tag = soup.find('link', rel=lambda r: r and any(x in r.lower() for x in ('icon', 'shortcut icon', 'apple-touch-icon')))
        if favicon_tag and favicon_tag.get('href'):
            href = favicon_tag['href']
            clean_url = self._clean_img_url(href, page_url)
            if clean_url:
                return {'url': clean_url, 'alt': 'Site Icon', 'source_page': page_url}
        return None
