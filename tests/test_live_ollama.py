import pytest
import httpx
from apps.ai.ollama import OllamaProvider
from apps.ai.gateway import parse_json_safely

@pytest.mark.django_db
class TestLiveOllama:
    """
    Live integration test running against the local Ollama instance on http://localhost:11434.
    """

    def test_live_ollama_qwen_json_generation(self):
        # Verify Ollama is reachable
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get("http://localhost:11434/api/tags")
                if res.status_code != 200:
                    pytest.skip("Local Ollama not reachable")
        except Exception:
            pytest.skip("Local Ollama not reachable")

        provider = OllamaProvider()
        test_prompt = """
        Extract the company name and year from this text:
        "Stripe was founded in 2010 by Patrick and John Collison."

        Return JSON format:
        {"company": "...", "year": 2010}
        """

        raw_output = provider.generate(
            prompt=test_prompt,
            system_prompt="You are a data extractor. Return JSON only.",
            model="qwen2.5:1.5b",
            json_mode=True,
            temperature=0.0,
            timeout=30.0
        )

        assert raw_output is not None
        parsed = parse_json_safely(raw_output)
        assert "company" in parsed or "year" in parsed
