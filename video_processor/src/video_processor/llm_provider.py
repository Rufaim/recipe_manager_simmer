import os
import time

import requests


def join_api_path(base_url: str, suffix: str) -> str:
    """Append ``suffix`` to an API base URL, tolerating a trailing slash."""
    return f"{base_url.rstrip('/')}/{suffix}"


class OpenAICompatibleLLMProvider(object):
    def __init__(self, base_url: str | None = None,
                    api_key: str | None = None,
                    timeout: tuple[int,int] | int = (10, 120), # connect, read — read is long: reasoning-enabled replies are slow
                    max_retries = 2,
                    retry_backoff_secs = 2
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_secs = retry_backoff_secs

    @property
    def _url(self) -> str:
        base_url = self.base_url
        if self.base_url is None:
            base_url = os.getenv("LLM_API_BASE_URL")
            if base_url is None:
                raise RuntimeError(
                    "No base URL configured. Pass 'base_url' to "
                    "OpenAICompatibleLLMProvider or set the 'LLM_API_BASE_URL'"
                    " environment variable."
                )

        return join_api_path(base_url, "v1/chat/completions")

    @property
    def _headers(self) -> dict[str, str]:
        api_key = self.api_key
        if self.api_key is None:
            api_key = os.getenv("LLM_API_KEY")
            if api_key is None:
                raise RuntimeError(
                    "No API key configured. Pass 'api_key' to "
                    "OpenAICompatibleLLMProvider or set the 'LLM_API_KEY'"
                    " environment variable."
                )

        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def make_request(self, messages: list[dict[str, str]], model: str | None = None, reasoning: bool = True):
        if model is None:
            model = os.getenv("LLM_MODEL_NAME")
            if model is None:
                raise RuntimeError(
                    "No model name specified. Pass 'model' to 'make_request' "
                    "or set the 'LLM_MODEL_NAME' environment variable."
                )

        payload = {
            "model": model,
            "messages": messages,
            "reasoning": {"enabled": reasoning},
        }

        delay = self.retry_backoff_secs
        for attempt in range(self.max_retries):
            if attempt > 0:
                time.sleep(delay)

            try:
                response = requests.post(
                    url=self._url,
                    headers=self._headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                # Timeout/connection errors are bounded and NOT retried: the provider
                # may have completed and billed the request anyway, so replaying
                # could duplicate work.
                raise RuntimeError(f"LLM API request failed: {exc}") from exc

            if response.ok:
                # Extract the assistant message with reasoning_details
                return response.json()["choices"][0]["message"]

            if response.status_code in (429, *range(500, 600)) and attempt < MAX_RETRIES-1:
                retry_after = response.headers.get("Retry-After")
                if retry_after is not None:
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        delay = self.retry_backoff_secs
                continue

            raise RuntimeError(
                f"LLM API returned HTTP {response.status_code}: {response.text[:500]}"
            )
