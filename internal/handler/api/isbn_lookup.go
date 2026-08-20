package api

import (
	"errors"
	"net/http"

	"github.com/gin-gonic/gin"

	"bookmgr/internal/apperr"
	"bookmgr/internal/service"
)

type ISBNLookupHandler struct {
	lookup *service.ISBNLookupService
}

func NewISBNLookupHandler(lookup *service.ISBNLookupService) *ISBNLookupHandler {
	return &ISBNLookupHandler{lookup: lookup}
}

func (h *ISBNLookupHandler) Register(rg *gin.RouterGroup) {
	rg.GET("/isbn-lookup", h.Lookup)
}

func (h *ISBNLookupHandler) Lookup(c *gin.Context) {
	info, err := h.lookup.Lookup(c.Request.Context(), c.Query("isbn"))
	if err != nil {
		switch {
		case errors.Is(err, apperr.ErrValidation):
			c.JSON(http.StatusBadRequest, gin.H{"error": gin.H{"code": "VALIDATION_ERROR", "message": err.Error()}})
		case errors.Is(err, apperr.ErrNotFound):
			c.JSON(http.StatusNotFound, gin.H{"error": gin.H{"code": "NOT_FOUND", "message": "no book found for isbn"}})
		default:
			c.JSON(http.StatusBadGateway, gin.H{"error": gin.H{"code": "UPSTREAM_ERROR", "message": "failed to fetch book info"}})
		}
		return
	}
	respondData(c, http.StatusOK, info)
}
