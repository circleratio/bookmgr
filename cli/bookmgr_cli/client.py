from __future__ import annotations

import httpx


class APIError(Exception):
    """Raised when the server responds with a non-2xx status and a
    {"error": {"code", "message"}} body."""

    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message} (status {status_code})")


class Client:
    """A client for bookmgr's REST API (/api/*), authenticating via the
    X-API-Key header. Mirrors internal/apiclient's Go client 1:1."""

    def __init__(self, base_url: str, api_key: str, transport: httpx.BaseTransport | None = None):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._http = httpx.Client(timeout=10.0, transport=transport)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def _request(self, method: str, path: str, *, json_body=None, params=None):
        resp = self._http.request(
            method,
            self._base_url + path,
            json=json_body,
            params=params,
            headers={"X-API-Key": self._api_key},
        )
        if resp.status_code >= 300:
            body: dict = {}
            try:
                body = resp.json()
            except ValueError:
                pass
            error = body.get("error") or {}
            raise APIError(resp.status_code, error.get("code", ""), error.get("message", ""))
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def list(self, q: str = "", page: int = 0, page_size: int = 0) -> tuple[list[dict], dict]:
        params = {}
        if q:
            params["q"] = q
        if page:
            params["page"] = page
        if page_size:
            params["page_size"] = page_size
        body = self._request("GET", "/api/books", params=params)
        return body["data"], body["pagination"]

    def get(self, book_id: int) -> dict:
        return self._request("GET", f"/api/books/{book_id}")["data"]

    def create(self, input: dict) -> dict:
        return self._request("POST", "/api/books", json_body=input)["data"]

    def update(self, book_id: int, input: dict) -> dict:
        return self._request("PUT", f"/api/books/{book_id}", json_body=input)["data"]

    def delete(self, book_id: int) -> None:
        self._request("DELETE", f"/api/books/{book_id}")

    def isbn_lookup(self, isbn: str) -> dict:
        return self._request("GET", "/api/isbn-lookup", params={"isbn": isbn})["data"]
