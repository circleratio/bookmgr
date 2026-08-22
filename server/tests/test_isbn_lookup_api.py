from fastapi.testclient import TestClient

from .conftest import auth_headers


def test_isbn_lookup_unauthorized(client: TestClient):
    resp = client.get("/api/isbn-lookup?isbn=9784101010359")
    assert resp.status_code == 401


def test_isbn_lookup_success(client: TestClient, monkeypatch):
    def fake_get(url, params=None, timeout=None):
        import httpx

        req = httpx.Request("GET", url, params=params)
        return httpx.Response(
            200,
            json={
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
            request=req,
        )

    monkeypatch.setattr("app.services.isbn_lookup_service.httpx.get", fake_get)

    resp = client.get("/api/isbn-lookup?isbn=9784101010359", headers=auth_headers())
    assert resp.status_code == 200, resp.text


def test_isbn_lookup_not_found(client: TestClient, monkeypatch):
    def fake_get(url, params=None, timeout=None):
        import httpx

        req = httpx.Request("GET", url, params=params)
        return httpx.Response(200, json={"items": []}, request=req)

    monkeypatch.setattr("app.services.isbn_lookup_service.httpx.get", fake_get)

    resp = client.get("/api/isbn-lookup?isbn=0000000000000", headers=auth_headers())
    assert resp.status_code == 404


def test_isbn_lookup_missing_param(client: TestClient):
    resp = client.get("/api/isbn-lookup", headers=auth_headers())
    assert resp.status_code == 400
