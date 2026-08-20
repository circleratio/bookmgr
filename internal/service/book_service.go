package service

import (
	"context"
	"regexp"
	"strings"
	"time"

	"bookmgr/internal/apperr"
	"bookmgr/internal/model"
	"bookmgr/internal/repository"
)

const (
	DefaultPageSize = 20
	MaxPageSize     = 100
)

var publishedDatePattern = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}$`)

// BookInput carries book fields as submitted by API/form clients, before
// validation and normalization into a model.Book.
type BookInput struct {
	Title         string
	Author        string
	Rating        *int
	Memo          *string
	ISBN          *string
	Publisher     *string
	PublishedDate *string
}

type Pagination struct {
	Page     int
	PageSize int
	Total    int
}

type BookService struct {
	repo repository.BookRepository
}

func NewBookService(repo repository.BookRepository) *BookService {
	return &BookService{repo: repo}
}

func (s *BookService) List(ctx context.Context, query string, page, pageSize int) ([]model.Book, Pagination, error) {
	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > MaxPageSize {
		pageSize = DefaultPageSize
	}

	books, total, err := s.repo.List(ctx, query, page, pageSize)
	if err != nil {
		return nil, Pagination{}, err
	}
	return books, Pagination{Page: page, PageSize: pageSize, Total: total}, nil
}

func (s *BookService) Get(ctx context.Context, id int64) (*model.Book, error) {
	return s.repo.FindByID(ctx, id)
}

func (s *BookService) Create(ctx context.Context, input BookInput) (*model.Book, error) {
	book, err := validateInput(input)
	if err != nil {
		return nil, err
	}
	if err := s.repo.Create(ctx, book); err != nil {
		return nil, err
	}
	return book, nil
}

func (s *BookService) Update(ctx context.Context, id int64, input BookInput) (*model.Book, error) {
	book, err := validateInput(input)
	if err != nil {
		return nil, err
	}
	book.ID = id
	if err := s.repo.Update(ctx, book); err != nil {
		return nil, err
	}
	return book, nil
}

func (s *BookService) Delete(ctx context.Context, id int64) error {
	return s.repo.Delete(ctx, id)
}

func validateInput(input BookInput) (*model.Book, error) {
	title := strings.TrimSpace(input.Title)
	if title == "" {
		return nil, apperr.NewValidationError("title is required")
	}
	if len([]rune(title)) > 255 {
		return nil, apperr.NewValidationError("title must be at most 255 characters")
	}

	author := strings.TrimSpace(input.Author)
	if author == "" {
		return nil, apperr.NewValidationError("author is required")
	}
	if len([]rune(author)) > 255 {
		return nil, apperr.NewValidationError("author must be at most 255 characters")
	}

	if input.Rating != nil && (*input.Rating < 1 || *input.Rating > 5) {
		return nil, apperr.NewValidationError("rating must be between 1 and 5")
	}

	memo := normalizeOptional(input.Memo)
	if memo != nil && len([]rune(*memo)) > 2000 {
		return nil, apperr.NewValidationError("memo must be at most 2000 characters")
	}

	isbn := normalizeOptional(input.ISBN)
	if isbn != nil {
		digits := strings.ReplaceAll(*isbn, "-", "")
		if !isAllDigits(digits) || (len(digits) != 10 && len(digits) != 13) {
			return nil, apperr.NewValidationError("isbn must be 10 or 13 digits (hyphens allowed)")
		}
	}

	publisher := normalizeOptional(input.Publisher)
	if publisher != nil && len([]rune(*publisher)) > 255 {
		return nil, apperr.NewValidationError("publisher must be at most 255 characters")
	}

	publishedDate := normalizeOptional(input.PublishedDate)
	if publishedDate != nil {
		if !publishedDatePattern.MatchString(*publishedDate) {
			return nil, apperr.NewValidationError("published_date must be in YYYY-MM-DD format")
		}
		if _, err := time.Parse("2006-01-02", *publishedDate); err != nil {
			return nil, apperr.NewValidationError("published_date must be a valid date")
		}
	}

	return &model.Book{
		Title:         title,
		Author:        author,
		Rating:        input.Rating,
		Memo:          memo,
		ISBN:          isbn,
		Publisher:     publisher,
		PublishedDate: publishedDate,
	}, nil
}

// normalizeOptional trims whitespace and converts an empty result to nil so
// optional fields are stored as SQL NULL rather than an empty string.
func normalizeOptional(s *string) *string {
	if s == nil {
		return nil
	}
	trimmed := strings.TrimSpace(*s)
	if trimmed == "" {
		return nil
	}
	return &trimmed
}

func isAllDigits(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if r < '0' || r > '9' {
			return false
		}
	}
	return true
}
