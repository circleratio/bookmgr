import json

import httpx
import pytest

from bookmgr_cli.client import APIError, Client

TEST_API_KEY = "test-api-key"


class FakeServer:
    """A minimal stand-in for the real bookmgr API, just enough to exercise
    this client's request building and response/error parsing. Mirrors the
    fake server used by internal/apiclient's Go tests."""

    def __init__(self):
        self.books: dict[int, dict] = {}
        self.next_id = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("X-API-Key") != TEST_API_KEY:
            return self._error(401, "UNAUTHORIZED", "invalid or missing API key")

        method, path = request.method, request.url.path
        if method == "POST" and path == "/api/books":
            return self._create(request)
        if method == "GET" and path == "/api/books":
            return self._list(request)
        if method == "GET" and path.startswith("/api/books/"):
            return self._get(self._id_from_path(path))
        if method == "PUT" and path.startswith("/api/books/"):
            return self._update(request, self._id_from_path(path))
        if method == "DELETE" and path.startswith("/api/books/"):
            return self._delete(self._id_from_path(path))
        return httpx.Response(404)

    @staticmethod
    def _id_from_path(path: str) -> int:
        return int(path.rsplit("/", 1)[-1])

    @staticmethod
    def _error(status: int, code: str, message: str) -> httpx.Response:
        return httpx.Response(status, json={"error": {"code": code, "message": message}})

    def _create(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        if not (body.get("title") or "").strip():
            return self._error(400, "VALIDATION_ERROR", "title is required")
        self.next_id += 1
        body["id"] = self.next_id
        self.books[self.next_id] = body
        return httpx.Response(201, json={"data": body})

    def _get(self, book_id: int) -> httpx.Response:
        book = self.books.get(book_id)
        if book is None:
            return self._error(404, "NOT_FOUND", "book not found")
        return httpx.Response(200, json={"data": book})

    def _update(self, request: httpx.Request, book_id: int) -> httpx.Response:
        if book_id not in self.books:
            return self._error(404, "NOT_FOUND", "book not found")
        body = json.loads(request.content or b"{}")
        body["id"] = book_id
        self.books[book_id] = body
        return httpx.Response(200, json={"data": body})

    def _delete(self, book_id: int) -> httpx.Response:
        if book_id not in self.books:
            return self._error(404, "NOT_FOUND", "book not found")
        del self.books[book_id]
        return httpx.Response(204)

    def _list(self, request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page") or 1)
        page_size = int(request.url.params.get("page_size") or 20)
        ids = sorted(self.books.keys(), reverse=True)
        total = len(ids)
        start = min((page - 1) * page_size, total)
        end = min(start + page_size, total)
        books = [self.books[i] for i in ids[start:end]]
        return httpx.Response(
            200,
            json={
                "data": books,
                "pagination": {"page": page, "page_size": page_size, "total": total},
            },
        )


@pytest.fixture
def client():
    transport = httpx.MockTransport(FakeServer().handle)
    with Client("http://testserver", TEST_API_KEY, transport=transport) as c:
        yield c


def test_create_get_update_delete(client: Client):
    created = client.create(
        {"title": "吾輩は猫である", "author": "夏目漱石", "rating": 5, "isbn": "9784101010359"}
    )
    assert created["id"] != 0

    got = client.get(created["id"])
    assert got["title"] == "吾輩は猫である"

    updated = client.update(created["id"], {"title": "坊っちゃん", "author": "夏目漱石"})
    assert updated["title"] == "坊っちゃん"

    client.delete(created["id"])

    with pytest.raises(APIError) as exc_info:
        client.get(created["id"])
    assert exc_info.value.status_code == 404


def test_create_validation_error(client: Client):
    with pytest.raises(APIError) as exc_info:
        client.create({"title": "", "author": "X"})
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_unauthorized():
    transport = httpx.MockTransport(FakeServer().handle)
    with Client("http://testserver", "wrong-key", transport=transport) as client:
        with pytest.raises(APIError) as exc_info:
            client.list()
        assert exc_info.value.status_code == 401


def test_list_search_and_pagination(client: Client):
    for title in ["吾輩は猫である", "坊っちゃん", "人間失格"]:
        client.create({"title": title, "author": "someone"})

    books, pagination = client.list(page=1, page_size=2)
    assert pagination["total"] == 3
    assert len(books) == 2
