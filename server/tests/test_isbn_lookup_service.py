import pytest

from app.errors import NotFoundError, UpstreamError, ValidationError
from app.services.isbn_lookup_service import ISBNLookupService


@pytest.fixture
def patch_httpx_get(monkeypatch):
    """Stubs httpx.get so tests don't hit the real Google Books API."""

    def _patch(status_code: int, body: dict, capture: dict | None = None):
        def fake_get(url, params=None, headers=None, timeout=None):
            import httpx

            if capture is not None:
                capture["params"] = params or {}
                capture["headers"] = headers or {}
            req = httpx.Request("GET", url, params=params)
            return httpx.Response(status_code, json=body, request=req)

        monkeypatch.setattr("app.services.isbn_lookup_service.httpx.get", fake_get)

    return _patch


def test_lookup_success(patch_httpx_get):
    patch_httpx_get(
        200,
        {
            "items": [
                {
                    "volumeInfo": {
                        "title": "吾輩は猫である",
                        "authors": ["夏目漱石"],
                        "publisher": "新潮社",
                        "publishedDate": "2003-05-01",
                        "industryIdentifiers": [
                            {"type": "ISBN_13", "identifier": "9784101010359"}
                        ],
                    }
                }
            ]
        },
    )

    svc = ISBNLookupService()
    info = svc.lookup("978-4-10-101035-9")
    assert info.title == "吾輩は猫である"
    assert info.author == "夏目漱石"
    assert info.publisher == "新潮社"
    assert info.published_date == "2003-05-01"
    assert info.isbn == "9784101010359"


def test_lookup_merges_fields_across_multiple_items(patch_httpx_get):
    patch_httpx_get(
        200,
        {
            "items": [
                {"volumeInfo": {"title": "吾輩は猫である", "authors": ["夏目漱石"]}},
                {
                    "volumeInfo": {
                        "title": "吾輩は猫である",
                        "authors": ["夏目漱石"],
                        "publisher": "新潮社",
                        "publishedDate": "2003-05-01",
                    }
                },
            ]
        },
    )

    svc = ISBNLookupService()
    info = svc.lookup("9784101010359")
    assert info.publisher == "新潮社"
    assert info.published_date == "2003-05-01"


def test_lookup_multiple_authors_joined(patch_httpx_get):
    patch_httpx_get(
        200, {"items": [{"volumeInfo": {"title": "共著本", "authors": ["著者A", "著者B"]}}]}
    )

    svc = ISBNLookupService()
    info = svc.lookup("9780000000002")
    assert info.author == "著者A,著者B"


def test_lookup_falls_back_to_isbn10_then_input(patch_httpx_get):
    patch_httpx_get(
        200,
        {
            "items": [
                {
                    "volumeInfo": {
                        "title": "T",
                        "authors": ["A"],
                        "industryIdentifiers": [{"type": "ISBN_10", "identifier": "4101010351"}],
                    }
                }
            ]
        },
    )

    svc = ISBNLookupService()
    info = svc.lookup("4101010351")
    assert info.isbn == "4101010351"


@pytest.mark.parametrize(
    "raw,want", [("2003", "2003-01-01"), ("2003-05", "2003-05-01"), ("2003-05-01", "2003-05-01")]
)
def test_lookup_published_date_normalization(patch_httpx_get, raw, want):
    patch_httpx_get(
        200, {"items": [{"volumeInfo": {"title": "T", "authors": ["A"], "publishedDate": raw}}]}
    )

    svc = ISBNLookupService()
    info = svc.lookup("9780000000002")
    assert info.published_date == want


def test_lookup_not_found(patch_httpx_get):
    patch_httpx_get(200, {"items": []})

    svc = ISBNLookupService()
    with pytest.raises(NotFoundError):
        svc.lookup("9780000000000")


def test_lookup_empty_isbn():
    svc = ISBNLookupService()
    with pytest.raises(ValidationError):
        svc.lookup("  ")


def test_lookup_upstream_error(patch_httpx_get):
    patch_httpx_get(500, {})

    svc = ISBNLookupService()
    with pytest.raises(UpstreamError):
        svc.lookup("9780000000000")


def test_lookup_non_json_body_is_upstream_error(monkeypatch):
    import httpx

    def fake_get(url, params=None, headers=None, timeout=None):
        req = httpx.Request("GET", url, params=params)
        return httpx.Response(200, content=b"<html>oops</html>", request=req)

    monkeypatch.setattr("app.services.isbn_lookup_service.httpx.get", fake_get)

    with pytest.raises(UpstreamError):
        ISBNLookupService().lookup("9780000000000")


@pytest.mark.parametrize("body", [{"items": "x"}, {"items": {"a": 1}}, {"items": 3}])
def test_lookup_wrongly_shaped_items_is_upstream_error(patch_httpx_get, body):
    patch_httpx_get(200, body)

    with pytest.raises(UpstreamError):
        ISBNLookupService().lookup("9780000000000")


@pytest.mark.parametrize("body", [[], "x", {}, {"items": None}])
def test_lookup_body_without_items_is_not_found(patch_httpx_get, body):
    patch_httpx_get(200, body)

    with pytest.raises(NotFoundError):
        ISBNLookupService().lookup("9780000000000")


def test_lookup_skips_malformed_items_and_fields(patch_httpx_get):
    patch_httpx_get(
        200,
        {
            "items": [
                "not-an-object",
                {"volumeInfo": "not-an-object"},
                {
                    "volumeInfo": {
                        "title": 123,
                        "authors": "not-a-list",
                        "publisher": ["x"],
                        "publishedDate": None,
                        "industryIdentifiers": "not-a-list",
                    }
                },
                {
                    "volumeInfo": {
                        "title": "T",
                        "authors": ["A", 1, None, "B"],
                        "publisher": "P",
                        "publishedDate": "2001",
                        "industryIdentifiers": [
                            "x",
                            {"type": "ISBN_13", "identifier": 9780000000000},
                            {"type": "ISBN_10", "identifier": "0000000000"},
                        ],
                    }
                },
            ]
        },
    )

    info = ISBNLookupService().lookup("9780000000000")
    assert info.title == "T"
    assert info.author == "A,B"
    assert info.publisher == "P"
    assert info.published_date == "2001-01-01"
    assert info.isbn == "0000000000"


def test_lookup_api_key_passed_as_header(patch_httpx_get):
    capture: dict = {}
    patch_httpx_get(
        200, {"items": [{"volumeInfo": {"title": "T", "authors": ["A"]}}]}, capture=capture
    )

    svc = ISBNLookupService(api_key="my-google-key")
    svc.lookup("9780000000000")
    assert capture["headers"].get("X-Goog-Api-Key") == "my-google-key"
    assert "key" not in capture["params"]


@pytest.mark.parametrize(
    "isbn",
    [
        "abc",
        "978000000000",
        "97800000000001",
        "9780000000000 intitle:x",
        "123456789Y",
    ],
)
def test_lookup_rejects_non_isbn_input(isbn):
    svc = ISBNLookupService()
    with pytest.raises(ValidationError):
        svc.lookup(isbn)
