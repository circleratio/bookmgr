package main

import (
	"log"
	"os"

	"github.com/gin-gonic/gin"

	apihandler "bookmgr/internal/handler/api"
	webhandler "bookmgr/internal/handler/web"
	"bookmgr/internal/middleware"
	"bookmgr/internal/repository"
	"bookmgr/internal/service"
)

func main() {
	apiKey := os.Getenv("API_KEY")
	if apiKey == "" {
		log.Fatal("API_KEY environment variable is required")
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	dbPath := os.Getenv("DB_PATH")
	if dbPath == "" {
		dbPath = "db/bookmgr.db"
	}

	db, err := repository.Open(dbPath, "db/migrations")
	if err != nil {
		log.Fatalf("failed to open database: %v", err)
	}
	defer db.Close()

	bookRepo := repository.NewBookRepository(db)
	bookService := service.NewBookService(bookRepo)
	isbnLookupService := service.NewISBNLookupService(os.Getenv("GOOGLE_BOOKS_API_KEY"), "")

	renderer, err := webhandler.NewRenderer("templates")
	if err != nil {
		log.Fatalf("failed to load templates: %v", err)
	}

	r := gin.Default()
	r.Static("/static", "static")

	authHandler := webhandler.NewAuthHandler(apiKey, renderer)
	authHandler.Register(r)

	webAuthorized := r.Group("/")
	webAuthorized.Use(middleware.WebAuth(apiKey))
	webhandler.NewBookHandler(bookService, isbnLookupService, renderer).Register(webAuthorized)

	apiGroup := r.Group("/api")
	apiGroup.Use(middleware.APIKeyAuth(apiKey))
	apihandler.NewBookHandler(bookService).Register(apiGroup)
	apihandler.NewISBNLookupHandler(isbnLookupService).Register(apiGroup)

	log.Printf("listening on :%s", port)
	if err := r.Run(":" + port); err != nil {
		log.Fatalf("server error: %v", err)
	}
}
