package service

import (
	"context"
	"errors"
	"testing"

	"bookmgr/internal/apperr"
	"bookmgr/internal/model"
)

type fakeRepo struct {
	books  map[int64]*model.Book
	nextID int64
}

func newFakeRepo() *fakeRepo {
	return &fakeRepo{books: make(map[int64]*model.Book)}
}

func (r *fakeRepo) List(ctx context.Context, query string, page, pageSize int) ([]model.Book, int, error) {
	var result []model.Book
	for _, b := range r.books {
		result = append(result, *b)
	}
	return result, len(result), nil
}

func (r *fakeRepo) FindByID(ctx context.Context, id int64) (*model.Book, error) {
	b, ok := r.books[id]
	if !ok {
		return nil, apperr.ErrNotFound
	}
	return b, nil
}

func (r *fakeRepo) Create(ctx context.Context, book *model.Book) error {
	for _, b := range r.books {
		if book.ISBN != nil && b.ISBN != nil && *b.ISBN == *book.ISBN {
			return apperr.NewConflictError("isbn already exists")
		}
	}
	r.nextID++
	book.ID = r.nextID
	r.books[book.ID] = book
	return nil
}

func (r *fakeRepo) Update(ctx context.Context, book *model.Book) error {
	if _, ok := r.books[book.ID]; !ok {
		return apperr.ErrNotFound
	}
	r.books[book.ID] = book
	return nil
}

func (r *fakeRepo) Delete(ctx context.Context, id int64) error {
	if _, ok := r.books[id]; !ok {
		return apperr.ErrNotFound
	}
	delete(r.books, id)
	return nil
}

func validInput() BookInput {
	return BookInput{Title: "吾輩は猫である", Author: "夏目漱石"}
}

func TestBookService_Create_Valid(t *testing.T) {
	svc := NewBookService(newFakeRepo())
	book, err := svc.Create(context.Background(), validInput())
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if book.ID == 0 {
		t.Error("expected non-zero id")
	}
}

func TestBookService_Create_TitleRequired(t *testing.T) {
	svc := NewBookService(newFakeRepo())
	input := validInput()
	input.Title = "  "
	_, err := svc.Create(context.Background(), input)
	if !errors.Is(err, apperr.ErrValidation) {
		t.Fatalf("err = %v, want ErrValidation", err)
	}
}

func TestBookService_Create_AuthorRequired(t *testing.T) {
	svc := NewBookService(newFakeRepo())
	input := validInput()
	input.Author = ""
	_, err := svc.Create(context.Background(), input)
	if !errors.Is(err, apperr.ErrValidation) {
		t.Fatalf("err = %v, want ErrValidation", err)
	}
}

func TestBookService_Create_RatingBoundaries(t *testing.T) {
	cases := []struct {
		rating  int
		wantErr bool
	}{
		{0, true},
		{1, false},
		{5, false},
		{6, true},
	}
	for _, tc := range cases {
		svc := NewBookService(newFakeRepo())
		input := validInput()
		input.Rating = &tc.rating
		_, err := svc.Create(context.Background(), input)
		if tc.wantErr && !errors.Is(err, apperr.ErrValidation) {
			t.Errorf("rating=%d: err = %v, want ErrValidation", tc.rating, err)
		}
		if !tc.wantErr && err != nil {
			t.Errorf("rating=%d: unexpected err = %v", tc.rating, err)
		}
	}
}

func TestBookService_Create_ISBN(t *testing.T) {
	cases := []struct {
		name    string
		isbn    string
		wantErr bool
	}{
		{"10 digits no hyphen", "4101010351", false},
		{"13 digits no hyphen", "9784101010359", false},
		{"13 digits with hyphens", "978-4-10-101035-9", false},
		{"10 digits with trailing X", "410101003X", false},
		{"10 digits with trailing lowercase x", "410101003x", false},
		{"10 digits with hyphens and trailing X", "4-10-101003-X", false},
		{"X in non-final position", "41010100X1", true},
		{"13 digits with trailing X", "978410101003X", true},
		{"too short", "12345", true},
		{"non-numeric", "abcdefghij", true},
		{"11 digits", "12345678901", true},
	}
	for _, tc := range cases {
		svc := NewBookService(newFakeRepo())
		input := validInput()
		input.ISBN = &tc.isbn
		_, err := svc.Create(context.Background(), input)
		if tc.wantErr && !errors.Is(err, apperr.ErrValidation) {
			t.Errorf("%s: err = %v, want ErrValidation", tc.name, err)
		}
		if !tc.wantErr && err != nil {
			t.Errorf("%s: unexpected err = %v", tc.name, err)
		}
	}
}

func TestBookService_Create_EmptyOptionalFieldsBecomeNil(t *testing.T) {
	svc := NewBookService(newFakeRepo())
	input := validInput()
	empty := "   "
	input.Memo = &empty
	input.ISBN = &empty
	book, err := svc.Create(context.Background(), input)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if book.Memo != nil {
		t.Errorf("Memo = %v, want nil", *book.Memo)
	}
	if book.ISBN != nil {
		t.Errorf("ISBN = %v, want nil", *book.ISBN)
	}
}

func TestBookService_Create_PublishedDateFormat(t *testing.T) {
	cases := []struct {
		date    string
		wantErr bool
	}{
		{"2003-05-01", false},
		{"2003/05/01", true},
		{"not-a-date", true},
		{"2003-13-40", true},
	}
	for _, tc := range cases {
		svc := NewBookService(newFakeRepo())
		input := validInput()
		input.PublishedDate = &tc.date
		_, err := svc.Create(context.Background(), input)
		if tc.wantErr && !errors.Is(err, apperr.ErrValidation) {
			t.Errorf("date=%q: err = %v, want ErrValidation", tc.date, err)
		}
		if !tc.wantErr && err != nil {
			t.Errorf("date=%q: unexpected err = %v", tc.date, err)
		}
	}
}

func TestBookService_Create_DuplicateISBNConflict(t *testing.T) {
	repo := newFakeRepo()
	svc := NewBookService(repo)
	isbn := "9784101010359"

	input := validInput()
	input.ISBN = &isbn
	if _, err := svc.Create(context.Background(), input); err != nil {
		t.Fatalf("create first: %v", err)
	}

	_, err := svc.Create(context.Background(), input)
	if !errors.Is(err, apperr.ErrConflict) {
		t.Fatalf("err = %v, want ErrConflict", err)
	}
}

func TestBookService_List_DefaultsAndClamping(t *testing.T) {
	svc := NewBookService(newFakeRepo())

	_, pagination, err := svc.List(context.Background(), "", 0, 0)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if pagination.Page != 1 {
		t.Errorf("page = %d, want 1", pagination.Page)
	}
	if pagination.PageSize != DefaultPageSize {
		t.Errorf("page size = %d, want %d", pagination.PageSize, DefaultPageSize)
	}

	_, pagination, err = svc.List(context.Background(), "", 1, 500)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if pagination.PageSize != DefaultPageSize {
		t.Errorf("page size = %d, want default fallback %d", pagination.PageSize, DefaultPageSize)
	}
}

func TestBookService_Delete_NotFound(t *testing.T) {
	svc := NewBookService(newFakeRepo())
	err := svc.Delete(context.Background(), 999)
	if !errors.Is(err, apperr.ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
}
