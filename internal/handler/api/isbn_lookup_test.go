package api

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"

	"bookmgr/internal/middleware"
	"bookmgr/internal/service"
)

func setupISBNLookupRouter(t *testing.T, googleBooksURL string) *gin.Engine {
	t.Helper()
	gin.SetMode(gin.TestMode)

	lookup := service.NewISBNLookupService("", googleBooksURL)

	r := gin.New()
	apiGroup := r.Group("/api")
	apiGroup.Use(middleware.APIKeyAuth(testAPIKey))
	NewISBNLookupHandler(lookup).Register(apiGroup)
	return r
}

func TestAPI_ISBNLookup_Unauthorized(t *testing.T) {
	r := setupISBNLookupRouter(t, "http://unused.invalid")
	w := doRequest(r, http.MethodGet, "/api/isbn-lookup?isbn=9784101010359", nil, false)
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", w.Code)
	}
}

func TestAPI_ISBNLookup_Success(t *testing.T) {
	googleBooks := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{
			"items": [{
				"volumeInfo": {
					"title": "吾輩は猫である",
					"authors": ["夏目漱石"],
					"publisher": "新潮社",
					"publishedDate": "2003-05-01",
					"industryIdentifiers": [{"type": "ISBN_13", "identifier": "9784101010359"}]
				}
			}]
		}`))
	}))
	t.Cleanup(googleBooks.Close)

	r := setupISBNLookupRouter(t, googleBooks.URL)
	w := doRequest(r, http.MethodGet, "/api/isbn-lookup?isbn=9784101010359", nil, true)
	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200, body=%s", w.Code, w.Body.String())
	}
}

func TestAPI_ISBNLookup_NotFound(t *testing.T) {
	googleBooks := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"items": []}`))
	}))
	t.Cleanup(googleBooks.Close)

	r := setupISBNLookupRouter(t, googleBooks.URL)
	w := doRequest(r, http.MethodGet, "/api/isbn-lookup?isbn=0000000000000", nil, true)
	if w.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404, body=%s", w.Code, w.Body.String())
	}
}

func TestAPI_ISBNLookup_MissingParam(t *testing.T) {
	r := setupISBNLookupRouter(t, "http://unused.invalid")
	w := doRequest(r, http.MethodGet, "/api/isbn-lookup", nil, true)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400, body=%s", w.Code, w.Body.String())
	}
}
