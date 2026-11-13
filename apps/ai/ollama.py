import httpx
import logging
from typing import Optional
from django.conf import settings
from .gateway import (
    LLMProvider,
    LLMUnavailableException,
    LLMTimeoutException,
    InvalidLLMResponseException,
)

logger = logging.getLogger(__name__)

class OllamaProvider(LLMProvider):
    """
    Production Ollama HTTP API client.
    """

    def __init__(self, base_url: Optional[str] = None):
        config = getattr(settings, 'WEBSITE_INTEL', {})
        self.base_url = (base_url or config.get('OLLAMA_BASE_URL', 'http://localhost:11434')).rstrip('/')

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.1,
        timeout: float = 60.0,
        num_predict: int = 800,
    ) -> str:
        config = getattr(settings, 'WEBSITE_INTEL', {})
        effective_timeout = timeout or config.get('LLM_TIMEOUT_SECONDS', 60.0)
        chosen_model = model or config.get('DEFAULT_FAST_MODEL', 'qwen2.5:1.5b')

        payload = {
            "model": chosen_model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
                "num_ctx": 2048,
                "num_thread": 8,
            }
        }

        if json_mode:
            payload["format"] = "json"

        endpoint = f"{self.base_url}/api/generate"

        try:
            with httpx.Client(timeout=effective_timeout) as client:
                response = client.post(endpoint, json=payload)
                if response.status_code != 200:
                    raise LLMUnavailableException(
                        f"Ollama API error {response.status_code}: {response.text}"
                    )

                data = response.json()
                raw_response = data.get("response", "")
                if not raw_response:
                    raise InvalidLLMResponseException("Empty response field from Ollama API.")

                return raw_response

        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to Ollama at {self.base_url}: {e}")
            raise LLMUnavailableException(f"Ollama daemon unreachable at {self.base_url}: {e}")
        except httpx.TimeoutException as e:
            logger.error(f"Ollama generation timed out after {timeout}s: {e}")
            raise LLMTimeoutException(f"Ollama model '{chosen_model}' timed out after {timeout}s: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in Ollama generation: {e}")
            raise LLMUnavailableException(f"Ollama call failed: {e}")

def get_default_llm_provider() -> LLMProvider:
    """Factory function for instantiating configured LLM provider."""
    provider_name = getattr(settings, 'WEBSITE_INTEL', {}).get('LLM_PROVIDER', 'ollama').lower()
    if provider_name == 'ollama':
        return OllamaProvider()
    # Extensible for OpenAI or other future providers
    return OllamaProvider()
