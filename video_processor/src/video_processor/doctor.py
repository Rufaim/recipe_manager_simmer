"""One-shot validation of the environment the pipeline needs."""

import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from enum import StrEnum
from pathlib import Path
from typing import Self
from urllib.parse import urlparse

import requests
from dotenv import find_dotenv

from .llm_provider import join_api_path


class CheckStatus(StrEnum):
    PENDING = "pending"
    SKIPPED = "skip"
    OK = "ok"
    WARNING = "warn"
    ERROR = "fail"


class Check(ABC):
    def __init__(self, name: str):
        self.name = name
        self.status: CheckStatus = CheckStatus.PENDING
        self.details = None

    def ok(self) -> bool:
        return self.status is CheckStatus.OK

    def error(self) -> bool:
        return self.status is CheckStatus.ERROR

    def set_skip(self):
        self.status = CheckStatus.SKIPPED
        self.details = ""

    @abstractmethod
    def __call__(self) -> Self:
        raise NotImplementedError


class DotenvCheck(Check):
    def __init__(self) -> None:
        super().__init__(name=".env")

    def __call__(self):
        path = find_dotenv()
        if len(path) == 0:
            self.status = CheckStatus.WARNING
            self.details = "not found, relying on the shell environment"
        else:
            self.status = CheckStatus.OK
            self.details = path
        return self


class YT_DLPCheck(Check):
    def __init__(self, timeout: int = 10) -> None:
        super().__init__(name="yt-dlp")
        self.timeout = timeout

    def __call__(self):
        path = os.getenv("YT_DLP_PATH")
        if path is None or len(path) == 0:
            self.status = CheckStatus.ERROR
            self.details = "YT_DLP_PATH is not set (download the yt-dlp binary and set YT_DLP_PATH to it)"
            return self

        binary = Path(path)
        if not binary.is_file():
            self.status = CheckStatus.ERROR
            self.details = f"{binary} is not a file"
            return self
        if not os.access(binary, os.X_OK):
            self.status = CheckStatus.ERROR
            self.details = f"{binary} is not executable (hint: chmod +x {binary} )"
            return self

        try:
            result = subprocess.run([str(binary), "--version"], capture_output=True,
                                    text=True, timeout=self.timeout, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            self.status = CheckStatus.ERROR
            self.details = f"{binary} does not run as yt-dlp: {exc}"
            return self
        self.status = CheckStatus.OK
        self.details = f"{binary} (version {result.stdout.strip()})"
        return self


class LLMEnvVarModelNameCheck(Check):
    def __init__(self) -> None:
        super().__init__(name="LLM_MODEL_NAME")

    def __call__(self):
        value = os.getenv(self.name)
        if value is None or len(value) == 0:
            self.status = CheckStatus.ERROR
            self.details = "not set"
            return self
        self.status = CheckStatus.OK
        self.details = value
        return self


class LLMEnvVarBaseUrlCheck(Check):
    def __init__(self) -> None:
        super().__init__(name="LLM_API_BASE_URL")

    def __call__(self):
        value = os.getenv(self.name)
        if value is None or len(value) == 0:
            self.status = CheckStatus.ERROR
            self.details = "not set"
            return self

        # Any prefix path is valid for a provider ("/api", "", "/gateway"), what breaks
        # the client is pasting the endpoint path that llm_provider._url appends itself.
        if urlparse(value).path.rstrip("/").endswith(("/v1", "/chat/completions")):
            self.status = CheckStatus.WARNING
            self.details = f"'{value}' already includes an endpoint path; v1/chat/completions \
is appended to the base URL (keep it at the API root, commonly \"https://<domain>/api\")"
            return self
        self.status = CheckStatus.OK
        self.details = value
        return self


class LLMEnvVarAPIKeyCheck(Check):
    def __init__(self) -> None:
        super().__init__(name="LLM_API_KEY")

    def __call__(self):
        value = os.getenv(self.name)
        if value is None or len(value) == 0:
            self.status = CheckStatus.ERROR
            self.details = "not set"
            return self
        self.status = CheckStatus.OK
        self.details = "set"
        return self


class LLMEndpointCheck(Check):
    def __init__(self, timeout: int = 10) -> None:
        super().__init__(name="LLM endpoint")
        self.timeout = timeout

    def __call__(self):
        key, base, model = (os.getenv(var) for var in ["LLM_API_KEY", "LLM_API_BASE_URL", "LLM_MODEL_NAME"])
        url = join_api_path(base, "v1/models")

        try:
            response = requests.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=self.timeout)
        except requests.RequestException as exc:
            self.status = CheckStatus.ERROR
            self.details = f"{url} not reachable ({type(exc).__name__}), check LLM_API_BASE_URL"
            return self

        if response.status_code in (401, 403):
            self.status = CheckStatus.ERROR
            self.details = f"API key rejected (HTTP {response.status_code}), check LLM_API_KEY"
            return self
        if not response.ok:
            self.status = CheckStatus.WARNING
            self.details = f"reached {url} but got HTTP {response.status_code}, auth not verified"
            return self

        try:
            entries = response.json().get("data", [])
        except (ValueError, AttributeError):
            entries = []
        ids = {entry.get("id") for entry in entries}
        if ids and model not in ids:
            self.status = CheckStatus.WARNING
            self.details = f"key accepted, but '{model}' is not in the models list (check LLM_MODEL_NAME)"
            return self
        self.status = CheckStatus.OK
        self.details = f"{url} reachable, key accepted"
        return self


def run_doctor(timeout: int = 10) -> list[Check]:
    ind_checks_fns = [
        DotenvCheck(),
        YT_DLPCheck(timeout=timeout)
    ]
    llm_checks_fns = [
        LLMEnvVarModelNameCheck(),
        LLMEnvVarBaseUrlCheck(),
        LLMEnvVarAPIKeyCheck()
    ]
    llm_endpoint_check_fn = LLMEndpointCheck(timeout=timeout)

    out = [check() for check in ind_checks_fns]
    llm_vars_check_results = [check() for check in llm_checks_fns]
    out.extend(llm_vars_check_results)
    if all(r.ok() for r in llm_vars_check_results):
        llm_endpoint_check_fn()
    else:
        llm_endpoint_check_fn.set_skip()
    out.append(llm_endpoint_check_fn)

    return out
