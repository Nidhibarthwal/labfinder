from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict, Any, Optional, Set
import logging
from .normalizer import normalize_url, is_same_domain

logger = logging.getLogger(__name__)

class DiscoveredLink:
    def __init__(
        self,
        url: str,
        normalized_url: str,
        anchor_text: str,
        title_attr: str = "",
        location: str = "body", # header, footer, nav, body
        context_text: str = "",
        is_internal: bool = True,
    ):
        self.url = url
        self.normalized_url = normalized_url
        self.anchor_text = anchor_text.strip()
        self.title_attr = title_attr.strip()
        self.location = location
        self.context_text = context_text.strip()
        self.is_internal = is_internal

    def to_dict(self) -> Dict[str, Any]:
        return {
            'url': self.url,
            'normalized_url': self.normalized_url,
            'anchor_text': self.anchor_text,
            'title_attr': self.title_attr,
            'location': self.location,
            'context_text': self.context_text[:120],
            'is_internal': self.is_internal,
        }

class LinkDiscovery:
    """
    Extracts, classifies, and prioritizes links from HTML pages.
    """

    def __init__(self, base_url: str):
        self.base_url = base_url

    def discover_links(self, html: str, page_url: str) -> List[DiscoveredLink]:
        """
        Parses the page HTML and extracts all internal links, annotating their
        DOM location (header, nav, footer, body) and surrounding text context.
        """
        if not html:
            return []

        soup = BeautifulSoup(html, 'html.parser')
        discovered: Dict[str, DiscoveredLink] = {}

        # Identify structural landmarks
        nav_elements = soup.find_all(['nav', 'header', 'footer', 'aside'])
        header_tag = soup.find('header')
        footer_tag = soup.find('footer')

        all_links = soup.find_all('a', href=True)

        for a_tag in all_links:
            raw_href = a_tag['href'].strip()
            if not raw_href or raw_href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                continue

            normalized = normalize_url(raw_href, base_url=page_url)
            if not normalized:
                continue

            is_internal = is_same_domain(self.base_url, normalized)
            if not is_internal:
                continue

            # Determine DOM location
            location = "body"
            parents = [p.name.lower() for p in a_tag.parents if p.name]
            parent_classes = " ".join([
                " ".join(p.get('class', [])) for p in a_tag.parents if hasattr(p, 'get') and p.get('class')
            ]).lower()

            if footer_tag and a_tag in footer_tag.descendants or 'footer' in parents or 'footer' in parent_classes:
                location = "footer"
            elif header_tag and a_tag in header_tag.descendants or 'header' in parents or 'header' in parent_classes:
                location = "header"
            elif 'nav' in parents or 'menu' in parent_classes or 'navigation' in parent_classes:
                location = "nav"

            anchor_text = a_tag.get_text(separator=' ', strip=True)
            title_attr = a_tag.get('title', '')
            
            # Extract surrounding parent text context (e.g. li or p)
            context = ""
            if a_tag.parent and a_tag.parent.name in ('p', 'li', 'td', 'div', 'span'):
                context = a_tag.parent.get_text(separator=' ', strip=True)

            # Store or enhance discovered link
            if normalized not in discovered or (location in ('nav', 'header') and discovered[normalized].location == 'body'):
                discovered[normalized] = DiscoveredLink(
                    url=raw_href,
                    normalized_url=normalized,
                    anchor_text=anchor_text,
                    title_attr=title_attr,
                    location=location,
                    context_text=context,
                    is_internal=is_internal
                )

        return list(discovered.values())
