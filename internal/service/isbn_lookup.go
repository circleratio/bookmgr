package service

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	"bookmgr/internal/apperr"
)

const googleBooksBaseURL = "https://www.googleapis.com/books/v1/volumes"

// BookInfo is bibliographic data looked up from an external source (Google
// Books) to prefill the new-book form; it is not persisted directly.
type BookInfo struct {
	Title         string `json:"title"`
	Author        string `json:"author"`
	Publisher     string `json:"publisher"`
	PublishedDate string `json:"published_date"`
	ISBN          string `json:"isbn"`
}

type ISBNLookupService struct {
	httpClient *http.Client
	apiKey     string
	baseURL    string
}

// NewISBNLookupService creates a client for the Google Books API. apiKey may
// be empty (the API works unauthenticated, with lower rate limits). baseURL
// may be empty to use the real Google Books endpoint; tests can override it
// with an httptest.Server URL.
func NewISBNLookupService(apiKey, baseURL string) *ISBNLookupService {
	if baseURL == "" {
		baseURL = googleBooksBaseURL
	}
	return &ISBNLookupService{
		httpClient: &http.Client{Timeout: 5 * time.Second},
		apiKey:     apiKey,
		baseURL:    baseURL,
	}
}

type googleBooksResponse struct {
	Items []struct {
		VolumeInfo struct {
			Title               string   `json:"title"`
			Authors             []string `json:"authors"`
			Publisher           string   `json:"publisher"`
			PublishedDate       string   `json:"publishedDate"`
			IndustryIdentifiers []struct {
				Type       string `json:"type"`
				Identifier string `json:"identifier"`
			} `json:"industryIdentifiers"`
		} `json:"volumeInfo"`
	} `json:"items"`
}

func (s *ISBNLookupService) Lookup(ctx context.Context, isbn string) (*BookInfo, error) {
	normalized := strings.ReplaceAll(strings.TrimSpace(isbn), "-", "")
	if normalized == "" {
		return nil, apperr.NewValidationError("isbn is required")
	}

	q := url.Values{}
	q.Set("q", "isbn:"+normalized)
	if s.apiKey != "" {
		q.Set("key", s.apiKey)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, s.baseURL+"?"+q.Encode(), nil)
	if err != nil {
		return nil, fmt.Errorf("build google books request: %w", err)
	}

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("call google books api: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("google books api returned status %d", resp.StatusCode)
	}

	var parsed googleBooksResponse
	if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
		return nil, fmt.Errorf("decode google books response: %w", err)
	}

	if len(parsed.Items) == 0 {
		return nil, apperr.ErrNotFound
	}

	// A q=isbn:... search can return several candidate records for the same
	// book (e.g. from different regional catalogs), and the metadata each
	// one carries is inconsistent — one may have title/authors but no
	// publisher or date, while a later item does. Merge fields across all
	// returned items instead of trusting items[0] alone, keeping the first
	// non-empty value seen for each field.
	info := &BookInfo{}
	var isbn13, isbn10 string
	for _, item := range parsed.Items {
		v := item.VolumeInfo
		if info.Title == "" && v.Title != "" {
			info.Title = v.Title
		}
		if info.Author == "" && len(v.Authors) > 0 {
			info.Author = strings.Join(v.Authors, ",")
		}
		if info.Publisher == "" && v.Publisher != "" {
			info.Publisher = v.Publisher
		}
		if info.PublishedDate == "" && v.PublishedDate != "" {
			info.PublishedDate = v.PublishedDate
		}
		for _, id := range v.IndustryIdentifiers {
			switch id.Type {
			case "ISBN_13":
				if isbn13 == "" {
					isbn13 = id.Identifier
				}
			case "ISBN_10":
				if isbn10 == "" {
					isbn10 = id.Identifier
				}
			}
		}
	}

	info.PublishedDate = normalizePublishedDate(info.PublishedDate)
	info.ISBN = normalized
	switch {
	case isbn13 != "":
		info.ISBN = isbn13
	case isbn10 != "":
		info.ISBN = isbn10
	}

	return info, nil
}

// normalizePublishedDate pads a Google Books publishedDate (which may be a
// bare year "YYYY" or year-month "YYYY-MM") out to "YYYY-MM-DD" so it fits
// an HTML date input; a full date, or anything else, is passed through as-is.
func normalizePublishedDate(d string) string {
	switch len(d) {
	case 4:
		return d + "-01-01"
	case 7:
		return d + "-01"
	default:
		return d
	}
}
