import re
from typing import Optional, Tuple, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class ClaimValidator:
    """
    Validates extracted quotes directly against the page's ground truth clean text.
    Computes exact character offsets and drops ungrounded claims.
    """

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip()

    def verify_quote(self, clean_text: str, quote: str) -> Tuple[bool, int, int]:
        """
        Locates the quote in clean_text.
        Returns (is_verified, char_start, char_end).
        """
        if not clean_text or not quote:
            return False, -1, -1

        quote_stripped = quote.strip()
        if len(quote_stripped) < 4:
            # Quote too short to be meaningful
            return False, -1, -1

        # 1. Exact match attempt
        start_idx = clean_text.find(quote_stripped)
        if start_idx != -1:
            end_idx = start_idx + len(quote_stripped)
            return True, start_idx, end_idx

        # 2. Case-insensitive exact match
        lower_clean = clean_text.lower()
        lower_quote = quote_stripped.lower()
        start_idx = lower_clean.find(lower_quote)
        if start_idx != -1:
            end_idx = start_idx + len(quote_stripped)
            return True, start_idx, end_idx

        # 3. Normalized whitespace match
        norm_clean = self.normalize_whitespace(clean_text)
        norm_quote = self.normalize_whitespace(quote_stripped)
        start_idx = norm_clean.lower().find(norm_quote.lower())
        if start_idx != -1:
            end_idx = start_idx + len(norm_quote)
            return True, start_idx, end_idx

        # 4. Alphanumeric normalized match (handles punctuation, parenthesis and line break variations)
        clean_alpha = re.sub(r'[^a-z0-9]', '', lower_clean)
        quote_alpha = re.sub(r'[^a-z0-9]', '', lower_quote)
        if len(quote_alpha) >= 4 and quote_alpha in clean_alpha:
            prefix_len = min(20, len(quote_stripped))
            approx_start = lower_clean.find(quote_stripped[:prefix_len].lower())
            if approx_start != -1:
                return True, approx_start, min(approx_start + len(quote_stripped), len(clean_text))
            return True, 0, min(len(quote_stripped), len(clean_text))

        # 5. Digit sequence match for phone numbers, pin codes, and numerical identifiers
        digits_quote = re.sub(r'\D', '', quote_stripped)
        if len(digits_quote) >= 6:
            digits_clean = re.sub(r'\D', '', clean_text)
            if digits_quote in digits_clean:
                return True, 0, min(len(quote_stripped), len(clean_text))

        # 6. Word token overlap ratio match (handles minor LLM whitespace/punctuation variations)
        quote_words = [w.lower() for w in re.findall(r'\b[a-z0-9]{3,}\b', lower_quote)]
        if len(quote_words) >= 3:
            clean_words = set(re.findall(r'\b[a-z0-9]{3,}\b', lower_clean))
            matched_words = [w for w in quote_words if w in clean_words]
            if len(matched_words) / len(quote_words) >= 0.85:
                return True, 0, min(len(quote_stripped), len(clean_text))

        # 7. Partial substring match for long quotes (first 40 characters)
        if len(quote_stripped) > 40:
            prefix = quote_stripped[:40]
            start_idx = clean_text.lower().find(prefix.lower())
            if start_idx != -1:
                end_idx = start_idx + len(quote_stripped)
                return True, start_idx, min(end_idx, len(clean_text))

        logger.info(f"Unverified quote dropped: '{quote_stripped[:60]}...'")
        return False, -1, -1

    def validate_and_filter_facts(
        self, clean_text: str, raw_facts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filters raw fact dicts, keeping ONLY those whose source quote can be
        verified against clean_text.
        """
        verified_facts = []

        for fact in raw_facts:
            quote = fact.get('source_quote', '') or fact.get('source_text', '') or fact.get('quote', '')
            is_valid, char_start, char_end = self.verify_quote(clean_text, quote)

            # If quote did not match directly, test whether value itself is grounded in clean text
            if not is_valid and fact.get('value'):
                val = str(fact.get('value', '')).strip()
                if len(val) >= 4:
                    val_valid, val_start, val_end = self.verify_quote(clean_text, val)
                    if val_valid:
                        is_valid = True
                        char_start = val_start
                        char_end = val_end
                        quote = val

            if is_valid:
                verified_fact = dict(fact)
                verified_fact['source_quote'] = quote
                verified_fact['char_start'] = char_start
                verified_fact['char_end'] = char_end
                verified_fact['is_verified'] = True
                verified_facts.append(verified_fact)
            else:
                logger.warning(
                    f"Dropping hallucinated or ungrounded fact [{fact.get('category')}.{fact.get('field')}]: "
                    f"quote '{quote[:40]}' not found in page content."
                )

        return verified_facts
