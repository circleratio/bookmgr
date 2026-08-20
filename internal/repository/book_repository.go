package repository

import (
	"context"
	"database/sql"
	"errors"
	"fmt"

	sqlite "modernc.org/sqlite"
	sqlite3lib "modernc.org/sqlite/lib"

	"bookmgr/internal/apperr"
	"bookmgr/internal/model"
)

type BookRepository interface {
	List(ctx context.Context, query string, page, pageSize int) ([]model.Book, int, error)
	FindByID(ctx context.Context, id int64) (*model.Book, error)
	Create(ctx context.Context, book *model.Book) error
	Update(ctx context.Context, book *model.Book) error
	Delete(ctx context.Context, id int64) error
}

type bookRepository struct {
	db *sql.DB
}

func NewBookRepository(db *sql.DB) BookRepository {
	return &bookRepository{db: db}
}

func (r *bookRepository) List(ctx context.Context, query string, page, pageSize int) ([]model.Book, int, error) {
	like := "%" + query + "%"
	var total int
	if err := r.db.QueryRowContext(ctx,
		`SELECT COUNT(*) FROM books WHERE title LIKE ? OR author LIKE ?`,
		like, like,
	).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count books: %w", err)
	}

	offset := (page - 1) * pageSize
	rows, err := r.db.QueryContext(ctx,
		`SELECT id, title, author, rating, memo, isbn, publisher, published_date, created_at, updated_at
		 FROM books
		 WHERE title LIKE ? OR author LIKE ?
		 ORDER BY id DESC
		 LIMIT ? OFFSET ?`,
		like, like, pageSize, offset,
	)
	if err != nil {
		return nil, 0, fmt.Errorf("list books: %w", err)
	}
	defer rows.Close()

	books := make([]model.Book, 0, pageSize)
	for rows.Next() {
		b, err := scanBook(rows)
		if err != nil {
			return nil, 0, fmt.Errorf("scan book: %w", err)
		}
		books = append(books, *b)
	}
	if err := rows.Err(); err != nil {
		return nil, 0, fmt.Errorf("list books: %w", err)
	}

	return books, total, nil
}

func (r *bookRepository) FindByID(ctx context.Context, id int64) (*model.Book, error) {
	row := r.db.QueryRowContext(ctx,
		`SELECT id, title, author, rating, memo, isbn, publisher, published_date, created_at, updated_at
		 FROM books WHERE id = ?`,
		id,
	)
	b, err := scanBook(row)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, apperr.ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("find book: %w", err)
	}
	return b, nil
}

func (r *bookRepository) Create(ctx context.Context, book *model.Book) error {
	res, err := r.db.ExecContext(ctx,
		`INSERT INTO books (title, author, rating, memo, isbn, publisher, published_date)
		 VALUES (?, ?, ?, ?, ?, ?, ?)`,
		book.Title, book.Author, book.Rating, book.Memo, book.ISBN, book.Publisher, book.PublishedDate,
	)
	if err != nil {
		if isUniqueConstraintErr(err) {
			return apperr.NewConflictError("isbn already exists")
		}
		return fmt.Errorf("create book: %w", err)
	}
	id, err := res.LastInsertId()
	if err != nil {
		return fmt.Errorf("create book: %w", err)
	}
	created, err := r.FindByID(ctx, id)
	if err != nil {
		return fmt.Errorf("create book: %w", err)
	}
	*book = *created
	return nil
}

func (r *bookRepository) Update(ctx context.Context, book *model.Book) error {
	res, err := r.db.ExecContext(ctx,
		`UPDATE books
		 SET title = ?, author = ?, rating = ?, memo = ?, isbn = ?, publisher = ?, published_date = ?,
		     updated_at = CURRENT_TIMESTAMP
		 WHERE id = ?`,
		book.Title, book.Author, book.Rating, book.Memo, book.ISBN, book.Publisher, book.PublishedDate, book.ID,
	)
	if err != nil {
		if isUniqueConstraintErr(err) {
			return apperr.NewConflictError("isbn already exists")
		}
		return fmt.Errorf("update book: %w", err)
	}
	affected, err := res.RowsAffected()
	if err != nil {
		return fmt.Errorf("update book: %w", err)
	}
	if affected == 0 {
		return apperr.ErrNotFound
	}
	updated, err := r.FindByID(ctx, book.ID)
	if err != nil {
		return fmt.Errorf("update book: %w", err)
	}
	*book = *updated
	return nil
}

func (r *bookRepository) Delete(ctx context.Context, id int64) error {
	res, err := r.db.ExecContext(ctx, `DELETE FROM books WHERE id = ?`, id)
	if err != nil {
		return fmt.Errorf("delete book: %w", err)
	}
	affected, err := res.RowsAffected()
	if err != nil {
		return fmt.Errorf("delete book: %w", err)
	}
	if affected == 0 {
		return apperr.ErrNotFound
	}
	return nil
}

type rowScanner interface {
	Scan(dest ...any) error
}

func scanBook(row rowScanner) (*model.Book, error) {
	var b model.Book
	if err := row.Scan(
		&b.ID, &b.Title, &b.Author, &b.Rating, &b.Memo, &b.ISBN, &b.Publisher, &b.PublishedDate,
		&b.CreatedAt, &b.UpdatedAt,
	); err != nil {
		return nil, err
	}
	return &b, nil
}

func isUniqueConstraintErr(err error) bool {
	var sqliteErr *sqlite.Error
	if errors.As(err, &sqliteErr) {
		code := sqliteErr.Code()
		return code == sqlite3lib.SQLITE_CONSTRAINT_UNIQUE || code == sqlite3lib.SQLITE_CONSTRAINT
	}
	return false
}
