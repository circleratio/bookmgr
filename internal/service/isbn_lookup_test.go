package service

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"bookmgr/internal/apperr"
)

func newFakeGoogleBooksServer(t *testing.T, status int, body string) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		w.Write([]byte(body))
	}))
	t.Cleanup(srv.Close)
	return srv
}

func TestISBNLookupService_Lookup_Success(t *testing.T) {
	srv := newFakeGoogleBooksServer(t, http.StatusOK, `{
		"items": [{
			"volumeInfo": {
				"title": "吾輩は猫である",
				"authors": ["夏目漱石"],
				"publisher": "新潮社",
				"publishedDate": "2003-05-01",
				"industryIdentifiers": [
					{"type": "ISBN_10", "identifier": "4101010351"},
					{"type": "ISBN_13", "identifier": "9784101010359"}
				]
			}
		}]
	}`)

	svc := NewISBNLookupService("", srv.URL)
	info, err := svc.Lookup(context.Background(), "978-4-10-101035-9")
	if err != nil {
		t.Fatalf("lookup: %v", err)
	}
	if info.Title != "吾輩は猫である" {
		t.Errorf("title = %q", info.Title)
	}
	if info.Author != "夏目漱石" {
		t.Errorf("author = %q", info.Author)
	}
	if info.Publisher != "新潮社" {
		t.Errorf("publisher = %q", info.Publisher)
	}
	if info.PublishedDate != "2003-05-01" {
		t.Errorf("published_date = %q", info.PublishedDate)
	}
	if info.ISBN != "9784101010359" {
		t.Errorf("isbn = %q, want ISBN_13 preferred", info.ISBN)
	}
}

func TestISBNLookupService_Lookup_MultipleAuthorsJoined(t *testing.T) {
	srv := newFakeGoogleBooksServer(t, http.StatusOK, `{
		"items": [{"volumeInfo": {"title": "共著本", "authors": ["著者A", "著者B"]}}]
	}`)

	svc := NewISBNLookupService("", srv.URL)
	info, err := svc.Lookup(context.Background(), "9780000000002")
	if err != nil {
		t.Fatalf("lookup: %v", err)
	}
	if info.Author != "著者A,著者B" {
		t.Errorf("author = %q, want %q", info.Author, "著者A,著者B")
	}
}

func TestISBNLookupService_Lookup_FallsBackToISBN10ThenInput(t *testing.T) {
	srv := newFakeGoogleBooksServer(t, http.StatusOK, `{
		"items": [{"volumeInfo": {
			"title": "T", "authors": ["A"],
			"industryIdentifiers": [{"type": "ISBN_10", "identifier": "4101010351"}]
		}}]
	}`)
	svc := NewISBNLookupService("", srv.URL)
	info, err := svc.Lookup(context.Background(), "4101010351")
	if err != nil {
		t.Fatalf("lookup: %v", err)
	}
	if info.ISBN != "4101010351" {
		t.Errorf("isbn = %q, want ISBN_10 fallback", info.ISBN)
	}
}

func TestISBNLookupService_Lookup_PublishedDateNormalization(t *testing.T) {
	cases := []struct {
		in, want string
	}{
		{"2003", "2003-01-01"},
		{"2003-05", "2003-05-01"},
		{"2003-05-01", "2003-05-01"},
	}
	for _, tc := range cases {
		srv := newFakeGoogleBooksServer(t, http.StatusOK, `{"items":[{"volumeInfo":{"title":"T","authors":["A"],"publishedDate":"`+tc.in+`"}}]}`)
		svc := NewISBNLookupService("", srv.URL)
		info, err := svc.Lookup(context.Background(), "9780000000002")
		if err != nil {
			t.Fatalf("lookup(%q): %v", tc.in, err)
		}
		if info.PublishedDate != tc.want {
			t.Errorf("published_date(%q) = %q, want %q", tc.in, info.PublishedDate, tc.want)
		}
	}
}

func TestISBNLookupService_Lookup_NotFound(t *testing.T) {
	srv := newFakeGoogleBooksServer(t, http.StatusOK, `{"items": []}`)
	svc := NewISBNLookupService("", srv.URL)
	_, err := svc.Lookup(context.Background(), "9780000000000")
	if !errors.Is(err, apperr.ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
}

func TestISBNLookupService_Lookup_EmptyISBN(t *testing.T) {
	svc := NewISBNLookupService("", "http://unused.invalid")
	_, err := svc.Lookup(context.Background(), "  ")
	if !errors.Is(err, apperr.ErrValidation) {
		t.Fatalf("err = %v, want ErrValidation", err)
	}
}

func TestISBNLookupService_Lookup_UpstreamError(t *testing.T) {
	srv := newFakeGoogleBooksServer(t, http.StatusInternalServerError, `{}`)
	svc := NewISBNLookupService("", srv.URL)
	_, err := svc.Lookup(context.Background(), "9780000000000")
	if err == nil {
		t.Fatal("expected error for non-200 upstream response")
	}
}

func TestISBNLookupService_Lookup_APIKeyPassedAsQueryParam(t *testing.T) {
	var gotKey string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotKey = r.URL.Query().Get("key")
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"items":[{"volumeInfo":{"title":"T","authors":["A"]}}]}`))
	}))
	t.Cleanup(srv.Close)

	svc := NewISBNLookupService("my-google-key", srv.URL)
	if _, err := svc.Lookup(context.Background(), "9780000000000"); err != nil {
		t.Fatalf("lookup: %v", err)
	}
	if gotKey != "my-google-key" {
		t.Errorf("key param = %q, want %q", gotKey, "my-google-key")
	}
}
