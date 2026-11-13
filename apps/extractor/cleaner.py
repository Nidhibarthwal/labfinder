from bs4 import BeautifulSoup, Comment
import re
from typing import Dict, Any, Optional

BOILERPLATE_TAGS = [
    'script', 'style', 'noscript', 'svg', 'canvas', 'iframe', 'dialog'
]

BOILERPLATE_CLASSES_OR_IDS = [
    'cookie', 'consent', 'banner', 'modal', 'popup', 'newsletter',
    'subscription', 'ad-', 'ads', 'advertisement', 'social-share',
    'share-bar', 'disclaimer'
]

class ExtractedContent:
    def __init__(
        self,
        title: str,
        clean_text: str,
        headings: Dict[str, list],
        html_length: int,
        text_length: int,
        word_count: int,
        quality_score: float,
    ):
        self.title = title
        self.clean_text = clean_text
        self.headings = headings
        self.html_length = html_length
        self.text_length = text_length
        self.word_count = word_count
        self.quality_score = quality_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            'title': self.title,
            'clean_text': self.clean_text,
            'headings': self.headings,
            'html_length': self.html_length,
            'text_length': self.text_length,
            'word_count': self.word_count,
            'quality_score': self.quality_score,
        }

def decode_cloudflare_email(encoded_hex: str) -> str:
    """Decodes Cloudflare email obfuscation hex strings."""
    try:
        k = int(encoded_hex[:2], 16)
        return ''.join([chr(int(encoded_hex[i:i+2], 16) ^ k) for i in range(2, len(encoded_hex), 2)])
    except Exception:
        return ''

class ContentExtractor:
    """
    Cleans raw HTML, extracts structured headings and body text, and calculates quality.
    """

    def extract(self, html: str) -> ExtractedContent:
        if not html or not html.strip():
            return ExtractedContent(
                title="",
                clean_text="",
                headings={'h1': [], 'h2': [], 'h3': []},
                html_length=0,
                text_length=0,
                word_count=0,
                quality_score=0.0
            )

        html_length = len(html)
        soup = BeautifulSoup(html, 'html.parser')

        # De-obfuscate Cloudflare protected email tags
        for cf_tag in soup.find_all(attrs={'data-cfemail': True}):
            encoded = cf_tag.get('data-cfemail')
            if encoded:
                decoded = decode_cloudflare_email(encoded)
                if decoded:
                    cf_tag.string = decoded

        # 1. Extract title
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else ""

        # 2. Extract Headings before stripping
        headings = {
            'h1': [h.get_text(separator=' ', strip=True) for h in soup.find_all('h1')],
            'h2': [h.get_text(separator=' ', strip=True) for h in soup.find_all('h2')],
            'h3': [h.get_text(separator=' ', strip=True) for h in soup.find_all('h3')],
        }

        # 3. Strip comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # 4. Strip boilerplate tags
        for tag in soup.find_all(BOILERPLATE_TAGS):
            tag.decompose()

        # 5. Strip elements with cookie/ad/popup class or id
        for el in list(soup.find_all(True)):
            if getattr(el, 'decomposed', False):
                continue
            attrs = getattr(el, 'attrs', None)
            if not isinstance(attrs, dict):
                continue

            classes_val = attrs.get('class', [])
            el_classes = " ".join(classes_val).lower() if isinstance(classes_val, list) else str(classes_val).lower()
            el_id = str(attrs.get('id', '')).lower()

            for keyword in BOILERPLATE_CLASSES_OR_IDS:
                if keyword in el_classes or keyword in el_id:
                    el.decompose()
                    break

        # 6. Prefer main/article if present and rich
        main_tag = soup.find(['main', 'article'])
        content_root = main_tag if main_tag and len(main_tag.get_text(strip=True)) > 200 else soup

        # 7. Extract cleaned text with normalized whitespace
        raw_text = content_root.get_text(separator='\n', strip=True)
        # Collapse excessive newlines and whitespace
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)

        text_length = len(clean_text)
        word_count = len(clean_text.split())

        # 8. Compute quality score (0.0 to 1.0)
        quality_score = self._calculate_quality(html_length, text_length, word_count, headings)

        return ExtractedContent(
            title=title,
            clean_text=clean_text,
            headings=headings,
            html_length=html_length,
            text_length=text_length,
            word_count=word_count,
            quality_score=quality_score
        )

    def _calculate_quality(
        self, html_len: int, text_len: int, words: int, headings: Dict[str, list]
    ) -> float:
        if text_len == 0 or html_len == 0:
            return 0.0

        score = 0.0

        # Word count contribution (up to 0.4)
        if words >= 300:
            score += 0.4
        elif words >= 100:
            score += 0.3
        elif words >= 40:
            score += 0.15
        else:
            score += 0.05

        # Text density contribution (text_len / html_len) (up to 0.3)
        density = text_len / max(html_len, 1)
        if density >= 0.15:
            score += 0.3
        elif density >= 0.05:
            score += 0.2
        elif density >= 0.01:
            score += 0.1

        # Heading structure contribution (up to 0.3)
        h1_count = len(headings.get('h1', []))
        h2_count = len(headings.get('h2', []))
        if h1_count >= 1 and h2_count >= 1:
            score += 0.3
        elif h1_count >= 1 or h2_count >= 1:
            score += 0.2
        else:
            score += 0.05

        return min(1.0, round(score, 2))
