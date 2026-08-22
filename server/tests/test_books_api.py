from fastapi.testclient import TestClient

from .conftest import auth_headers


def test_unauthorized(client: TestClient):
    resp = client.get("/api/books")
    assert resp.status_code == 401


def test_create_and_get(client: TestClient):
    resp = client.post(
        "/api/books",
        json={"title": "吾輩は猫である", "author": "夏目漱石"},
        headers=auth_headers(),
    )
    assert resp.status_code == 201, resp.text
    book_id = resp.json()["data"]["id"]
    assert book_id != 0

    resp = client.get(f"/api/books/{book_id}", headers=auth_headers())
    assert resp.status_code == 200, resp.text


def test_get_not_found(client: TestClient):
    resp = client.get("/api/books/999", headers=auth_headers())
    assert resp.status_code == 404


def test_create_validation_error(client: TestClient):
    resp = client.post("/api/books", json={"title": ""}, headers=auth_headers())
    assert resp.status_code == 400


def test_create_conflict_isbn(client: TestClient):
    body = {"title": "A", "author": "X", "isbn": "9784101010359"}
    resp = client.post("/api/books", json=body, headers=auth_headers())
    assert resp.status_code == 201, resp.text

    resp = client.post("/api/books", json=body, headers=auth_headers())
    assert resp.status_code == 409


def test_get_by_isbn(client: TestClient):
    body = {"title": "A", "author": "X", "isbn": "978-4-10-101035-9"}
    client.post("/api/books", json=body, headers=auth_headers())

    resp = client.get("/api/books/by-isbn/9784101010359", headers=auth_headers())
    assert resp.status_code == 200, resp.text


def test_get_by_isbn_not_found(client: TestClient):
    resp = client.get("/api/books/by-isbn/9784101010359", headers=auth_headers())
    assert resp.status_code == 404


def test_list_search_and_pagination(client: TestClient):
    for title in ["吾輩は猫である", "坊っちゃん", "人間失格"]:
        client.post(
            "/api/books", json={"title": title, "author": "someone"}, headers=auth_headers()
        )

    resp = client.get("/api/books?page=1&page_size=2", headers=auth_headers())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["pagination"]["total"] == 3
    assert len(body["data"]) == 2


def test_delete(client: TestClient):
    resp = client.post(
        "/api/books", json={"title": "A", "author": "X"}, headers=auth_headers()
    )
    book_id = resp.json()["data"]["id"]

    resp = client.delete(f"/api/books/{book_id}", headers=auth_headers())
    assert resp.status_code == 204

    resp = client.get(f"/api/books/{book_id}", headers=auth_headers())
    assert resp.status_code == 404
