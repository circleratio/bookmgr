import pytest

from app.errors import ConflictError, NotFoundError
from app.repositories.book_repository import BookRepository
from app.schemas import Book


def make_book(**overrides) -> Book:
    fields = dict(
        id=0,
        title="A",
        author="X",
        rating=None,
        memo=None,
        isbn=None,
        publisher=None,
        published_date=None,
        created_at="",
        updated_at="",
    )
    fields.update(overrides)
    return Book(**fields)


def test_create_and_find_by_id(book_repo: BookRepository):
    book = make_book(title="吾輩は猫である", author="夏目漱石", rating=5, isbn="978-4-10-101035-9")
    created = book_repo.create(book)
    assert created.id != 0

    found = book_repo.find_by_id(created.id)
    assert found.title == book.title


def test_find_by_id_not_found(book_repo: BookRepository):
    with pytest.raises(NotFoundError):
        book_repo.find_by_id(999)


def test_find_by_isbn(book_repo: BookRepository):
    book = make_book(title="吾輩は猫である", author="夏目漱石", isbn="978-4-10-101035-9")
    created = book_repo.create(book)

    # Scanned barcodes are hyphen-free digits; lookup should still match a
    # hyphenated ISBN stored via manual entry.
    found = book_repo.find_by_isbn("9784101010359")
    assert found.id == created.id


def test_find_by_isbn_not_found(book_repo: BookRepository):
    with pytest.raises(NotFoundError):
        book_repo.find_by_isbn("9784101010359")


def test_create_duplicate_isbn(book_repo: BookRepository):
    isbn = "978-4-10-101035-9"
    book_repo.create(make_book(title="A", author="X", isbn=isbn))
    with pytest.raises(ConflictError):
        book_repo.create(make_book(title="B", author="Y", isbn=isbn))


def test_create_multiple_nil_isbn(book_repo: BookRepository):
    book_repo.create(make_book(title="A", author="X"))
    book_repo.create(make_book(title="B", author="Y"))


def test_update(book_repo: BookRepository):
    created = book_repo.create(make_book(title="A", author="X"))
    updated = make_book(title="B", author="X")
    book_repo.update(created.id, updated)

    found = book_repo.find_by_id(created.id)
    assert found.title == "B"


def test_update_not_found(book_repo: BookRepository):
    with pytest.raises(NotFoundError):
        book_repo.update(999, make_book(title="A", author="X"))


def test_delete(book_repo: BookRepository):
    created = book_repo.create(make_book(title="A", author="X"))
    book_repo.delete(created.id)
    with pytest.raises(NotFoundError):
        book_repo.find_by_id(created.id)


def test_delete_not_found(book_repo: BookRepository):
    with pytest.raises(NotFoundError):
        book_repo.delete(999)


def test_list_search_and_pagination(book_repo: BookRepository):
    for title, author in [
        ("吾輩は猫である", "夏目漱石"),
        ("坊っちゃん", "夏目漱石"),
        ("人間失格", "太宰治"),
    ]:
        book_repo.create(make_book(title=title, author=author))

    books, total = book_repo.list("夏目漱石", 1, 20)
    assert total == 2
    assert len(books) == 2

    books, total = book_repo.list("", 1, 2)
    assert total == 3
    assert len(books) == 2

    books, _ = book_repo.list("", 2, 2)
    assert len(books) == 1
