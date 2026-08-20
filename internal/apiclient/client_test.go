package apiclient

import (
	"context"
	"errors"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"

	apihandler "bookmgr/internal/handler/api"
	"bookmgr/internal/middleware"
	"bookmgr/internal/repository"
	"bookmgr/internal/service"
)

const testAPIKey = "test-api-key"

func setupTestServer(t *testing.T) *httptest.Server {
	t.Helper()
	gin.SetMode(gin.TestMode)

	db, err := repository.Open(":memory:", "../../db/migrations")
	if err != nil {
		t.Fatalf("open db: %v", err)
	}
	t.Cleanup(func() { db.Close() })

	bookService := service.NewBookService(repository.NewBookRepository(db))

	r := gin.New()
	apiGroup := r.Group("/api")
	apiGroup.Use(middleware.APIKeyAuth(testAPIKey))
	apihandler.NewBookHandler(bookService).Register(apiGroup)

	srv := httptest.NewServer(r)
	t.Cleanup(srv.Close)
	return srv
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
