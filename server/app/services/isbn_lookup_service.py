import logging

import httpx

from ..errors import NotFoundError, UpstreamError, ValidationError
from ..schemas import BookInfo

GOOGLE_BOOKS_BASE_URL = "https://www.googleapis.com/books/v1/volumes"

logger = logging.getLogger(__name__)


def _normalize_published_date(d: str) -> str:
    """Pad a Google Books publishedDate ("YYYY" or "YYYY-MM") out to
    "YYYY-MM-DD" so it fits an HTML date input; anything else passes through."""
    if len(d) == 4:
        return d + "-01-01"
    if len(d) == 7:
        return d + "-01"
    return d


class ISBNLookupService:
    """Client for the Google Books API. api_key may be empty (the API works
    unauthenticated, with lower rate limits). base_url may be overridden in
    tests to point at a fake server."""

    def __init__(self, api_key: str = "", base_url: str = ""):
        self._api_key = api_key
        self._base_url = base_url or GOOGLE_BOOKS_BASE_URL

    def lookup(self, isbn: str) -> BookInfo:
        normalized = isbn.strip().replace("-", "")
        if not normalized:
            raise ValidationError("isbn is required")

        params = {"q": f"isbn:{normalized}"}
        if self._api_key:
            params["key"] = self._api_key

        try:
            resp = httpx.get(self._base_url, params=params, timeout=5.0)
        except httpx.HTTPError as exc:
            # The client-facing message is intentionally generic; log the
            # underlying cause (e.g. upstream rate limiting) for diagnosis.
            logger.warning("isbn lookup failed: isbn=%r err=%r", isbn, exc)
            raise UpstreamError() from exc

        if resp.status_code != 200:
            logger.warning(
                "isbn lookup failed: isbn=%r status=%d", isbn, resp.status_code
            )
            raise UpstreamError()

        parsed = resp.json()
        items = parsed.get("items") or []
        if not items:
            raise NotFoundError("no book found for isbn")

        # A q=isbn:... search can return several candidate records for the
        # same book (e.g. from different regional catalogs), and the
        # metadata each one carries is inconsistent — one may have
        # title/authors but no publisher or date, while a later item does.
        # Merge fields across all returned items instead of trusting
        # items[0] alone, keeping the first non-empty value seen per field.
        title = author = publisher = published_date = ""
        isbn_13 = isbn_10 = ""
        for item in items:
            v = item.get("volumeInfo", {})
            if not title and v.get("title"):
                title = v["title"]
            if not author and v.get("authors"):
                author = ",".join(v["authors"])
            if not publisher and v.get("publisher"):
                publisher = v["publisher"]
            if not published_date and v.get("publishedDate"):
                published_date = v["publishedDate"]
            for ident in v.get("industryIdentifiers", []):
                if ident.get("type") == "ISBN_13" and not isbn_13:
                    isbn_13 = ident.get("identifier", "")
                elif ident.get("type") == "ISBN_10" and not isbn_10:
                    isbn_10 = ident.get("identifier", "")

        result_isbn = isbn_13 or isbn_10 or normalized

        return BookInfo(
            title=title,
            author=author,
            publisher=publisher,
            published_date=_normalize_published_date(published_date),
            isbn=result_isbn,
        )
