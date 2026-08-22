package apiclient

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"sync"
	"testing"
)

const testAPIKey = "test-api-key"

// fakeServer is a minimal stand-in for the real bookmgr API, just enough to
// exercise this Go client's request building and response/error parsing.
// It intentionally does not depend on the server implementation (which may
// be written in any language) so this test only verifies the HTTP contract.
type fakeServer struct {
	mu     sync.Mutex
	books  map[int64]map[string]any
	nextID int64
}

func setupTestServer(t *testing.T) *httptest.Server {
	t.Helper()
	fs := &fakeServer{books: make(map[int64]map[string]any)}
	srv := httptest.NewServer(http.HandlerFunc(fs.handle))
	t.Cleanup(srv.Close)
	return srv
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(body)
}

func writeError(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, map[string]any{
		"error": map[string]any{"code": code, "message": message},
	})
}

func (fs *fakeServer) handle(w http.ResponseWriter, r *http.Request) {
	if r.Header.Get("X-API-Key") != testAPIKey {
		writeError(w, http.StatusUnauthorized, "UNAUTHORIZED", "invalid or missing API key")
		return
	}

	fs.mu.Lock()
	defer fs.mu.Unlock()

	switch {
	case r.Method == http.MethodPost && r.URL.Path == "/api/books":
		fs.create(w, r)
	case r.Method == http.MethodGet && r.URL.Path == "/api/books":
		fs.list(w, r)
	case r.Method == http.MethodGet && strings.HasPrefix(r.URL.Path, "/api/books/"):
		fs.get(w, idFromPath(r.URL.Path))
	case r.Method == http.MethodPut && strings.HasPrefix(r.URL.Path, "/api/books/"):
		fs.update(w, r, idFromPath(r.URL.Path))
	case r.Method == http.MethodDelete && strings.HasPrefix(r.URL.Path, "/api/books/"):
		fs.delete(w, idFromPath(r.URL.Path))
	default:
		http.NotFound(w, r)
	}
}

func idFromPath(path string) int64 {
	id, _ := strconv.ParseInt(strings.TrimPrefix(path, "/api/books/"), 10, 64)
	return id
}

func (fs *fakeServer) create(w http.ResponseWriter, r *http.Request) {
	var input map[string]any
	json.NewDecoder(r.Body).Decode(&input)

	title, _ := input["title"].(string)
	if strings.TrimSpace(title) == "" {
		writeError(w, http.StatusBadRequest, "VALIDATION_ERROR", "title is required")
		return
	}

	fs.nextID++
	input["id"] = fs.nextID
	fs.books[fs.nextID] = input
	writeJSON(w, http.StatusCreated, map[string]any{"data": input})
}

func (fs *fakeServer) get(w http.ResponseWriter, id int64) {
	book, ok := fs.books[id]
	if !ok {
		writeError(w, http.StatusNotFound, "NOT_FOUND", "book not found")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": book})
}

func (fs *fakeServer) update(w http.ResponseWriter, r *http.Request, id int64) {
	if _, ok := fs.books[id]; !ok {
		writeError(w, http.StatusNotFound, "NOT_FOUND", "book not found")
		return
	}
	var input map[string]any
	json.NewDecoder(r.Body).Decode(&input)
	input["id"] = id
	fs.books[id] = input
	writeJSON(w, http.StatusOK, map[string]any{"data": input})
}

func (fs *fakeServer) delete(w http.ResponseWriter, id int64) {
	if _, ok := fs.books[id]; !ok {
		writeError(w, http.StatusNotFound, "NOT_FOUND", "book not found")
		return
	}
	delete(fs.books, id)
	w.WriteHeader(http.StatusNoContent)
}

func (fs *fakeServer) list(w http.ResponseWriter, r *http.Request) {
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	if page < 1 {
		page = 1
	}
	pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))
	if pageSize < 1 {
		pageSize = 20
	}

	ids := make([]int64, 0, len(fs.books))
	for id := range fs.books {
		ids = append(ids, id)
	}
	// Deterministic order matching the real API's `id DESC`.
	for i := 0; i < len(ids); i++ {
		for j := i + 1; j < len(ids); j++ {
			if ids[j] > ids[i] {
				ids[i], ids[j] = ids[j], ids[i]
			}
		}
	}

	total := len(ids)
	start := (page - 1) * pageSize
	end := start + pageSize
	if start > total {
		start = total
	}
	if end > total {
		end = total
	}

	books := make([]map[string]any, 0, end-start)
	for _, id := range ids[start:end] {
		books = append(books, fs.books[id])
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"data": books,
		"pagination": map[string]any{
			"page": page, "page_size": pageSize, "total": total,
		},
	})
}

func strPtr(s string) *string { return &s }
func intPtr(i int) *int       { return &i }

func TestClient_CreateGetUpdateDelete(t *testing.T) {
	srv := setupTestServer(t)
	client := New(srv.URL, testAPIKey)
	ctx := context.Background()

	created, err := client.Create(ctx, BookInput{
		Title:  "吾輩は猫である",
		Author: "夏目漱石",
		Rating: intPtr(5),
		ISBN:   strPtr("9784101010359"),
	})
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	if created.ID == 0 {
		t.Fatal("expected non-zero id")
	}

	got, err := client.Get(ctx, created.ID)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if got.Title != "吾輩は猫である" {
		t.Errorf("title = %q", got.Title)
	}

	updated, err := client.Update(ctx, created.ID, BookInput{Title: "坊っちゃん", Author: "夏目漱石"})
	if err != nil {
		t.Fatalf("update: %v", err)
	}
	if updated.Title != "坊っちゃん" {
		t.Errorf("title after update = %q", updated.Title)
	}

	if err := client.Delete(ctx, created.ID); err != nil {
		t.Fatalf("delete: %v", err)
	}

	_, err = client.Get(ctx, created.ID)
	var apiErr *APIError
	if !errors.As(err, &apiErr) || apiErr.StatusCode != 404 {
		t.Fatalf("err = %v, want 404 APIError", err)
	}
}

func TestClient_Create_ValidationError(t *testing.T) {
	srv := setupTestServer(t)
	client := New(srv.URL, testAPIKey)

	_, err := client.Create(context.Background(), BookInput{Title: "", Author: "X"})
	var apiErr *APIError
	if !errors.As(err, &apiErr) || apiErr.StatusCode != 400 || apiErr.Code != "VALIDATION_ERROR" {
		t.Fatalf("err = %v, want 400 VALIDATION_ERROR", err)
	}
}

func TestClient_Unauthorized(t *testing.T) {
	srv := setupTestServer(t)
	client := New(srv.URL, "wrong-key")

	_, err := client.List(context.Background(), "", 0, 0)
	var apiErr *APIError
	if !errors.As(err, &apiErr) || apiErr.StatusCode != 401 {
		t.Fatalf("err = %v, want 401 APIError", err)
	}
}

func TestClient_List_SearchAndPagination(t *testing.T) {
	srv := setupTestServer(t)
	client := New(srv.URL, testAPIKey)
	ctx := context.Background()

	for _, title := range []string{"吾輩は猫である", "坊っちゃん", "人間失格"} {
		if _, err := client.Create(ctx, BookInput{Title: title, Author: "someone"}); err != nil {
			t.Fatalf("create: %v", err)
		}
	}

	result, err := client.List(ctx, "", 1, 2)
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if result.Pagination.Total != 3 {
		t.Errorf("total = %d, want 3", result.Pagination.Total)
	}
	if len(result.Books) != 2 {
		t.Errorf("len(books) = %d, want 2", len(result.Books))
	}
}
