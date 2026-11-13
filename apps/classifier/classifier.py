import re
from typing import Dict, Any, Tuple, Optional
from urllib.parse import urlparse

# Deterministic keywords mapped to PageTypes (supporting both space and hyphenated words)
PAGE_PATTERNS = {
    'ABOUT': [
        r'\babout\b', r'\babout[-_\s]us\b', r'\bwho[-_\s]we[-_\s]are\b',
        r'\bour[-_\s]story\b', r'\bcorporate[-_\s]profile\b', r'\bcompany[-_\s]profile\b',
        r'\bour[-_\s]company\b', r'\boverview\b', r'\bhistory\b', r'\bmission\b'
    ],
    'LEADERSHIP': [
        r'\bleadership\b', r'\bboard[-_\s]of[-_\s]directors\b', r'\bexecutives\b',
        r'\bmanagement\b', r'\bleaders\b', r'\bfounders\b'
    ],
    'TEAM': [
        r'\bteam\b', r'\bour[-_\s]team\b', r'\bpeople\b', r'\bstaff\b'
    ],
    'COMPANY': [
        r'\bcompany\b', r'\bcorporate\b', r'\borganization\b'
    ],
    'PRODUCT': [
        r'\bproducts\b', r'\bproduct\b', r'\bfeatures\b', r'\bplatform\b',
        r'\bsoftware\b', r'\bpricing\b', r'\bkits?\b', r'\bdevices?\b',
        r'\bequipment\b', r'\breagents?\b', r'\banalyzers?\b', r'\bconsumables\b'
    ],
    'SERVICE': [
        r'\bservices\b', r'\bservice\b', r'\bour[-_\s]services\b', r'\bconsulting\b',
        r'\bcapabilities\b', r'\btests\b', r'\btest[-_\s]menu\b', r'\bdiagnostics?\b',
        r'\bpathology\b', r'\blab[-_\s]tests?\b', r'\bclinical[-_\s]tests?\b',
        r'\bscreening\b', r'\bhealth[-_\s]packages?\b', r'\bpanels?\b', r'\bassays?\b',
        r'\bradiology\b', r'\bimaging\b', r'\bbiopsy\b'
    ],
    'SOLUTION': [
        r'\bsolutions\b', r'\bsolution\b', r'\buse[-_\s]cases\b', r'\benterprise\b'
    ],
    'INDUSTRY': [
        r'\bindustries\b', r'\bindustry\b', r'\bverticals\b', r'\bsectors\b'
    ],
    'CUSTOMER': [
        r'\bcustomers\b', r'\bclients\b', r'\btestimonials\b', r'\breviews\b'
    ],
    'CASE_STUDY': [
        r'\bcase[-_\s]studies\b', r'\bcase[-_\s]study\b', r'\bsuccess[-_\s]stories\b'
    ],
    'PARTNER': [
        r'\bpartners\b', r'\balliances\b', r'\becosystem\b', r'\baffiliates\b'
    ],
    'TECHNOLOGY': [
        r'\btechnology\b', r'\btech[-_\s]stack\b', r'\barchitecture\b', r'\bpatents\b',
        r'\bsecurity\b', r'\binnovation\b'
    ],
    'CAREERS': [
        r'\bcareers?\b', r'\bjobs?\b', r'\bjoin[-_\s]us\b', r'\bwork[-_\s]with[-_\s]us\b',
        r'\bhiring\b', r'\bopen[-_\s]positions?\b', r'\bopenings?\b'
    ],
    'CONTACT': [
        r'\bcontacts?\b', r'\bcontact[-_\s]us\b', r'\bget[-_\s]in[-_\s]touch\b',
        r'\breach[-_\s]us\b', r'\blocation\b', r'\boffices?\b', r'\bcontact[-_\s]support\b',
        r'\bhelpdesk\b', r'/support/?$'
    ],
    'PRESS': [
        r'\bpress\b', r'\bmedia\b', r'\bpress[-_\s]releases\b', r'\bnewsroom\b'
    ],
    'NEWS': [
        r'\bnews\b', r'\bannouncements\b', r'\bupdates\b'
    ],
    'BLOG': [
        r'\bblog\b', r'\barticles\b', r'\bposts\b', r'\binsights\b'
    ],
    'RESOURCE': [
        r'\bresources\b', r'\bwhitepapers\b', r'\bebooks\b', r'\bdocs\b', r'\bguides\b'
    ],
}

