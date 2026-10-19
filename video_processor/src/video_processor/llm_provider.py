import os

import requests


def join_api_path(base_url: str, suffix: str) -> str:
    """Append ``suffix`` to an API base URL, tolerating a trailing slash."""
    return f"{base_url.rstrip('/')}/{suffix}"


class OpenAICompatibleLLMProvider(object):
    def __init__(self, base_url: str | None = None,
                    api_key: str | None = None) -> None:
        self.base_url = base_url
        self.api_key = api_key

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

        # First API call with reasoning
        response = requests.post(
          url=self._url,
          headers=self._headers,
          json={
            "model": model,
            "messages": messages,
            "reasoning": {"enabled": reasoning}
          }
        )

        # Extract the assistant message with reasoning_details
        response = response.json()
        return response['choices'][0]['message']
