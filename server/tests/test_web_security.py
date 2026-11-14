import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.auth import client_key
from app.config import MIN_API_KEY_LENGTH, Settings

from .conftest import TEST_API_KEY, auth_headers

SAME_ORIGIN = {"Origin": "http://testserver"}


def login(client: TestClient) -> None:
    resp = client.post(
        "/login", data={"api_key": TEST_API_KEY}, headers=SAME_ORIGIN, follow_redirects=False
    )
    assert resp.status_code == 302, resp.text


def test_login_same_origin(client: TestClient):
    login(client)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 200


def test_login_rejects_cross_origin(client: TestClient):
    resp = client.post(
        "/login",
        data={"api_key": TEST_API_KEY},
        headers={"Origin": "https://evil.example"},
        follow_redirects=False,
    )
    assert resp.status_code == 403


def test_login_accepts_same_origin_referer(client: TestClient):
    resp = client.post(
        "/login",
        data={"api_key": TEST_API_KEY},
        headers={"Referer": "http://testserver/login"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "null"},
        {"Origin": "https://evil.example"},
        {"Origin": "http://testserver.evil.example"},
        {"Referer": "https://evil.example/?u=http://testserver"},
    ],
)
def test_web_post_rejects_missing_or_foreign_origin(client: TestClient, headers):
    login(client)
    resp = client.post(
        "/books", data={"title": "T", "author": "A"}, headers=headers, follow_redirects=False
    )
    assert resp.status_code == 403

    resp = client.get("/api/books", headers=auth_headers())
    assert resp.json()["pagination"]["total"] == 0


def test_web_post_same_origin_creates_book(client: TestClient):
    login(client)
    resp = client.post(
        "/books", data={"title": "T", "author": "A"}, headers=SAME_ORIGIN, follow_redirects=False
    )
    assert resp.status_code == 302


def test_logout_revokes_session(client: TestClient):
    login(client)
    resp = client.post("/logout", headers=SAME_ORIGIN, follow_redirects=False)
    assert resp.status_code == 302
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"


def test_pagination_link_urlencodes_query(client: TestClient):
    for i in range(21):
        client.post(
            "/api/books", json={"title": f"a&b {i}", "author": "X"}, headers=auth_headers()
        )
    login(client)
    resp = client.get("/", params={"q": "a&b"})
    assert 'href="/?q=a%26b&page=2"' in resp.text


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_api_docs_disabled(client: TestClient, path: str):
    assert client.get(path).status_code == 404


def test_validation_error_does_not_echo_input(client: TestClient):
    resp = client.post(
        "/api/books",
        json={"title": "T", "author": "A", "rating": "secret-marker"},
        headers=auth_headers(),
    )
    assert resp.status_code == 400
    message = resp.json()["error"]["message"]
    assert "rating" in message
    assert "secret-marker" not in message


def _request_from(host: str) -> Request:
    return Request({"type": "http", "client": (host, 12345), "headers": []})


def test_client_key_groups_ipv6_by_64_prefix():
    a = client_key(_request_from("2001:db8:1:2::1"))
    b = client_key(_request_from("2001:db8:1:2:ffff::9"))
    c = client_key(_request_from("2001:db8:1:3::1"))
    assert a == b == "2001:db8:1:2::/64"
    assert a != c


def test_client_key_ipv4_unchanged():
    assert client_key(_request_from("192.0.2.1")) == "192.0.2.1"


def test_settings_rejects_short_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "x" * (MIN_API_KEY_LENGTH - 1))
    with pytest.raises(RuntimeError):
        Settings.from_env()


def test_settings_accepts_long_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "x" * MIN_API_KEY_LENGTH)
    assert Settings.from_env().api_key == "x" * MIN_API_KEY_LENGTH


def test_api_rejects_non_ascii_key_and_counts_failure(client: TestClient):
    resp = client.get("/api/books", headers={"X-API-Key": "é".encode("latin-1")})
    assert resp.status_code == 401
    assert client.app.state.login_limiter.tracked_keys() == 1


def test_login_rejects_non_ascii_key(client: TestClient):
    resp = client.post("/login", data={"api_key": "日本語"}, headers=SAME_ORIGIN)
    assert resp.status_code == 401


@pytest.mark.parametrize("path", ["/api/books?page=99999999999999999999"])
def test_huge_page_does_not_500(client: TestClient, path: str):
    resp = client.get(path, headers=auth_headers())
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_web_huge_page_does_not_500(client: TestClient):
    login(client)
    resp = client.get("/?page=99999999999999999999")
    assert resp.status_code == 200
