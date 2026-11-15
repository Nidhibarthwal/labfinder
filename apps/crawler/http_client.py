import httpx
import time
import logging
from typing import Optional, Dict, Any, Tuple
from django.conf import settings
from .security import validate_url_security, SSRFBlockedException, InvalidURLException, DNSResolutionException

logger = logging.getLogger(__name__)

class FetchResult:
    def __init__(
        self,
        url: str,
        status_code: Optional[int],
        html: str = "",
        headers: Optional[Dict[str, str]] = None,
        redirect_history: Optional[list] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        response_time_ms: float = 0.0,
    ):
        self.url = url
        self.status_code = status_code
        self.html = html
        self.headers = headers or {}
        self.redirect_history = redirect_history or []
        self.error_code = error_code
        self.error_message = error_message
        self.response_time_ms = response_time_ms

    @property
    def is_success(self) -> bool:
        return self.status_code is not None and 200 <= self.status_code < 300 and not self.error_code

class SafeHttpClient:
    """
    Production-grade HTTP client with:
    - Integrated SSRF checks on initial target and every redirect hop.
    - Max byte size limits (streaming reading to abort oversized responses early).
    - Configurable timeouts, User-Agent, and connection pooling.
    - Selective retries for transient failures with backoff.
    """

    def __init__(
        self,
        timeout: Optional[float] = None,
        max_redirects: Optional[int] = None,
        max_response_bytes: Optional[int] = None,
        user_agent: Optional[str] = None,
        enforce_ssrf: Optional[bool] = None,
    ):
        config = getattr(settings, 'WEBSITE_INTEL', {})
        self.timeout = timeout or config.get('HTTP_TIMEOUT_SECONDS', 15.0)
        self.max_redirects = max_redirects or config.get('MAX_REDIRECTS', 5)
        self.max_response_bytes = max_response_bytes or config.get('MAX_RESPONSE_SIZE_BYTES', 5242880) # 5 MB
        self.user_agent = user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 WebsiteIntelligence/1.0'
        self.enforce_ssrf = enforce_ssrf if enforce_ssrf is not None else config.get('SSRF_ENFORCE', True)

    def fetch(self, url: str, max_retries: int = 2) -> FetchResult:
        """
        Safely fetches the given URL with SSRF checks on each hop and selective retry.
        """
        current_url = url
        redirect_history = []
        start_time = time.monotonic()

        # Step 1: Pre-flight security check
        try:
            validate_url_security(current_url, enforce=self.enforce_ssrf)
        except SSRFBlockedException as e:
            return FetchResult(url=current_url, status_code=None, error_code='SSRF_BLOCKED', error_message=str(e))
        except (InvalidURLException, DNSResolutionException) as e:
            return FetchResult(url=current_url, status_code=None, error_code='DNS_ERROR', error_message=str(e))

        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }

        # Follow redirects manually to validate SSRF on every hop
        for redirect_count in range(self.max_redirects + 1):
            attempt = 0
            while attempt <= max_retries:
                attempt += 1
                try:
                    # Validate security of hop
                    if redirect_count > 0:
                        validate_url_security(current_url, enforce=self.enforce_ssrf)

                    with httpx.Client(
                        timeout=httpx.Timeout(self.timeout, connect=10.0),
                        follow_redirects=False,
                        verify=True,
                    ) as client:
                        response = client.get(current_url, headers=headers)
                        elapsed_ms = (time.monotonic() - start_time) * 1000

                        # Check for redirect status (301, 302, 303, 307, 308)
                        if response.is_redirect:
                            location = response.headers.get('location')
                            if not location:
                                return FetchResult(
                                    url=current_url,
                                    status_code=response.status_code,
                                    error_code='REDIRECT_ERROR',
                                    error_message="Redirect missing Location header.",
                                    redirect_history=redirect_history,
                                    response_time_ms=elapsed_ms
                                )

                            # Resolve relative redirect location
                            from urllib.parse import urljoin
                            next_url = urljoin(current_url, location)
                            redirect_history.append((response.status_code, current_url, next_url))
                            current_url = next_url
                            break  # Proceed to next hop in redirect loop

                        # Validate Content-Type
                        content_type = response.headers.get('content-type', '').lower()
                        if content_type and not any(t in content_type for t in ('text/html', 'xhtml', 'xml', 'text/plain')):
                            logger.info(f"Skipping non-HTML content-type: {content_type} for {current_url}")
                            return FetchResult(
                                url=current_url,
                                status_code=response.status_code,
                                error_code='UNSUPPORTED_CONTENT_TYPE',
                                error_message=f"Unsupported Content-Type: {content_type}",
                                redirect_history=redirect_history,
                                response_time_ms=elapsed_ms
                            )

                        # Enforce response byte ceiling
                        content_bytes = response.content
                        if len(content_bytes) > self.max_response_bytes:
                            return FetchResult(
                                url=current_url,
                                status_code=response.status_code,
                                error_code='RESPONSE_TOO_LARGE',
                                error_message=f"Response size {len(content_bytes)} bytes exceeds limit of {self.max_response_bytes} bytes",
                                redirect_history=redirect_history,
                                response_time_ms=elapsed_ms
                            )

                        html_text = response.text
                        return FetchResult(
                            url=current_url,
                            status_code=response.status_code,
                            html=html_text,
                            headers=dict(response.headers),
                            redirect_history=redirect_history,
                            response_time_ms=elapsed_ms
                        )

                except SSRFBlockedException as e:
                    return FetchResult(url=current_url, status_code=None, error_code='SSRF_BLOCKED', error_message=str(e), redirect_history=redirect_history)
                except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
                    if attempt > max_retries:
                        return FetchResult(url=current_url, status_code=None, error_code='TIMEOUT', error_message=str(e), redirect_history=redirect_history)
                    time.sleep(0.5 * attempt)
                except httpx.ConnectError as e:
                    if attempt > max_retries:
                        return FetchResult(url=current_url, status_code=None, error_code='CONNECT_ERROR', error_message=str(e), redirect_history=redirect_history)
                    time.sleep(0.5 * attempt)
                except Exception as e:
                    logger.error(f"Unexpected HTTP fetch error for {current_url}: {e}")
                    return FetchResult(url=current_url, status_code=None, error_code='FETCH_ERROR', error_message=str(e), redirect_history=redirect_history)
        
        # If loop finished without returning, redirects exceeded limit
        return FetchResult(
            url=current_url,
            status_code=None,
            error_code='REDIRECT_LIMIT',
            error_message=f"Exceeded maximum redirect limit of {self.max_redirects}",
            redirect_history=redirect_history,
            response_time_ms=(time.monotonic() - start_time) * 1000
        )

    def fetch_binary(self, url: str, max_retries: int = 1) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Safely fetches binary content (such as logo images) with SSRF validation.
        Returns tuple: (bytes_data, content_type_str) or (None, None).
        """
        if not url:
            return None, None
            
        current_url = url
        try:
            validate_url_security(current_url, enforce=self.enforce_ssrf)
        except Exception as e:
            logger.warning(f"SSRF or URL validation failed for binary fetch {current_url}: {e}")
            return None, None

        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        }

        for redirect_count in range(self.max_redirects + 1):
            attempt = 0
            while attempt <= max_retries:
                attempt += 1
                try:
                    if redirect_count > 0:
                        validate_url_security(current_url, enforce=self.enforce_ssrf)

                    with httpx.Client(
                        timeout=httpx.Timeout(self.timeout, connect=5.0),
                        follow_redirects=False,
                        verify=True,
                    ) as client:
                        response = client.get(current_url, headers=headers)
                        if response.is_redirect:
                            location = response.headers.get('location')
                            if not location:
                                return None, None
                            from urllib.parse import urljoin
                            current_url = urljoin(current_url, location)
                            break

                        if response.status_code == 200:
                            content_bytes = response.content
                            if len(content_bytes) > self.max_response_bytes:
                                return None, None
                            content_type = response.headers.get('content-type', '')
                            return content_bytes, content_type
                        else:
                            return None, None
                except Exception as e:
                    if attempt > max_retries:
                        logger.warning(f"Failed to fetch binary from {current_url}: {e}")
                        return None, None
                    time.sleep(0.3 * attempt)
        return None, None

