import sqlite3

from ..db import Database
from ..errors import ConflictError, NotFoundError
from ..schemas import Book

_SELECT_COLUMNS = (
    "id, title, author, rating, memo, isbn, publisher, published_date, "
    "created_at, updated_at"
)


def _row_to_book(row: sqlite3.Row) -> Book:
    return Book(
        id=row["id"],
        title=row["title"],
        author=row["author"],
        rating=row["rating"],
        memo=row["memo"],
        isbn=row["isbn"],
        publisher=row["publisher"],
        published_date=row["published_date"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _is_unique_constraint_error(exc: sqlite3.IntegrityError) -> bool:
    return "UNIQUE constraint failed" in str(exc)


class BookRepository:
    def __init__(self, db: Database):
        self._db = db

    def list(self, query: str, page: int, page_size: int) -> tuple[list[Book], int]:
        like = f"%{query}%"
        with self._db.lock:
            total = self._db.conn.execute(
                "SELECT COUNT(*) FROM books WHERE title LIKE ? OR author LIKE ?",
                (like, like),
            ).fetchone()[0]

            offset = (page - 1) * page_size
            rows = self._db.conn.execute(
                f"""SELECT {_SELECT_COLUMNS}
                    FROM books
                    WHERE title LIKE ? OR author LIKE ?
                    ORDER BY id DESC
                    LIMIT ? OFFSET ?""",
                (like, like, page_size, offset),
            ).fetchall()

        return [_row_to_book(r) for r in rows], total

    def find_by_id(self, book_id: int) -> Book:
        with self._db.lock:
            row = self._db.conn.execute(
                f"SELECT {_SELECT_COLUMNS} FROM books WHERE id = ?", (book_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError()
        return _row_to_book(row)

    def find_by_isbn(self, isbn: str) -> Book:
        normalized = isbn.replace("-", "")
        with self._db.lock:
            row = self._db.conn.execute(
                f"SELECT {_SELECT_COLUMNS} FROM books WHERE REPLACE(isbn, '-', '') = ?",
                (normalized,),
            ).fetchone()
        if row is None:
            raise NotFoundError()
        return _row_to_book(row)

    def create(self, book: Book) -> Book:
        with self._db.lock:
            try:
                cur = self._db.conn.execute(
                    """INSERT INTO books (title, author, rating, memo, isbn, publisher, published_date)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        book.title,
                        book.author,
                        book.rating,
                        book.memo,
                        book.isbn,
                        book.publisher,
                        book.published_date,
                    ),
                )
                self._db.conn.commit()
            except sqlite3.IntegrityError as exc:
                self._db.conn.rollback()
                if _is_unique_constraint_error(exc):
                    raise ConflictError("isbn already exists") from exc
                raise
            book_id = cur.lastrowid
        return self.find_by_id(book_id)

    def update(self, book_id: int, book: Book) -> Book:
        with self._db.lock:
            try:
                cur = self._db.conn.execute(
                    """UPDATE books
                       SET title = ?, author = ?, rating = ?, memo = ?, isbn = ?, publisher = ?,
                           published_date = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (
                        book.title,
                        book.author,
                        book.rating,
                        book.memo,
                        book.isbn,
                        book.publisher,
                        book.published_date,
                        book_id,
                    ),
                )
                self._db.conn.commit()
            except sqlite3.IntegrityError as exc:
                self._db.conn.rollback()
                if _is_unique_constraint_error(exc):
                    raise ConflictError("isbn already exists") from exc
                raise
            affected = cur.rowcount
        if affected == 0:
            raise NotFoundError()
        return self.find_by_id(book_id)

    def delete(self, book_id: int) -> None:
        with self._db.lock:
            cur = self._db.conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
            self._db.conn.commit()
            affected = cur.rowcount
        if affected == 0:
            raise NotFoundError()
