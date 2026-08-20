package web

import (
	"errors"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"

	"bookmgr/internal/apperr"
	"bookmgr/internal/service"
)

type BookHandler struct {
	service  *service.BookService
	lookup   *service.ISBNLookupService
	renderer *Renderer
}

func NewBookHandler(service *service.BookService, lookup *service.ISBNLookupService, renderer *Renderer) *BookHandler {
	return &BookHandler{service: service, lookup: lookup, renderer: renderer}
}

func (h *BookHandler) Register(r gin.IRouter) {
	r.GET("/", h.List)
	r.GET("/books/new", h.NewForm)
	r.POST("/books", h.Create)
	r.GET("/books/:id/edit", h.EditForm)
	r.POST("/books/:id", h.Update)
	r.POST("/books/:id/delete", h.Delete)
	r.GET("/books/isbn-lookup", h.ISBNLookup)
}

func (h *BookHandler) ISBNLookup(c *gin.Context) {
	info, err := h.lookup.Lookup(c.Request.Context(), c.Query("isbn"))
	if err != nil {
		status := http.StatusBadGateway
		message := "書誌情報の取得に失敗しました"
		switch {
		case errors.Is(err, apperr.ErrValidation):
			status = http.StatusBadRequest
			message = err.Error()
		case errors.Is(err, apperr.ErrNotFound):
			status = http.StatusNotFound
			message = "該当する書籍が見つかりませんでした"
		}
		c.JSON(status, gin.H{"error": message})
		return
	}
	c.JSON(http.StatusOK, gin.H{"data": info})
}

func (h *BookHandler) List(c *gin.Context) {
	q := c.Query("q")
	page, _ := strconv.Atoi(c.Query("page"))

	books, pagination, err := h.service.List(c.Request.Context(), q, page, 0)
	if err != nil {
		h.renderer.HTML(c, http.StatusInternalServerError, "books/list.html", gin.H{"Error": "予期しないエラーが発生しました"})
		return
	}

	totalPages := (pagination.Total + pagination.PageSize - 1) / pagination.PageSize
	if totalPages < 1 {
		totalPages = 1
	}

	h.renderer.HTML(c, http.StatusOK, "books/list.html", gin.H{
		"Books":      books,
		"Query":      q,
		"Page":       pagination.Page,
		"TotalPages": totalPages,
		"Total":      pagination.Total,
	})
}

func (h *BookHandler) NewForm(c *gin.Context) {
	h.renderer.HTML(c, http.StatusOK, "books/form.html", gin.H{
		"IsNew": true,
		"ID":    int64(0),
	})
}

func (h *BookHandler) Create(c *gin.Context) {
	input := bindBookForm(c)
	book, err := h.service.Create(c.Request.Context(), input)
	if err != nil {
		h.renderer.HTML(c, errStatus(err), "books/form.html", gin.H{
			"IsNew":  true,
			"ID":     int64(0),
			"Error":  errMessage(err),
			"Values": input,
		})
		return
	}
	c.Redirect(http.StatusFound, "/books/"+strconv.FormatInt(book.ID, 10)+"/edit")
}

func (h *BookHandler) EditForm(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.Redirect(http.StatusFound, "/")
		return
	}
	book, err := h.service.Get(c.Request.Context(), id)
	if err != nil {
		h.renderer.HTML(c, errStatus(err), "books/form.html", gin.H{
			"IsNew": false,
			"ID":    id,
			"Error": errMessage(err),
		})
		return
	}
	h.renderer.HTML(c, http.StatusOK, "books/form.html", gin.H{
		"IsNew":  false,
		"ID":     id,
		"Values": book,
	})
}

func (h *BookHandler) Update(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.Redirect(http.StatusFound, "/")
		return
	}
	input := bindBookForm(c)
	book, err := h.service.Update(c.Request.Context(), id, input)
	if err != nil {
		h.renderer.HTML(c, errStatus(err), "books/form.html", gin.H{
			"IsNew":  false,
			"ID":     id,
			"Error":  errMessage(err),
			"Values": input,
		})
		return
	}
	c.Redirect(http.StatusFound, "/books/"+strconv.FormatInt(book.ID, 10)+"/edit")
}

func (h *BookHandler) Delete(c *gin.Context) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		c.Redirect(http.StatusFound, "/")
		return
	}
	_ = h.service.Delete(c.Request.Context(), id)
	c.Redirect(http.StatusFound, "/")
}

func bindBookForm(c *gin.Context) service.BookInput {
	input := service.BookInput{
		Title:         c.PostForm("title"),
		Author:        c.PostForm("author"),
		Memo:          formStringPtr(c, "memo"),
		ISBN:          formStringPtr(c, "isbn"),
		Publisher:     formStringPtr(c, "publisher"),
		PublishedDate: formStringPtr(c, "published_date"),
	}
	if v := c.PostForm("rating"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			input.Rating = &n
		}
	}
	return input
}

func formStringPtr(c *gin.Context, key string) *string {
	v := c.PostForm(key)
	return &v
}

func errStatus(err error) int {
	switch {
	case errors.Is(err, apperr.ErrValidation):
		return http.StatusBadRequest
	case errors.Is(err, apperr.ErrConflict):
		return http.StatusConflict
	case errors.Is(err, apperr.ErrNotFound):
		return http.StatusNotFound
	default:
		return http.StatusInternalServerError
	}
}

func errMessage(err error) string {
	return err.Error()
}
