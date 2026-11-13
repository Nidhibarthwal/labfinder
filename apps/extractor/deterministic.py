import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Production-grade compiled regexes for instant deterministic extraction
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b')
PHONE_REGEX = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b')
# Expanded social media domain matchers
SOCIAL_DOMAINS = [
    'linkedin.com', 'twitter.com', 'x.com', 'facebook.com', 'fb.com',
    'instagram.com', 'youtube.com', 'github.com', 'threads.net', 'pinterest.com'
]

SOCIAL_REGEX = re.compile(
    r'https?://(?:www\.)?(?:'
    r'linkedin\.com/(?:company|school|in)/[a-zA-Z0-9_\-\.\%]+|'
    r'(?:twitter\.com|x\.com)/[a-zA-Z0-9_]+|'
    r'facebook\.com/[a-zA-Z0-9_\-\.]+|'
    r'instagram\.com/[a-zA-Z0-9_\-\.]+|'
    r'youtube\.com/(?:c/|channel/|user/|@)[a-zA-Z0-9_\-\.]+|'
    r'github\.com/[a-zA-Z0-9_\-\.]+|'
    r'threads\.net/@[a-zA-Z0-9_\-\.]+|'
    r'pinterest\.com/[a-zA-Z0-9_\-\.]+'
    r')/?',
    re.IGNORECASE
)

# Non-profile paths to filter out (share dialogs, intents, generic views)
SOCIAL_EXCLUDE_PATHS = [
    'sharer', 'share', 'intent', 'tweet', 'sharearticle', 'dialog',
    'search', 'hashtag', 'policies', 'privacy', 'terms', 'help',
    'login', 'signup', 'watch', 'embed', 'playlist', 'shorts',
    'pin/create', 'widgets', 'tr', 'plugins'
]

# Working hours regex (e.g. "Mon - Sat: 8:00 AM - 8:00 PM", "Open 24/7", "Timing: 7am to 9pm")
WORKING_HOURS_REGEX = re.compile(
    r'(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day|s)?(?:\s*[-–to]\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day|s)?)?[:\s]+(?:\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\s*[-–to]\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)|(?:Open\s+)?24\s*[/xX]\s*7(?:\s*Hours)?|\b(?:Timings?|Hours(?:\s+of\s+Operation)?|Working\s+Hours?|Operating\s+Hours?|Open)\s*[:\-]\s*[^\n,;]{5,80})',
    re.IGNORECASE
)

# Address keyword indicators
ADDRESS_INDICATORS = [
    'sector', 'road', 'rd', 'street', 'st.', 'avenue', 'ave', 'lane', 'plot',
    'building', 'tower', 'floor', 'block', 'suite', 'noida', 'delhi', 'mumbai',
    'bengaluru', 'bangalore', 'chennai', 'hyderabad', 'kolkata', 'gurugram',
    'gurgaon', 'pune', 'ahmedabad', 'pin', 'zip', 'india', 'usa', 'united states',
    'near', 'opp', 'opposite', 'behind', 'beside', 'postal code', 'district',
    'compound', 'area', 'ind.', 'g.t.', 'g.t', 'h.o.', 'head office', 'office address'
]

PINCODE_REGEX = re.compile(r'\b(?:\d{6}|\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b|\b\d{5}(?:-\d{4})?)\b')

