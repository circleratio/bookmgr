package api

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"

	"bookmgr/internal/middleware"
	"bookmgr/internal/repository"
	"bookmgr/internal/service"
)

const testAPIKey = "test-api-key"

func setupRouter(t *testing.T) *gin.Engine {
	t.Helper()
	gin.SetMode(gin.TestMode)

	db, err := repository.Open(":memory:", "../../../db/migrations")
	if err != nil {
		t.Fatalf("open db: %v", err)
	}
	t.Cleanup(func() { db.Close() })

	bookService := service.NewBookService(repository.NewBookRepository(db))

	r := gin.New()
	apiGroup := r.Group("/api")
	apiGroup.Use(middleware.APIKeyAuth(testAPIKey))
	NewBookHandler(bookService).Register(apiGroup)
	return r
}

func doRequest(r *gin.Engine, method, path string, body any, withAuth bool) *httptest.ResponseRecorder {
	var reqBody *bytes.Buffer
	if body != nil {
		b, _ := json.Marshal(body)
		reqBody = bytes.NewBuffer(b)
	} else {
		reqBody = bytes.NewBuffer(nil)
	}
	req := httptest.NewRequest(method, path, reqBody)
	req.Header.Set("Content-Type", "application/json")
	if withAuth {
		req.Header.Set("X-API-Key", testAPIKey)
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func TestAPI_Unauthorized(t *testing.T) {
	r := setupRouter(t)
	w := doRequest(r, http.MethodGet, "/api/books", nil, false)
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want 401", w.Code)
	}
}

func TestAPI_CreateAndGet(t *testing.T) {
	r := setupRouter(t)

	createBody := map[string]any{
		"title":  "吾輩は猫である",
		"author": "夏目漱石",
	}
	w := doRequest(r, http.MethodPost, "/api/books", createBody, true)
	if w.Code != http.StatusCreated {
		t.Fatalf("create status = %d, want 201, body=%s", w.Code, w.Body.String())
	}

	var created struct {
		Data struct {
			ID int64 `json:"id"`
		} `json:"data"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &created); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if created.Data.ID == 0 {
		t.Fatal("expected non-zero id")
	}

	w = doRequest(r, http.MethodGet, "/api/books/"+jsonInt(created.Data.ID), nil, true)
	if w.Code != http.StatusOK {
		t.Fatalf("get status = %d, want 200, body=%s", w.Code, w.Body.String())
	}
}

func TestAPI_Get_NotFound(t *testing.T) {
	r := setupRouter(t)
	w := doRequest(r, http.MethodGet, "/api/books/999", nil, true)
	if w.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404, body=%s", w.Code, w.Body.String())
	}
}

func TestAPI_Create_ValidationError(t *testing.T) {
	r := setupRouter(t)
	w := doRequest(r, http.MethodPost, "/api/books", map[string]any{"title": ""}, true)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400, body=%s", w.Code, w.Body.String())
	}
}

func TestAPI_Create_ConflictISBN(t *testing.T) {
	r := setupRouter(t)
	body := map[string]any{"title": "A", "author": "X", "isbn": "9784101010359"}

	w := doRequest(r, http.MethodPost, "/api/books", body, true)
	if w.Code != http.StatusCreated {
		t.Fatalf("first create status = %d, want 201, body=%s", w.Code, w.Body.String())
	}

	w = doRequest(r, http.MethodPost, "/api/books", body, true)
	if w.Code != http.StatusConflict {
		t.Fatalf("second create status = %d, want 409, body=%s", w.Code, w.Body.String())
	}
}

func TestAPI_GetByISBN(t *testing.T) {
	r := setupRouter(t)
	body := map[string]any{"title": "A", "author": "X", "isbn": "978-4-10-101035-9"}
	doRequest(r, http.MethodPost, "/api/books", body, true)

	w := doRequest(r, http.MethodGet, "/api/books/by-isbn/9784101010359", nil, true)
	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200, body=%s", w.Code, w.Body.String())
	}
}

func TestAPI_GetByISBN_NotFound(t *testing.T) {
	r := setupRouter(t)
	w := doRequest(r, http.MethodGet, "/api/books/by-isbn/9784101010359", nil, true)
	if w.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404, body=%s", w.Code, w.Body.String())
	}
}

func TestAPI_List_SearchAndPagination(t *testing.T) {
	r := setupRouter(t)
	for _, title := range []string{"吾輩は猫である", "坊っちゃん", "人間失格"} {
		doRequest(r, http.MethodPost, "/api/books", map[string]any{"title": title, "author": "someone"}, true)
	}

	w := doRequest(r, http.MethodGet, "/api/books?page=1&page_size=2", nil, true)
	if w.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200, body=%s", w.Code, w.Body.String())
	}

	var resp struct {
		Data       []any `json:"data"`
		Pagination struct {
			Total int `json:"total"`
		} `json:"pagination"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if resp.Pagination.Total != 3 {
		t.Errorf("total = %d, want 3", resp.Pagination.Total)
	}
	if len(resp.Data) != 2 {
		t.Errorf("len(data) = %d, want 2", len(resp.Data))
	}
}

func TestAPI_Delete(t *testing.T) {
	r := setupRouter(t)
	w := doRequest(r, http.MethodPost, "/api/books", map[string]any{"title": "A", "author": "X"}, true)
	var created struct {
		Data struct {
			ID int64 `json:"id"`
		} `json:"data"`
	}
	json.Unmarshal(w.Body.Bytes(), &created)

	w = doRequest(r, http.MethodDelete, "/api/books/"+jsonInt(created.Data.ID), nil, true)
	if w.Code != http.StatusNoContent {
		t.Fatalf("delete status = %d, want 204", w.Code)
	}

	w = doRequest(r, http.MethodGet, "/api/books/"+jsonInt(created.Data.ID), nil, true)
	if w.Code != http.StatusNotFound {
		t.Fatalf("get after delete status = %d, want 404", w.Code)
	}
}

func jsonInt(id int64) string {
	b, _ := json.Marshal(id)
	return string(b)
}
