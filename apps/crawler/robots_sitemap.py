import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging
from typing import List, Set, Optional, Tuple
from .http_client import SafeHttpClient
from .normalizer import normalize_url, is_same_domain

logger = logging.getLogger(__name__)

class RobotsHandler:
    """
    Parses and checks permissions against /robots.txt according to RFC 9309
    (Robots Exclusion Protocol): supports wildcards (* and $), longest-match
    rule, and proper precedence (Allow overrides Disallow on ties).
    """

    def __init__(self, base_url: str, http_client: Optional[SafeHttpClient] = None):
        self.base_url = base_url
        self.http_client = http_client or SafeHttpClient()
        self.robots_url = urljoin(base_url, '/robots.txt')
        self.is_loaded = False
        self.sitemaps: List[str] = []
        self.rules: List[Tuple[bool, str]] = []  # List of (allowance, pattern)

    def load(self):
        """Fetches and parses robots.txt."""
        try:
            res = self.http_client.fetch(self.robots_url)
            if res.is_success and res.html:
                self._parse(res.html)
            self.is_loaded = True
        except Exception as e:
            logger.warning(f"Failed to load robots.txt for {self.base_url}: {e}")
            self.is_loaded = True

    def _parse(self, content: str):
        lines = content.splitlines()
        current_agents: List[str] = []
        current_rules: List[Tuple[bool, str]] = []

        for raw_line in lines:
            line = raw_line.split('#', 1)[0].strip()
            if not line:
                continue

            if line.lower().startswith('sitemap:'):
                parts = line.split(':', 1)
                if len(parts) > 1:
                    smap = parts[1].strip()
                    if smap and smap not in self.sitemaps:
                        self.sitemaps.append(smap)
                continue

            if ':' not in line:
                continue

            directive, val = line.split(':', 1)
            directive = directive.strip().lower()
            val = val.strip()

            if directive == 'user-agent':
                if current_rules and current_agents:
                    if '*' in current_agents:
                        self.rules.extend(current_rules)
                    current_rules = []
                    current_agents = []
                current_agents.append(val.lower())
            elif directive in ('allow', 'disallow'):
                if directive == 'disallow' and not val:
                    # Empty disallow means allow all
                    current_rules.append((True, '/'))
                elif val:
                    allowance = (directive == 'allow')
                    current_rules.append((allowance, val))

        if current_rules and current_agents:
            if '*' in current_agents:
                self.rules.extend(current_rules)

    def can_fetch(self, url: str, user_agent: str = '*') -> bool:
        """
        Returns True if the URL path is allowed by robots.txt.
        Evaluates matches by RFC 9309 longest-match rule.
        """
        if not self.is_loaded:
            self.load()

        if not self.rules:
            return True

        parsed = urlparse(url)
        path = parsed.path or '/'
        if parsed.query:
            path = f"{path}?{parsed.query}"

        matching: List[Tuple[int, bool]] = []
        for allowance, pat in self.rules:
            try:
                escaped = re.escape(pat)
                escaped = escaped.replace(r'\*', '.*')
                if escaped.endswith(r'\$'):
                    pattern_regex = '^' + escaped[:-2] + '$'
                else:
                    pattern_regex = '^' + escaped

                if re.match(pattern_regex, path):
                    # Record (pattern_length, allowance)
                    matching.append((len(pat), allowance))
            except Exception:
                continue

        if not matching:
            return True

        # Longest match wins. On length tie, Allow (True) wins.
        matching.sort(key=lambda x: (x[0], 1 if x[1] else 0), reverse=True)
        return matching[0][1]


class SitemapHandler:
    """Discovers and parses sitemap.xml and nested sitemap index files."""

    def __init__(self, base_url: str, http_client: Optional[SafeHttpClient] = None):
        self.base_url = base_url
        self.http_client = http_client or SafeHttpClient()

    def discover_urls(self, custom_sitemap_urls: Optional[List[str]] = None, max_urls: int = 50) -> List[str]:
        """
        Discovers candidate URLs from sitemap.xml or explicitly found sitemaps.
        """
        targets = list(custom_sitemap_urls or [])
        default_sitemap = urljoin(self.base_url, '/sitemap.xml')
        if default_sitemap not in targets:
            targets.append(default_sitemap)

        discovered: Set[str] = set()
        visited_sitemaps: Set[str] = set()

        for sitemap_url in targets:
            if len(discovered) >= max_urls:
                break
            self._parse_sitemap_recursive(sitemap_url, discovered, visited_sitemaps, max_urls, depth=0)

        return list(discovered)

    def _parse_sitemap_recursive(
        self,
        sitemap_url: str,
        discovered: Set[str],
        visited_sitemaps: Set[str],
        max_urls: int,
        depth: int = 0
    ):
        if depth > 2 or sitemap_url in visited_sitemaps or len(discovered) >= max_urls:
            return

        visited_sitemaps.add(sitemap_url)
        res = self.http_client.fetch(sitemap_url)
        if not res.is_success or not res.html:
            return

        try:
            soup = BeautifulSoup(res.html, 'xml')
            
            # Check for sitemapindex (<sitemap><loc>...</loc></sitemap>)
            sitemap_locs = soup.find_all('sitemap')
            if sitemap_locs:
                for sm in sitemap_locs[:3]:
                    loc_tag = sm.find('loc')
                    if loc_tag and loc_tag.text:
                        sub_sitemap_url = loc_tag.text.strip()
                        self._parse_sitemap_recursive(sub_sitemap_url, discovered, visited_sitemaps, max_urls, depth + 1)
                        if len(discovered) >= max_urls:
                            return

            # Check for regular urlset (<url><loc>...</loc></url>)
            urls = soup.find_all('url')
            for u in urls:
                loc_tag = u.find('loc')
                if loc_tag and loc_tag.text:
                    raw_url = loc_tag.text.strip()
                    norm_url = normalize_url(raw_url, base_url=self.base_url)
                    if norm_url and is_same_domain(self.base_url, norm_url):
                        discovered.add(norm_url)
                        if len(discovered) >= max_urls:
                            return

        except Exception as e:
            logger.warning(f"Error parsing XML sitemap at {sitemap_url}: {e}")
