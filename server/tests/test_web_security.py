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


def test_templates_have_no_inline_scripts():
    """The CSP uses script-src 'self', so inline scripts and event handler
    attributes would be blocked; keep all JS in static/app.js."""
    import re
    from pathlib import Path

    templates = Path(__file__).resolve().parents[1] / "templates"
    for path in templates.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\bsrc=)", text), path
        assert not re.search(r"\son[a-z]+\s*=", text), path


def test_static_app_js_served(client: TestClient):
    resp = client.get("/static/app.js")
    assert resp.status_code == 200
    assert "data-confirm" in resp.text


def test_settings_default_host_is_loopback(monkeypatch):
    monkeypatch.setenv("API_KEY", "k" * MIN_API_KEY_LENGTH)
    monkeypatch.delenv("HOST", raising=False)
    assert Settings.from_env().host == "127.0.0.1"


def test_api_auth_runs_before_body_parsing(client: TestClient):
    """Unauthenticated requests must be rejected before the body is read,
    so a malformed body yields 401 (not a 400 that leaks field names)."""
    resp = client.post(
        "/api/books", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_api_wrong_key_counts_toward_rate_limit(client: TestClient):
    for _ in range(10):
        assert client.get("/api/books", headers={"X-API-Key": "wrong"}).status_code == 401
    resp = client.get("/api/books", headers=auth_headers())
    assert resp.status_code == 429


def test_oversized_content_length_rejected(client: TestClient):
    from app.middleware import MAX_BODY_BYTES

    body = b'{"title":"' + b"a" * MAX_BODY_BYTES + b'","author":"x"}'
    resp = client.post(
        "/api/books", content=body, headers={**auth_headers(), "Content-Type": "application/json"}
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_oversized_chunked_body_rejected(client: TestClient):
    from app.middleware import MAX_BODY_BYTES

    def chunks():
        yield b'{"title":"'
        for _ in range(MAX_BODY_BYTES // 65536 + 2):
            yield b"a" * 65536
        yield b'","author":"x"}'

    resp = client.post(
        "/api/books", content=chunks(), headers={**auth_headers(), "Content-Type": "application/json"}
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_oversized_login_form_rejected(client: TestClient):
    from app.middleware import MAX_BODY_BYTES

    resp = client.post(
        "/login",
        content=b"api_key=" + b"a" * MAX_BODY_BYTES,
        headers={**SAME_ORIGIN, "Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 413


def test_normal_sized_body_accepted(client: TestClient):
    resp = client.post(
        "/api/books", json={"title": "t", "author": "a", "memo": "m" * 2000}, headers=auth_headers()
    )
    assert resp.status_code == 201


@pytest.mark.parametrize("path", ["/login", "/static/style.css", "/api/books"])
def test_security_headers_on_every_response(client: TestClient, path: str):
    from app.middleware import SECURITY_HEADERS

    resp = client.get(path)  # /api/books without a key -> early 401 from middleware
    for name, value in SECURITY_HEADERS.items():
        assert resp.headers.get(name) == value, (path, name)
    assert "strict-transport-security" not in resp.headers


def test_security_headers_not_duplicated(client: TestClient):
    resp = client.get("/login")
    assert len(resp.headers.get_list("content-security-policy")) == 1


def test_security_headers_match_caddyfile():
    """The app and deploy/Caddyfile must send the same header values."""
    from pathlib import Path

    from app.middleware import SECURITY_HEADERS

    caddyfile = (Path(__file__).resolve().parents[2] / "deploy" / "Caddyfile").read_text()
    for name, value in SECURITY_HEADERS.items():
        assert f'{name} "{value}"' in caddyfile, name


@pytest.mark.parametrize("raw,expected", [(None, True), ("true", True), ("false", False), ("0", False)])
def test_settings_access_log(monkeypatch, raw, expected):
    monkeypatch.setenv("API_KEY", "k" * MIN_API_KEY_LENGTH)
    if raw is None:
        monkeypatch.delenv("ACCESS_LOG", raising=False)
    else:
        monkeypatch.setenv("ACCESS_LOG", raw)
    assert Settings.from_env().access_log is expected
