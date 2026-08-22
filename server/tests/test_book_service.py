import pytest

from app.errors import ConflictError, NotFoundError, ValidationError
from app.schemas import Book, BookInput
from app.services.book_service import DEFAULT_PAGE_SIZE, BookService


class FakeRepo:
    def __init__(self):
        self.books: dict[int, Book] = {}
        self.next_id = 0

    def list(self, query: str, page: int, page_size: int):
        result = list(self.books.values())
        return result, len(result)

    def find_by_id(self, book_id: int) -> Book:
        if book_id not in self.books:
            raise NotFoundError()
        return self.books[book_id]

    def find_by_isbn(self, isbn: str) -> Book:
        for b in self.books.values():
            if b.isbn == isbn:
                return b
        raise NotFoundError()

    def create(self, book: Book) -> Book:
        for b in self.books.values():
            if book.isbn is not None and b.isbn == book.isbn:
                raise ConflictError("isbn already exists")
        self.next_id += 1
        saved = book.model_copy(update={"id": self.next_id})
        self.books[saved.id] = saved
        return saved

    def update(self, book_id: int, book: Book) -> Book:
        if book_id not in self.books:
            raise NotFoundError()
        saved = book.model_copy(update={"id": book_id})
        self.books[book_id] = saved
        return saved

    def delete(self, book_id: int) -> None:
        if book_id not in self.books:
            raise NotFoundError()
        del self.books[book_id]


def valid_input(**overrides) -> BookInput:
    fields = dict(title="吾輩は猫である", author="夏目漱石")
    fields.update(overrides)
    return BookInput(**fields)


def test_create_valid():
    svc = BookService(FakeRepo())
    book = svc.create(valid_input())
    assert book.id != 0


def test_create_title_required():
    svc = BookService(FakeRepo())
    with pytest.raises(ValidationError):
        svc.create(valid_input(title="  "))


def test_create_author_required():
    svc = BookService(FakeRepo())
    with pytest.raises(ValidationError):
        svc.create(valid_input(author=""))


@pytest.mark.parametrize("rating,want_err", [(0, True), (1, False), (5, False), (6, True)])
def test_create_rating_boundaries(rating, want_err):
    svc = BookService(FakeRepo())
    if want_err:
        with pytest.raises(ValidationError):
            svc.create(valid_input(rating=rating))
    else:
        svc.create(valid_input(rating=rating))


@pytest.mark.parametrize(
    "isbn,want_err",
    [
        ("4101010351", False),
        ("9784101010359", False),
        ("978-4-10-101035-9", False),
        ("410101003X", False),
        ("410101003x", False),
        ("4-10-101003-X", False),
        ("41010100X1", True),
        ("978410101003X", True),
        ("12345", True),
        ("abcdefghij", True),
        ("12345678901", True),
    ],
)
def test_create_isbn(isbn, want_err):
    svc = BookService(FakeRepo())
    if want_err:
        with pytest.raises(ValidationError):
            svc.create(valid_input(isbn=isbn))
    else:
        svc.create(valid_input(isbn=isbn))


def test_create_empty_optional_fields_become_nil():
    svc = BookService(FakeRepo())
    book = svc.create(valid_input(memo="   ", isbn="   "))
    assert book.memo is None
    assert book.isbn is None


@pytest.mark.parametrize(
    "date,want_err",
    [
        ("2003-05-01", False),
        ("2003/05/01", True),
        ("not-a-date", True),
        ("2003-13-40", True),
    ],
)
def test_create_published_date_format(date, want_err):
    svc = BookService(FakeRepo())
    if want_err:
        with pytest.raises(ValidationError):
            svc.create(valid_input(published_date=date))
    else:
        svc.create(valid_input(published_date=date))


def test_create_duplicate_isbn_conflict():
    svc = BookService(FakeRepo())
    isbn = "9784101010359"
    svc.create(valid_input(isbn=isbn))
    with pytest.raises(ConflictError):
        svc.create(valid_input(isbn=isbn))


def test_list_defaults_and_clamping():
    svc = BookService(FakeRepo())

    _, pagination = svc.list("", 0, 0)
    assert pagination.page == 1
    assert pagination.page_size == DEFAULT_PAGE_SIZE

    _, pagination = svc.list("", 1, 500)
    assert pagination.page_size == DEFAULT_PAGE_SIZE


def test_delete_not_found():
    svc = BookService(FakeRepo())
    with pytest.raises(NotFoundError):
        svc.delete(999)
