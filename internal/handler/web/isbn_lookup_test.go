package web

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"

	"bookmgr/internal/repository"
	"bookmgr/internal/service"
)

func setupBookHandlerRouter(t *testing.T, lookup *service.ISBNLookupService) *gin.Engine {
	t.Helper()
	gin.SetMode(gin.TestMode)

	db, err := repository.Open(":memory:", "../../../db/migrations")
	if err != nil {
		t.Fatalf("open db: %v", err)
	}
	t.Cleanup(func() { db.Close() })
	bookService := service.NewBookService(repository.NewBookRepository(db))

	renderer, err := NewRenderer("../../../templates")
	if err != nil {
		t.Fatalf("new renderer: %v", err)
	}

	r := gin.New()
	NewBookHandler(bookService, lookup, renderer).Register(r)
	return r
}

func TestBookHandler_ISBNLookup_Success(t *testing.T) {
	googleBooks := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{
			"items": [{
				"volumeInfo": {
					"title": "吾輩は猫である",
					"authors": ["夏目漱石"],
					"publisher": "新潮社",
					"publishedDate": "2003-05-01",
					"industryIdentifiers": [
						{"type": "ISBN_13", "identifier": "9784101010359"}
					]
				}
			}]
		}`))
	}))
	t.Cleanup(googleBooks.Close)

	r := setupBookHandlerRouter(t, service.NewISBNLookupService("", googleBooks.URL))

	req := httptest.NewRequest(http.MethodGet, "/books/isbn-lookup?isbn=9784101010359", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200, body=%s", w.Code, w.Body.String())
	}

	var resp struct {
		Data service.BookInfo `json:"data"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if resp.Data.Title != "吾輩は猫である" {
		t.Errorf("title = %q", resp.Data.Title)
	}
	if resp.Data.ISBN != "9784101010359" {
		t.Errorf("isbn = %q", resp.Data.ISBN)
	}
}

func TestBookHandler_ISBNLookup_NotFound(t *testing.T) {
	googleBooks := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"items": []}`))
	}))
	t.Cleanup(googleBooks.Close)

	r := setupBookHandlerRouter(t, service.NewISBNLookupService("", googleBooks.URL))

	req := httptest.NewRequest(http.MethodGet, "/books/isbn-lookup?isbn=0000000000000", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404, body=%s", w.Code, w.Body.String())
	}
}

func TestBookHandler_ISBNLookup_MissingParam(t *testing.T) {
	r := setupBookHandlerRouter(t, service.NewISBNLookupService("", "http://unused.invalid"))

	req := httptest.NewRequest(http.MethodGet, "/books/isbn-lookup", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400, body=%s", w.Code, w.Body.String())
	}
}
