from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .utils import ReconcileError

SECURITY_API_BASE = "/_plugins/_security/api"


def security_collection_path(resource: str) -> str:
    return f"{SECURITY_API_BASE}/{resource}/"


def security_item_path(resource: str, name: str) -> str:
    return f"{SECURITY_API_BASE}/{resource}/{name}"


class OpenSearchAPI:
    def __init__(
        self,
        base_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        verify: bool | str | Path = True,
        client_cert: Optional[str | Path] = None,
        client_key: Optional[str | Path] = None,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "PUT", "POST", "DELETE", "HEAD", "PATCH"),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        if username is not None:
            self.session.auth = (username, password or "")

        self.verify = str(verify) if isinstance(verify, Path) else verify

        self.cert = None
        if client_cert and client_key:
            cert_value = str(client_cert) if isinstance(client_cert, Path) else client_cert
            key_value = str(client_key) if isinstance(client_key, Path) else client_key
            self.cert = (cert_value, key_value)
        elif client_cert:
            self.cert = str(client_cert) if isinstance(client_cert, Path) else client_cert

        self.session.headers.update({"Content-Type": "application/json"})

    def _url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.base_url}{path}"

    def request(self, method: str, path: str, expected: Iterable[int] = (200,), **kwargs: Any) -> requests.Response:
        url = self._url(path)
        try:
            resp = self.session.request(
                method=method,
                url=url,
                timeout=self.timeout,
                verify=self.verify,
                cert=self.cert,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ReconcileError(f"{method} {url} failed: {exc}") from exc

        if resp.status_code not in set(expected):
            raise ReconcileError(
                f"{method} {url} failed: HTTP {resp.status_code} - {resp.text[:1000]}"
            )
        return resp

    def get_json(self, path: str, expected: Iterable[int] = (200,)) -> Dict[str, Any]:
        resp = self.request("GET", path, expected=expected)
        if not resp.text.strip():
            return {}
        return resp.json()

    def put_json(self, path: str, payload: Dict[str, Any], expected: Iterable[int] = (200, 201)) -> Dict[str, Any]:
        resp = self.request("PUT", path, expected=expected, data=json.dumps(payload))
        return resp.json() if resp.text.strip() else {}

    def post_json(self, path: str, payload: Dict[str, Any], expected: Iterable[int] = (200, 201)) -> Dict[str, Any]:
        resp = self.request("POST", path, expected=expected, data=json.dumps(payload))
        return resp.json() if resp.text.strip() else {}

    def delete(self, path: str, expected: Iterable[int] = (200, 202)) -> Dict[str, Any]:
        resp = self.request("DELETE", path, expected=expected)
        return resp.json() if resp.text.strip() else {}

    def head(self, path: str, expected: Iterable[int] = (200, 404)) -> int:
        resp = self.request("HEAD", path, expected=expected)
        return resp.status_code