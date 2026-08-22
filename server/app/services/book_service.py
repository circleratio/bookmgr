import re
from dataclasses import dataclass
from datetime import date

from ..errors import ValidationError
from ..repositories.book_repository import BookRepository
from ..schemas import Book, BookInput

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

_PUBLISHED_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Pagination:
    page: int
    page_size: int
    total: int


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _is_valid_isbn(digits: str) -> bool:
    if len(digits) == 13:
        return digits.isdigit()
    if len(digits) == 10:
        return digits[:9].isdigit() and (digits[9].isdigit() or digits[9] in "Xx")
    return False


def _validate_input(input: BookInput) -> Book:
    title = input.title.strip()
    if not title:
        raise ValidationError("title is required")
    if len(title) > 255:
        raise ValidationError("title must be at most 255 characters")

    author = input.author.strip()
    if not author:
        raise ValidationError("author is required")
    if len(author) > 255:
        raise ValidationError("author must be at most 255 characters")

    if input.rating is not None and not (1 <= input.rating <= 5):
        raise ValidationError("rating must be between 1 and 5")

    memo = _normalize_optional(input.memo)
    if memo is not None and len(memo) > 2000:
        raise ValidationError("memo must be at most 2000 characters")

    isbn = _normalize_optional(input.isbn)
    if isbn is not None and not _is_valid_isbn(isbn.replace("-", "")):
        raise ValidationError(
            "isbn must be 13 digits, or 10 digits with an optional trailing X "
            "check digit (hyphens allowed)"
        )

    publisher = _normalize_optional(input.publisher)
    if publisher is not None and len(publisher) > 255:
        raise ValidationError("publisher must be at most 255 characters")

    published_date = _normalize_optional(input.published_date)
    if published_date is not None:
        if not _PUBLISHED_DATE_PATTERN.match(published_date):
            raise ValidationError("published_date must be in YYYY-MM-DD format")
        try:
            date.fromisoformat(published_date)
        except ValueError as exc:
            raise ValidationError("published_date must be a valid date") from exc

    return Book(
        id=0,
        title=title,
        author=author,
        rating=input.rating,
        memo=memo,
        isbn=isbn,
        publisher=publisher,
        published_date=published_date,
        created_at="",
        updated_at="",
    )


class BookService:
    def __init__(self, repo: BookRepository):
        self._repo = repo

    def list(self, query: str, page: int, page_size: int) -> tuple[list[Book], Pagination]:
        if page < 1:
            page = 1
        if page_size < 1 or page_size > MAX_PAGE_SIZE:
            page_size = DEFAULT_PAGE_SIZE

        books, total = self._repo.list(query, page, page_size)
        return books, Pagination(page=page, page_size=page_size, total=total)

    def get(self, book_id: int) -> Book:
        return self._repo.find_by_id(book_id)

    def get_by_isbn(self, isbn: str) -> Book:
        isbn = isbn.strip()
        if not isbn:
            raise ValidationError("isbn is required")
        return self._repo.find_by_isbn(isbn)

    def create(self, input: BookInput) -> Book:
        book = _validate_input(input)
        return self._repo.create(book)

    def update(self, book_id: int, input: BookInput) -> Book:
        book = _validate_input(input)
        return self._repo.update(book_id, book)

    def delete(self, book_id: int) -> None:
        self._repo.delete(book_id)
