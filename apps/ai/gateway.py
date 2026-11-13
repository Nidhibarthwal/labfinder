from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import json
import re
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class LLMException(Exception):
    """Base exception for LLM operations."""
    pass

class LLMUnavailableException(LLMException):
    """Raised when LLM daemon or endpoint is unreachable."""
    pass

class LLMTimeoutException(LLMException):
    """Raised when LLM generation times out."""
    pass

class InvalidLLMResponseException(LLMException):
    """Raised when LLM response cannot be parsed according to schema."""
    pass

class LLMProvider(ABC):
    """Abstract interface for LLM operations."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.1,
        timeout: float = 45.0,
        num_predict: int = 800,
    ) -> str:
        """Generates text from the underlying LLM provider."""
        pass


class ModelRouter:
    """
    Directs tasks to appropriate models based on latency and complexity requirements.
    """

    def __init__(self):
        config = getattr(settings, 'WEBSITE_INTEL', {})
        self.fast_model = config.get('DEFAULT_FAST_MODEL', 'qwen2.5:1.5b')
        self.synthesis_model = config.get('DEFAULT_SYNTHESIS_MODEL', 'mistral:latest')

    def get_model_for_task(self, task: str) -> str:
        if task in ('classification', 'extraction', 'entity_lookup'):
            return self.fast_model
        elif task in ('synthesis', 'conflict_detection', 'complex_reasoning'):
            return self.synthesis_model
        return self.fast_model


def parse_json_safely(raw_text: str) -> Dict[str, Any]:
    """
    Robustly extracts and parses JSON even if wrapped in markdown codeblocks
    or truncated before closing braces.
    """
    if not raw_text:
        raise InvalidLLMResponseException("LLM returned an empty response.")

    text = raw_text.strip()

    # If codeblock present, extract contents
    if '```' in text:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            text = match.group(1).strip()

    # Attempt direct JSON parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt finding the outermost JSON object { ... }
    match = re.search(r'(\{[\s\S]*\})', text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Recovery: Attempt repairing unclosed or truncated JSON
    start_idx = text.find('{')
    if start_idx != -1:
        candidate = text[start_idx:]
        for i in range(len(candidate), 10, -1):
            chunk = candidate[:i].rstrip()
            if chunk.endswith(','):
                chunk = chunk[:-1].rstrip()
            open_sq = chunk.count('[') - chunk.count(']')
            open_cr = chunk.count('{') - chunk.count('}')
            if open_sq >= 0 and open_cr >= 0:
                repaired = chunk + (']' * open_sq) + ('}' * open_cr)
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    continue

    raise InvalidLLMResponseException("No valid JSON structure found in LLM response.")
