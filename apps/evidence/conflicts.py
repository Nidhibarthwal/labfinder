from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class ConflictDetector:
    """
    Identifies contradictory facts extracted across different pages.
    """

    # Key fields where conflicts are critical
    CRITICAL_SINGLETON_FIELDS = {
        'founded_year', 'founded', 'established', 'headquarters', 'hq',
        'ceo', 'founder', 'founders', 'revenue', 'employees_count', 'employee_count'
    }

    def detect_conflicts(self, facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Groups facts by (category, field) and compares values from distinct source pages.
        """
        grouped: Dict[str, List[Dict[str, Any]]] = {}

        for fact in facts:
            field = str(fact.get('field', '')).strip().lower()
            category = str(fact.get('category', '')).strip().lower()
            key = f"{category}.{field}" if category else field

            if key not in grouped:
                grouped[key] = []
            grouped[key].append(fact)

        conflicts = []

        for key, fact_list in grouped.items():
            if len(fact_list) < 2:
                continue

            field_name = fact_list[0].get('field', key)
            is_critical = field_name.lower() in self.CRITICAL_SINGLETON_FIELDS

            # Collect distinct values
            value_sources: Dict[str, List[str]] = {}
            for f in fact_list:
                val = str(f.get('value', '')).strip()
                source_url = f.get('source_url', 'unknown')
                if val:
                    if val not in value_sources:
                        value_sources[val] = []
                    value_sources[val].append(source_url)

            # If more than 1 distinct value for critical fields (or substantial difference)
            if len(value_sources) > 1 and is_critical:
                logger.info(f"Conflict detected for field '{field_name}': {list(value_sources.keys())}")
                conflicts.append({
                    'field': field_name,
                    'conflict': True,
                    'competing_values': [
                        {'value': val, 'sources': list(set(sources))}
                        for val, sources in value_sources.items()
                    ],
                    'description': f"Contradictory values found for {field_name} across analysed pages."
                })

        return conflicts