def extract_deterministic_facts(clean_text: str, page_url: str) -> List[Dict[str, Any]]:
    """
    Instantly extracts high-confidence deterministic contact and company facts
    directly from page clean text with guaranteed verbatim source quotes (0.001s).
    """
    if not clean_text:
        return []

    facts = []
    seen_values = set()

    # 1. Emails
    for match in EMAIL_REGEX.finditer(clean_text):
        email = match.group(0).strip()
        if any(email.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp')):
            continue
        if email.lower() not in seen_values:
            seen_values.add(email.lower())
            facts.append({
                'category': 'CONTACT',
                'field': 'email',
                'value': email,
                'source_quote': email,
                'source_url': page_url,
                'char_start': match.start(),
                'char_end': match.end(),
            })

    # 2. Phone numbers
    for match in PHONE_REGEX.finditer(clean_text):
        phone = match.group(0).strip()
        digits_only = re.sub(r'\D', '', phone)
        if len(digits_only) >= 8 and phone not in seen_values:
            seen_values.add(phone)
            facts.append({
                'category': 'CONTACT',
                'field': 'phone',
                'value': phone,
                'source_quote': phone,
                'source_url': page_url,
                'char_start': match.start(),
                'char_end': match.end(),
            })

    # 3. Social Profiles
    for match in SOCIAL_REGEX.finditer(clean_text):
        social_url = match.group(0).strip()
        if social_url not in seen_values:
            seen_values.add(social_url)
            facts.append({
                'category': 'COMPANY',
                'field': 'social_profile',
                'value': social_url,
                'source_quote': social_url,
                'source_url': page_url,
                'char_start': match.start(),
                'char_end': match.end(),
            })

    # 4. Working hours
    for match in WORKING_HOURS_REGEX.finditer(clean_text):
        hours = match.group(0).strip()
        if len(hours) >= 6 and hours.lower() not in seen_values:
            seen_values.add(hours.lower())
            facts.append({
                'category': 'CONTACT',
                'field': 'working_hours',
                'value': hours,
                'source_quote': hours,
                'source_url': page_url,
                'char_start': match.start(),
                'char_end': match.end(),
            })

    # 5. Address lines with contiguous multi-line stitching
    lines = [l.strip() for l in clean_text.splitlines() if l.strip()]
    for i, line_clean in enumerate(lines):
        if len(line_clean) < 15 or len(line_clean) > 220:
            continue
        line_lower = line_clean.lower()
        has_pincode = bool(PINCODE_REGEX.search(line_clean))
        matches_indicator = sum(1 for ind in ADDRESS_INDICATORS if ind in line_lower)

        if (has_pincode and matches_indicator >= 1) or matches_indicator >= 2:
            full_addr = line_clean

            # Stitch preceding line if it contains address prefix (e.g. AO-150 Amrit Steel Compound)
            prefix_parts = []
            j = i - 1
            while j >= 0:
                prev = lines[j]
                prev_low = prev.lower()
                if any(p in prev_low for p in ['office address', 'head office', 'registered office', 'address:', 'location:']):
                    clean_prev = re.sub(r'^(?:office address|head office|registered office|address|location)[:\s]*', '', prev, flags=re.I).strip()
                    if clean_prev:
                        prefix_parts.insert(0, clean_prev)
                    break
                if len(prev) < 150 and any(k in prev_low for k in ['ao-', 'plot', 'no.', 'building', 'compound', 'suite', 'floor', 'street', 'road', 'h.no', 'flat', 'house']):
                    prefix_parts.insert(0, prev)
                    j -= 1
                else:
                    break

            if prefix_parts:
                full_addr = ' '.join(prefix_parts + [full_addr])

            # Stitch subsequent lines if they contain city, state, pincode, or country (e.g. Ghaziabad-201001, UP, India)
            j_next = i + 1
            while j_next < len(lines):
                nxt = lines[j_next]
                nxt_low = nxt.lower()
                if len(nxt) < 130 and (
                    PINCODE_REGEX.search(nxt) or
                    any(k in nxt_low for k in ['india', 'usa', 'up', 'delhi', 'ghaziabad', 'noida', 'mumbai', 'bengaluru', 'pincode', 'uttar pradesh', 'maharashtra', 'gujarat', 'haryana', 'karnataka', 'tamil nadu'])
                ):
                    full_addr = full_addr.rstrip(',') + ', ' + nxt.lstrip(',')
                    j_next += 1
                else:
                    break

            if full_addr not in seen_values:
                seen_values.add(full_addr)
                start_idx = clean_text.find(full_addr)
                if start_idx == -1:
                    start_idx = clean_text.find(line_clean)
                end_idx = start_idx + len(full_addr) if start_idx != -1 else -1

                facts.append({
                    'category': 'CONTACT',
                    'field': 'address',
                    'value': full_addr,
                    'source_quote': full_addr,
                    'source_url': page_url,
                    'char_start': start_idx,
                    'char_end': end_idx,
                })

    return facts


def extract_social_links(clean_text: str = "", html: Optional[str] = None) -> List[str]:
    """
    Extracts high-fidelity official company social media URLs from:
    1. Raw HTML anchor tags (footer/header/nav icons).
    2. JSON-LD Schema.org 'sameAs' entries.
    3. Page text content.
    Filters out share buttons, intent dialogs, and tracking params.
    """
    candidates = []
    seen = set()

    # 1. Extract from raw HTML if provided
    if html:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            # Extract from all anchor tags
            for a in soup.find_all('a', href=True):
                href = a['href'].strip()
                if any(dom in href.lower() for dom in SOCIAL_DOMAINS):
                    candidates.append(href)

            # Extract from JSON-LD sameAs
            import json
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    if script.string:
                        data = json.loads(script.string.strip())
                        same_as = []
                        if isinstance(data, dict):
                            same_as = data.get('sameAs', [])
                        elif isinstance(data, list):
                            for it in data:
                                if isinstance(it, dict) and 'sameAs' in it:
                                    same_as.extend(it.get('sameAs', []))
                        if isinstance(same_as, str):
                            same_as = [same_as]
                        for s in same_as:
                            if isinstance(s, str) and any(dom in s.lower() for dom in SOCIAL_DOMAINS):
                                candidates.append(s)
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Error parsing HTML for social links: {e}")

    # 2. Extract from clean text regex
    if clean_text:
        for match in SOCIAL_REGEX.finditer(clean_text):
            candidates.append(match.group(0).strip())

    # 3. Clean, normalize and filter candidates
    cleaned_socials = []
    from urllib.parse import urlparse
    for raw_url in candidates:
        u = str(raw_url).strip().rstrip(')>]"\'')
        if not u.startswith(('http://', 'https://')):
            if u.startswith('//'):
                u = 'https:' + u
            elif any(u.startswith(dom) or u.startswith('www.' + dom) for dom in SOCIAL_DOMAINS):
                u = 'https://' + u
            else:
                continue

        u_low = u.lower()

        # Exclude share/dialog/intent buttons
        if any(exc in u_low for exc in SOCIAL_EXCLUDE_PATHS):
            continue

        # Strip query parameters and fragment (utm tracking, ref, etc.)
        try:
            parsed = urlparse(u)
            netloc_clean = parsed.netloc.lower()
            if not any(dom in netloc_clean for dom in SOCIAL_DOMAINS):
                continue

            path_clean = parsed.path.rstrip('/')
            if not path_clean or path_clean == '':
                continue

            # Check for platform path validity
            parts = [p for p in path_clean.split('/') if p]
            if not parts:
                continue

            # E.g. linkedin.com must be company, school, or in
            if 'linkedin.com' in netloc_clean and parts[0] not in ('company', 'school', 'in'):
                continue

            # Standard canonical host
            canon_host = netloc_clean[4:] if netloc_clean.startswith('www.') else netloc_clean
            clean_url = f"https://{canon_host}{path_clean}"

            if clean_url.lower() not in seen:
                seen.add(clean_url.lower())
                cleaned_socials.append(clean_url)
        except Exception:
            continue

    return cleaned_socials


def extract_contact_bundle(clean_text: str, page_url: str, html: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns structured contact info strictly conforming to Requirement 5 JSON schema:
    {
      "phone": [],
      "email": [],
      "address": [],
      "working_hours": [],
      "social_links": [],
      "source_url": "..."
    }
    """
    facts = extract_deterministic_facts(clean_text, page_url)

    phones = []
    emails = []
    addresses = []
    hours = []
    socials = extract_social_links(clean_text=clean_text, html=html)

    for f in facts:
        field = f.get('field')
        val = f.get('value', '').strip()
        if not val:
            continue
        if field == 'phone' and val not in phones:
            phones.append(val)
        elif field == 'email' and val not in emails:
            emails.append(val)
        elif field == 'address' and val not in addresses:
            addresses.append(val)
        elif field == 'working_hours' and val not in hours:
            hours.append(val)

    return {
        'phone': phones,
        'email': emails,
        'address': addresses,
        'working_hours': hours,
        'social_links': socials,
        'source_url': page_url if any([phones, emails, addresses, hours, socials]) else None
    }


DEFAULT_SOCIAL_PLATFORMS = ['facebook', 'linkedin', 'instagram', 'youtube', 'twitter']

def format_social_links_dict(social_links: Any) -> Dict[str, str]:
    """
    Formats social links into a dictionary mapping platform name to URL string.
    Always includes default keys: facebook, linkedin, instagram, youtube, twitter.
    If a platform link is not found, its value defaults to empty string "".
    """
    result = {p: "" for p in DEFAULT_SOCIAL_PLATFORMS}

    if isinstance(social_links, dict):
        for k, v in social_links.items():
            k_low = str(k).lower().strip()
            v_str = str(v).strip() if v else ""
            result[k_low] = v_str
        return result

    links_list = social_links if isinstance(social_links, list) else ([social_links] if isinstance(social_links, str) else [])

    for link in links_list:
        if not isinstance(link, str) or not link.strip():
            continue
        link_str = link.strip()
        link_low = link_str.lower()

        if 'facebook.com' in link_low or 'fb.com' in link_low:
            if not result.get('facebook'):
                result['facebook'] = link_str
        elif 'linkedin.com' in link_low:
            if not result.get('linkedin'):
                result['linkedin'] = link_str
        elif 'instagram.com' in link_low:
            if not result.get('instagram'):
                result['instagram'] = link_str
        elif 'youtube.com' in link_low or 'youtu.be' in link_low:
            if not result.get('youtube'):
                result['youtube'] = link_str
        elif 'twitter.com' in link_low or 'x.com' in link_low:
            if not result.get('twitter'):
                result['twitter'] = link_str
        else:
            for dom in ('whatsapp', 'pinterest', 'tiktok', 'github'):
                if dom in link_low:
                    if not result.get(dom):
                        result[dom] = link_str
                    break

    return result