class PageClassifier:
    """
    Hybrid classifier combining deterministic heuristic pattern matching
    with fallback LLM classification for low-confidence candidate pages.
    """

    def classify_deterministic(
        self,
        url: str,
        anchor_text: str = "",
        title: str = "",
        h1: str = "",
    ) -> Tuple[str, float]:
        """
        Calculates category scores using URL path, anchor text, title, and H1.
        Returns (best_page_type, confidence_score).
        """
        scores: Dict[str, float] = {}

        parsed = urlparse(url)
        path_text = parsed.path.lower()
        anchor_clean = anchor_text.lower()
        title_clean = title.lower()
        h1_clean = h1.lower()

        # Check multi-word phrase patterns
        for p_type, patterns in PAGE_PATTERNS.items():
            score = 0.0
            for pat in patterns:
                # 1. URL Path match (high weight)
                if re.search(pat, path_text):
                    score += 0.50

                # 2. Anchor text match (high weight)
                if anchor_clean and re.search(pat, anchor_clean):
                    score += 0.40

                # 3. Title match
                if title_clean and re.search(pat, title_clean):
                    score += 0.30

                # 4. H1 match
                if h1_clean and re.search(pat, h1_clean):
                    score += 0.30

            if score > 0:
                # Specific types get precedence over general COMPANY if both match
                if p_type == 'ABOUT' and 'corporate' in path_text:
                    score += 0.2
                scores[p_type] = min(1.0, score)

        if not scores:
            return 'OTHER', 0.1

        best_type = max(scores, key=scores.get)
        return best_type, round(scores[best_type], 2)


class PageRanker:
    """
    Ranks candidate URLs according to their relevance to the analysis objective.
    """

    OBJECTIVE_PRIORITIES = {
        'company_intelligence': {
            'ABOUT': 100,
            'COMPANY': 90,
            'LEADERSHIP': 85,
            'TEAM': 75,
            'PRODUCT': 70,
            'SERVICE': 70,
            'SOLUTION': 65,
            'CONTACT': 60,
            'CAREERS': 50,
            'TECHNOLOGY': 45,
            'CUSTOMER': 40,
            'PRESS': 30,
            'OTHER': 10,
        },
        'product_analysis': {
            'PRODUCT': 100,
            'PRODUCT_DETAIL': 95,
            'SERVICE': 85,
            'SERVICE_DETAIL': 80,
            'SOLUTION': 80,
            'TECHNOLOGY': 75,
            'ABOUT': 60,
            'CUSTOMER': 55,
            'OTHER': 10,
        },
        'product_intelligence': {
            'PRODUCT': 100,
            'PRODUCT_DETAIL': 95,
            'SERVICE': 85,
            'SERVICE_DETAIL': 80,
            'SOLUTION': 80,
            'TECHNOLOGY': 75,
            'ABOUT': 60,
            'CUSTOMER': 55,
            'OTHER': 10,
        },
        'talent_recruitment': {
            'CAREERS': 100,
            'TEAM': 90,
            'ABOUT': 80,
            'CONTACT': 70,
            'COMPANY': 65,
            'LEADERSHIP': 60,
            'OTHER': 10,
        },
        'full_audit': {
            'ABOUT': 100,
            'COMPANY': 95,
            'PRODUCT': 90,
            'SERVICE': 85,
            'LEADERSHIP': 80,
            'TECHNOLOGY': 75,
            'CAREERS': 70,
            'CONTACT': 65,
            'OTHER': 10,
        },
        'lab_intelligence': {
            'ABOUT': 100,
            'CONTACT': 100,
            'SERVICE': 95,
            'PRODUCT': 95,
            'SERVICE_DETAIL': 90,
            'PRODUCT_DETAIL': 90,
            'COMPANY': 70,
            'LEADERSHIP': 50,
            'TECHNOLOGY': 40,
            'OTHER': 10,
        },
    }

    @classmethod
    def rank_candidates(
        cls,
        candidates: list,
        objective: str = 'company_intelligence',
        target_config: Optional[Any] = None
    ) -> list:
        """
        Sorts candidate page objects by their computed score, objective priority,
        and explicit TargetExtractionConfig preferences.
        """
        priority_map = cls.OBJECTIVE_PRIORITIES.get(
            objective, cls.OBJECTIVE_PRIORITIES['company_intelligence']
        )

        def compute_sort_key(candidate) -> float:
            p_type = getattr(candidate, 'page_type', 'OTHER')
            confidence = getattr(candidate, 'confidence', 0.5)
            location = getattr(candidate, 'location', 'body')
            url = getattr(candidate, 'normalized_url', '') or getattr(candidate, 'url', '')
            url_lower = url.lower()

            base_priority = priority_map.get(p_type, 10)

            # Target config boosts and demotions
            if target_config:
                if p_type in getattr(target_config, 'exclude_page_types', []):
                    return -100.0

                target_types = getattr(target_config, 'target_page_types', [])
                required_types = getattr(target_config, 'required_page_types', [])
                target_paths = getattr(target_config, 'target_paths', [])

                if p_type in required_types:
                    base_priority += 100
                elif target_types and p_type in target_types:
                    base_priority += 60
                elif target_types and p_type not in target_types:
                    # Demote non-target types when specific targets are requested
                    base_priority = 5

                # Path pattern matching boost
                if target_paths and any(p in url_lower for p in target_paths):
                    base_priority += 80

            # Nav/Header links get a structural boost
            location_boost = 1.2 if location in ('nav', 'header') else (1.1 if location == 'footer' else 1.0)

            return (base_priority * location_boost) + (confidence * 10)

        return sorted(candidates, key=compute_sort_key, reverse=True)
