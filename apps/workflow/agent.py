from typing import List, Optional, Dict, Any, Tuple
import logging
from apps.classifier.classifier import PageRanker

logger = logging.getLogger(__name__)

class CandidatePage:
    def __init__(
        self,
        url: str,
        normalized_url: str,
        page_type: str,
        confidence: float,
        location: str = "body",
        anchor_text: str = ""
    ):
        self.url = url
        self.normalized_url = normalized_url
        self.page_type = page_type
        self.confidence = confidence
        self.location = location
        self.anchor_text = anchor_text
        self.is_analysed = False

class AgentPlanner:
    """
    Bounded decision engine: evaluates collected facts, checks remaining budget,
    and determines whether to explore the next priority candidate page or finalize
    according to TargetExtractionConfig.
    """

    def __init__(self, objective: str = 'company_intelligence', target_config: Optional[Any] = None):
        self.objective = objective
        self.target_config = target_config

    def select_next_action(
        self,
        candidates: List[CandidatePage],
        analysed_urls: set,
        collected_categories: set,
        budget_exhausted: bool,
        attempted_urls: Optional[set] = None,
    ) -> Tuple[str, Optional[CandidatePage]]:
        """
        Determines the next action:
        - 'ANALYSE_PAGE': Inspect candidate
        - 'FINISH': Sufficient evidence gathered or no more candidates / budget exhausted
        """
        if budget_exhausted:
            logger.info("AgentPlanner: Budget exhausted. Decision -> FINISH")
            return 'FINISH', None

        # Filter out already attempted/analysed pages
        excluded = attempted_urls if attempted_urls is not None else analysed_urls
        unanalysed = [c for c in candidates if c.normalized_url not in excluded]
        if not unanalysed:
            logger.info("AgentPlanner: No unanalysed candidate pages remain. Decision -> FINISH")
            return 'FINISH', None

        # Filter strictly by eligibility if target_config defines specific target types/paths
        if self.target_config and (self.target_config.target_page_types or self.target_config.target_paths):
            eligible = [c for c in unanalysed if self.target_config.is_eligible(c.page_type, c.normalized_url)]
            if not eligible:
                logger.info("AgentPlanner: All eligible target pages analysed or none remain. Decision -> FINISH")
                return 'FINISH', None
            candidate_pool = eligible
        else:
            candidate_pool = unanalysed

        # Rank remaining candidates by relevance to objective and target configuration
        ranked = PageRanker.rank_candidates(
            candidate_pool,
            objective=self.objective,
            target_config=self.target_config
        )

        if not ranked:
            logger.info("AgentPlanner: No eligible candidates after ranking. Decision -> FINISH")
            return 'FINISH', None

        # Stop policy: evaluate target_config criteria
        if self.target_config:
            max_pages = self.target_config.max_pages
            min_pages = self.target_config.min_pages
            required_types = set(self.target_config.required_page_types)

            has_required = not required_types or any(req in collected_categories for req in required_types)

            if len(analysed_urls) >= max_pages:
                logger.info(f"AgentPlanner: Maximum target pages ({max_pages}) reached. Decision -> FINISH")
                return 'FINISH', None

            if len(analysed_urls) >= min_pages and has_required:
                # If top remaining candidate is not in explicit target types, stop
                target_types = set(self.target_config.target_page_types)
                if target_types and ranked[0].page_type not in target_types:
                    logger.info("AgentPlanner: Required and target pages satisfied. Decision -> FINISH")
                    return 'FINISH', None
        else:
            # Fallback legacy policy
            critical_categories = {'ABOUT', 'COMPANY'}
            has_core = any(cat in collected_categories for cat in critical_categories)
            if len(analysed_urls) >= 3 or (has_core and len(analysed_urls) >= 2):
                logger.info("AgentPlanner: Core intelligence collected from top candidate pages. Decision -> FINISH")
                return 'FINISH', None

        # Select highest-priority candidate
        next_candidate = ranked[0]
        logger.info(f"AgentPlanner: Next target selected: {next_candidate.page_type} -> {next_candidate.normalized_url}")
        return 'ANALYSE_PAGE', next_candidate
