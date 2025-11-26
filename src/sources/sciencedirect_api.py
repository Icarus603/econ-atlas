from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, cast

import httpx

LOGGER = logging.getLogger(__name__)
DEFAULT_BASE_URL = "https://api.elsevier.com/content/article/pii/"


class ScienceDirectApiError(RuntimeError):
    """Raise when Elsevier API calls fail."""

    def __init__(self, message: str, *, recoverable: bool = False):
        super().__init__(message)
        self.recoverable = recoverable


@dataclass(frozen=True)
class ElsevierApiConfig:
    api_key: str
    inst_token: str | None = None
    base_url: str = DEFAULT_BASE_URL
    timeout: float = 15.0
    max_retries: int = 3
    backoff_seconds: float = 1.0


class ScienceDirectApiClient:
    """Thin wrapper around Elsevier Article Retrieval API."""

    def __init__(self, config: ElsevierApiConfig) -> None:
        self._config = config
        self._client = httpx.Client(timeout=config.timeout)

    def close(self) -> None:
        self._client.close()

    def fetch_by_pii(self, pii: str) -> dict[str, Any]:
        url = self._config.base_url.rstrip("/") + "/" + pii
        headers = self._build_headers()
        params = {"httpAccept": "application/json"}
        for attempt in range(1, self._config.max_retries + 1):
            response = self._client.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return cast(dict[str, Any], response.json())
            if response.status_code in {401, 403}:
                raise ScienceDirectApiError("Elsevier API rejected the request (check API key / insttoken)")
            if response.status_code == 404:
                raise ScienceDirectApiError("ScienceDirect PII not found")
            if response.status_code == 429 or response.status_code >= 500:
                delay = min(self._config.backoff_seconds * (2 ** (attempt - 1)), 30)
                LOGGER.warning(
                    "Elsevier API %s %s; retrying in %.1fs", response.status_code, response.text[:120], delay
                )
                time.sleep(delay)
                continue
            raise ScienceDirectApiError(
                f"Elsevier API error {response.status_code}: {response.text[:200]}", recoverable=False
            )
        raise ScienceDirectApiError("Elsevier API exhausted retries", recoverable=True)

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "X-ELS-APIKey": self._config.api_key,
            "Accept": "application/json",
        }
        if self._config.inst_token:
            headers["X-ELS-Insttoken"] = self._config.inst_token
        return headers
