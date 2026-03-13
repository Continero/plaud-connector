"""Plaud.ai API client."""

from __future__ import annotations

import random
from typing import Any
from urllib.parse import urlencode

import requests

DEFAULT_BASE_URL = "https://api.plaud.ai"

_BROWSER_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://app.plaud.ai",
    "Referer": "https://app.plaud.ai/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15"
    ),
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "app-platform": "web",
    "edit-from": "web",
}


class PlaudClient:
    """Client for the Plaud.ai REST API."""

    def __init__(
        self,
        email: str,
        password: str,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(_BROWSER_HEADERS)
        self._token: str | None = None
        self._authenticate(email, password)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _authenticate(self, email: str, password: str) -> None:
        resp = self._session.post(
            f"{self._base_url}/auth/access-token",
            data={"username": email, "password": password, "client_id": "web"},
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        self._session.headers.update({"Authorization": f"bearer {self._token}"})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Issue a GET with a cache-busting ``r`` parameter."""
        params = dict(params or {})
        params["r"] = random.random()
        qs = urlencode(params)
        url = f"{self._base_url}{path}?{qs}"
        resp = self._session.get(url)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Recordings
    # ------------------------------------------------------------------

    def list_recordings(self, limit: int = 200) -> list[dict[str, Any]]:
        """Return all non-trashed recordings, paginating automatically."""
        all_files: list[dict[str, Any]] = []
        skip = 0
        while True:
            data = self._get(
                "/file/simple/web",
                {
                    "skip": skip,
                    "limit": limit,
                    "is_trash": 0,
                    "sort_by": "start_time",
                    "is_desc": "true",
                },
            )
            page = data.get("data_file_list", [])
            all_files.extend(page)
            if len(page) < limit:
                break
            skip += limit
        return all_files

    def get_recording_details(
        self, file_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Fetch full details (transcript, AI content) for given file IDs."""
        resp = self._session.post(
            f"{self._base_url}/file/list?support_mul_summ=true",
            json=file_ids,
        )
        resp.raise_for_status()
        return resp.json().get("data_file_list", [])

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def get_tags(self) -> list[dict[str, Any]]:
        """Return all user tags."""
        data = self._get("/filetag/")
        return data.get("data_filetag_list", [])
