package api

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"bookmgr/internal/service"
)

type BookHandler struct {
	service *service.BookService
}

func NewBookHandler(service *service.BookService) *BookHandler {
	return &BookHandler{service: service}
}

func (h *BookHandler) Register(rg *gin.RouterGroup) {
	rg.GET("/books", h.List)
	rg.GET("/books/:id", h.Get)
	rg.POST("/books", h.Create)
	rg.PUT("/books/:id", h.Update)
	rg.DELETE("/books/:id", h.Delete)
}

type bookRequest struct {
	Title         string  `json:"title"`
	Author        string  `json:"author"`
	Rating        *int    `json:"rating"`
	Memo          *string `json:"memo"`
	ISBN          *string `json:"isbn"`
	Publisher     *string `json:"publisher"`
	PublishedDate *string `json:"published_date"`
}

func (r bookRequest) toInput() service.BookInput {
	return service.BookInput{
		Title:         r.Title,
		Author:        r.Author,
		Rating:        r.Rating,
		Memo:          r.Memo,
		ISBN:          r.ISBN,
		Publisher:     r.Publisher,
		PublishedDate: r.PublishedDate,
	}
}

func (h *BookHandler) List(c *gin.Context) {
	q := c.Query("q")
	page, _ := strconv.Atoi(c.Query("page"))
	pageSize, _ := strconv.Atoi(c.Query("page_size"))

	books, pagination, err := h.service.List(c.Request.Context(), q, page, pageSize)
	if err != nil {
		respondError(c, err)
		return
	}
	respondList(c, books, pagination.Page, pagination.PageSize, pagination.Total)
}

func (h *BookHandler) Get(c *gin.Context) {
	id, err := parseID(c)
	if err != nil {
		respondError(c, err)
		return
	}
	book, err := h.service.Get(c.Request.Context(), id)
	if err != nil {
		respondError(c, err)
		return
	}
	respondData(c, http.StatusOK, book)
}

func (h *BookHandler) Create(c *gin.Context) {
	var req bookRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		respondError(c, badRequestErr(err))
		return
	}
	book, err := h.service.Create(c.Request.Context(), req.toInput())
	if err != nil {
		respondError(c, err)
		return
	}
	respondData(c, http.StatusCreated, book)
}

func (h *BookHandler) Update(c *gin.Context) {
	id, err := parseID(c)
	if err != nil {
		respondError(c, err)
		return
	}
	var req bookRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		respondError(c, badRequestErr(err))
		return
	}
	book, err := h.service.Update(c.Request.Context(), id, req.toInput())
	if err != nil {
		respondError(c, err)
		return
	}
	respondData(c, http.StatusOK, book)
}

func (h *BookHandler) Delete(c *gin.Context) {
	id, err := parseID(c)
	if err != nil {
		respondError(c, err)
		return
	}
	if err := h.service.Delete(c.Request.Context(), id); err != nil {
		respondError(c, err)
		return
	}
	c.Status(http.StatusNoContent)
}
