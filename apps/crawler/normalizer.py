import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, urljoin
from typing import Optional

TRACKING_QUERY_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'gclid', 'fbclid', 'msclkid', 'mc_cid', 'mc_eid', 'ref', 'source',
    '_ga', '_gl', 'yclid'
}

IGNORED_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico', '.bmp', '.tiff',
    '.css', '.js', '.map', '.json', '.xml', '.rss', '.atom',
    '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.csv',
    '.zip', '.tar', '.gz', '.rar', '.7z', '.exe', '.dmg', '.iso',
    '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.ogg',
    '.woff', '.woff2', '.ttf', '.eot', '.otf'
}

IGNORED_SCHEMES = {'mailto', 'tel', 'javascript', 'data', 'whatsapp', 'callto'}

def is_valid_http_url(url: str) -> bool:
    """Check if URL has http or https scheme and is not a resource/media file."""
    if not url or not isinstance(url, str):
        return False
    
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ('http', 'https'):
        return False
    
    path = parsed.path.lower()
    for ext in IGNORED_EXTENSIONS:
        if path.endswith(ext):
            return False
            
    return True

def normalize_url(raw_url: str, base_url: Optional[str] = None) -> Optional[str]:
    """
    Normalizes a given URL against a base URL:
    - Resolves relative URLs.
    - Strips fragment identifiers.
    - Lowercases scheme and netloc.
    - Strips tracking query parameters while preserving meaningful query parameters.
    - Sorts remaining query parameters.
    - Normalizes path slashes.
    """
    if not raw_url or not isinstance(raw_url, str):
        return None

    raw_url = raw_url.strip()

    # Check for ignored schemes like mailto:, javascript:
    if ':' in raw_url:
        scheme_prefix = raw_url.split(':', 1)[0].lower()
        if scheme_prefix in IGNORED_SCHEMES:
            return None

    # Resolve relative URL if base_url is supplied
    if base_url:
        try:
            raw_url = urljoin(base_url, raw_url)
        except Exception:
            return None

    try:
        parsed = urlparse(raw_url)
    except Exception:
        return None

    scheme = parsed.scheme.lower()
    if scheme not in ('http', 'https'):
        return None

    netloc = parsed.netloc.lower()
    if not netloc:
        return None

    # Remove standard ports
    if ':' in netloc:
        host, port = netloc.split(':', 1)
        if (scheme == 'http' and port == '80') or (scheme == 'https' and port == '443'):
            netloc = host

    # Normalize path
    path = parsed.path
    if not path:
        path = '/'
    else:
        # Collapse multiple consecutive slashes into single slash
        path = re.sub(r'/+', '/', path)
        # Remove trailing slash if path is longer than '/'
        if len(path) > 1 and path.endswith('/'):
            path = path[:-1]

    # Ignore resource files
    path_lower = path.lower()
    for ext in IGNORED_EXTENSIONS:
        if path_lower.endswith(ext):
            return None

    # Filter and sort query parameters
    filtered_params = []
    if parsed.query:
        for k, v in parse_qsl(parsed.query, keep_blank_values=True):
            if k.lower() not in TRACKING_QUERY_PARAMS:
                filtered_params.append((k, v))
        filtered_params.sort()

    new_query = urlencode(filtered_params) if filtered_params else ''

    # Reconstruct URL without fragment
    normalized = urlunparse((scheme, netloc, path, '', new_query, ''))
    return normalized

def extract_domain(url: str) -> Optional[str]:
    """Extract registered domain/host from URL."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if ':' in host:
            host = host.split(':', 1)[0]
        # Remove leading www.
        if host.startswith('www.'):
            host = host[4:]
        return host
    except Exception:
        return None

def is_same_domain(url_a: str, url_b: str) -> bool:
    """Check if two URLs belong to the same core domain."""
    domain_a = extract_domain(url_a)
    domain_b = extract_domain(url_b)
    if not domain_a or not domain_b:
        return False
    return domain_a == domain_b
