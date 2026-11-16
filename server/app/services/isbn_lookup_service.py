import logging
import re

import httpx

from ..errors import NotFoundError, UpstreamError, ValidationError
from ..schemas import BookInfo

GOOGLE_BOOKS_BASE_URL = "https://www.googleapis.com/books/v1/volumes"

_ISBN_PATTERN = re.compile(r"\d{13}|\d{9}[\dXx]")

logger = logging.getLogger(__name__)


def _normalize_published_date(d: str) -> str:
    """Pad a Google Books publishedDate ("YYYY" or "YYYY-MM") out to
    "YYYY-MM-DD" so it fits an HTML date input; anything else passes through."""
    if len(d) == 4:
        return d + "-01-01"
    if len(d) == 7:
        return d + "-01"
    return d


def _str_field(obj: dict, key: str) -> str:
    """Returns obj[key] if it is a string, else "" (treated as missing)."""
    value = obj.get(key)
    return value if isinstance(value, str) else ""


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
        # Only a bare ISBN may reach the upstream query, so arbitrary search
        # terms (e.g. "intitle:...") cannot be injected into q.
        if not _ISBN_PATTERN.fullmatch(normalized):
            raise ValidationError(
                "isbn must be 13 digits, or 10 digits with an optional trailing X "
                "check digit (hyphens allowed)"
            )

        params = {"q": f"isbn:{normalized}"}
        # Send the API key as a header rather than a query parameter so it
        # does not end up in logged request URLs.
        headers = {"X-Goog-Api-Key": self._api_key} if self._api_key else {}

        try:
            resp = httpx.get(self._base_url, params=params, headers=headers, timeout=5.0)
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

        # The upstream body is untrusted: a non-JSON or wrongly shaped body
        # is an upstream failure (502), not an internal error (500).
        try:
            parsed = resp.json()
        except ValueError as exc:
            logger.warning("isbn lookup failed: isbn=%r err=invalid JSON", isbn)
            raise UpstreamError() from exc
        items = parsed.get("items") if isinstance(parsed, dict) else None
        if items is None:
            items = []
        if not isinstance(items, list):
            logger.warning("isbn lookup failed: isbn=%r err=unexpected response shape", isbn)
            raise UpstreamError()
        if not items:
            raise NotFoundError("no book found for isbn")

        # A q=isbn:... search can return several candidate records for the
        # same book (e.g. from different regional catalogs), and the
        # metadata each one carries is inconsistent — one may have
        # title/authors but no publisher or date, while a later item does.
        # Merge fields across all returned items instead of trusting
        # items[0] alone, keeping the first non-empty value seen per field.
        # Items or fields of an unexpected type are skipped as if missing.
        title = author = publisher = published_date = ""
        isbn_13 = isbn_10 = ""
        for item in items:
            v = item.get("volumeInfo") if isinstance(item, dict) else None
            if not isinstance(v, dict):
                continue
            if not title:
                title = _str_field(v, "title")
            if not author:
                authors = v.get("authors")
                if isinstance(authors, list):
                    author = ",".join(a for a in authors if isinstance(a, str) and a)
            if not publisher:
                publisher = _str_field(v, "publisher")
            if not published_date:
                published_date = _str_field(v, "publishedDate")
            identifiers = v.get("industryIdentifiers")
            if not isinstance(identifiers, list):
                continue
            for ident in identifiers:
                if not isinstance(ident, dict):
                    continue
                if ident.get("type") == "ISBN_13" and not isbn_13:
                    isbn_13 = _str_field(ident, "identifier")
                elif ident.get("type") == "ISBN_10" and not isbn_10:
                    isbn_10 = _str_field(ident, "identifier")

        result_isbn = isbn_13 or isbn_10 or normalized

        return BookInfo(
            title=title,
            author=author,
            publisher=publisher,
            published_date=_normalize_published_date(published_date),
            isbn=result_isbn,
        )
