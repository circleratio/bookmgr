package repository

import (
	"context"
	"database/sql"
	"errors"
	"testing"

	"bookmgr/internal/apperr"
	"bookmgr/internal/model"
)

func setupTestDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open db: %v", err)
	}
	t.Cleanup(func() { db.Close() })

	if err := migrate(db, "../../db/migrations"); err != nil {
		t.Fatalf("migrate: %v", err)
	}
	return db
}

func strPtr(s string) *string { return &s }
func intPtr(i int) *int       { return &i }

func TestBookRepository_CreateAndFindByID(t *testing.T) {
	db := setupTestDB(t)
	repo := NewBookRepository(db)
	ctx := context.Background()

	book := &model.Book{
		Title:  "吾輩は猫である",
		Author: "夏目漱石",
		Rating: intPtr(5),
		ISBN:   strPtr("978-4-10-101035-9"),
	}
	if err := repo.Create(ctx, book); err != nil {
		t.Fatalf("create: %v", err)
	}
	if book.ID == 0 {
		t.Fatal("expected non-zero id after create")
	}

	found, err := repo.FindByID(ctx, book.ID)
	if err != nil {
		t.Fatalf("find by id: %v", err)
	}
	if found.Title != book.Title {
		t.Errorf("title = %q, want %q", found.Title, book.Title)
	}
}

func TestBookRepository_FindByID_NotFound(t *testing.T) {
	db := setupTestDB(t)
	repo := NewBookRepository(db)

	_, err := repo.FindByID(context.Background(), 999)
	if !errors.Is(err, apperr.ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
}

func TestBookRepository_FindByISBN(t *testing.T) {
	db := setupTestDB(t)
	repo := NewBookRepository(db)
	ctx := context.Background()

	book := &model.Book{Title: "吾輩は猫である", Author: "夏目漱石", ISBN: strPtr("978-4-10-101035-9")}
	if err := repo.Create(ctx, book); err != nil {
		t.Fatalf("create: %v", err)
	}

	// Scanned barcodes are hyphen-free digits; lookup should still match a
	// hyphenated ISBN stored via manual entry.
	found, err := repo.FindByISBN(ctx, "9784101010359")
	if err != nil {
		t.Fatalf("find by isbn: %v", err)
	}
	if found.ID != book.ID {
		t.Errorf("id = %d, want %d", found.ID, book.ID)
	}
}

func TestBookRepository_FindByISBN_NotFound(t *testing.T) {
	db := setupTestDB(t)
	repo := NewBookRepository(db)

	_, err := repo.FindByISBN(context.Background(), "9784101010359")
	if !errors.Is(err, apperr.ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
}

func TestBookRepository_Create_DuplicateISBN(t *testing.T) {
	db := setupTestDB(t)
	repo := NewBookRepository(db)
	ctx := context.Background()

	isbn := strPtr("978-4-10-101035-9")
	first := &model.Book{Title: "A", Author: "X", ISBN: isbn}
	if err := repo.Create(ctx, first); err != nil {
		t.Fatalf("create first: %v", err)
	}

	second := &model.Book{Title: "B", Author: "Y", ISBN: isbn}
	err := repo.Create(ctx, second)
	if !errors.Is(err, apperr.ErrConflict) {
		t.Fatalf("err = %v, want ErrConflict", err)
	}
}

func TestBookRepository_Create_MultipleNilISBN(t *testing.T) {
	db := setupTestDB(t)
	repo := NewBookRepository(db)
	ctx := context.Background()

	if err := repo.Create(ctx, &model.Book{Title: "A", Author: "X"}); err != nil {
		t.Fatalf("create first: %v", err)
	}
	if err := repo.Create(ctx, &model.Book{Title: "B", Author: "Y"}); err != nil {
		t.Fatalf("create second (nil isbn should not conflict): %v", err)
	}
}

func TestBookRepository_Update(t *testing.T) {
	db := setupTestDB(t)
	repo := NewBookRepository(db)
	ctx := context.Background()

	book := &model.Book{Title: "A", Author: "X"}
	if err := repo.Create(ctx, book); err != nil {
		t.Fatalf("create: %v", err)
	}

	book.Title = "B"
	if err := repo.Update(ctx, book); err != nil {
		t.Fatalf("update: %v", err)
	}

	found, err := repo.FindByID(ctx, book.ID)
	if err != nil {
		t.Fatalf("find by id: %v", err)
	}
	if found.Title != "B" {
		t.Errorf("title = %q, want %q", found.Title, "B")
	}
}

func TestBookRepository_Update_NotFound(t *testing.T) {
	db := setupTestDB(t)
	repo := NewBookRepository(db)

	err := repo.Update(context.Background(), &model.Book{ID: 999, Title: "A", Author: "X"})
	if !errors.Is(err, apperr.ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
}

func TestBookRepository_Delete(t *testing.T) {
	db := setupTestDB(t)
	repo := NewBookRepository(db)
	ctx := context.Background()

	book := &model.Book{Title: "A", Author: "X"}
	if err := repo.Create(ctx, book); err != nil {
		t.Fatalf("create: %v", err)
	}

	if err := repo.Delete(ctx, book.ID); err != nil {
		t.Fatalf("delete: %v", err)
	}

	_, err := repo.FindByID(ctx, book.ID)
	if !errors.Is(err, apperr.ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
}

func TestBookRepository_Delete_NotFound(t *testing.T) {
	db := setupTestDB(t)
	repo := NewBookRepository(db)

	err := repo.Delete(context.Background(), 999)
	if !errors.Is(err, apperr.ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
}

func TestBookRepository_List_SearchAndPagination(t *testing.T) {
	db := setupTestDB(t)
	repo := NewBookRepository(db)
	ctx := context.Background()

	titles := []struct{ title, author string }{
		{"吾輩は猫である", "夏目漱石"},
		{"坊っちゃん", "夏目漱石"},
		{"人間失格", "太宰治"},
	}
	for _, tc := range titles {
		if err := repo.Create(ctx, &model.Book{Title: tc.title, Author: tc.author}); err != nil {
			t.Fatalf("create: %v", err)
		}
	}

	books, total, err := repo.List(ctx, "夏目漱石", 1, 20)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if total != 2 {
		t.Errorf("total = %d, want 2", total)
	}
	if len(books) != 2 {
		t.Errorf("len(books) = %d, want 2", len(books))
	}

	books, total, err = repo.List(ctx, "", 1, 2)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if total != 3 {
		t.Errorf("total = %d, want 3", total)
	}
	if len(books) != 2 {
		t.Errorf("len(books) page 1 = %d, want 2", len(books))
	}

	books, _, err = repo.List(ctx, "", 2, 2)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if len(books) != 1 {
		t.Errorf("len(books) page 2 = %d, want 1", len(books))
	}
}
