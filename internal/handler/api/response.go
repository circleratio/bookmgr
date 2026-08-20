package api

import (
	"errors"
	"net/http"

	"github.com/gin-gonic/gin"

	"bookmgr/internal/apperr"
)

func respondData(c *gin.Context, status int, data any) {
	c.JSON(status, gin.H{"data": data})
}

func respondList(c *gin.Context, data any, page, pageSize, total int) {
	c.JSON(http.StatusOK, gin.H{
		"data": data,
		"pagination": gin.H{
			"page":      page,
			"page_size": pageSize,
			"total":     total,
		},
	})
}

func respondError(c *gin.Context, err error) {
	switch {
	case errors.Is(err, apperr.ErrValidation):
		c.JSON(http.StatusBadRequest, gin.H{"error": gin.H{"code": "VALIDATION_ERROR", "message": err.Error()}})
	case errors.Is(err, apperr.ErrNotFound):
		c.JSON(http.StatusNotFound, gin.H{"error": gin.H{"code": "NOT_FOUND", "message": "book not found"}})
	case errors.Is(err, apperr.ErrConflict):
		c.JSON(http.StatusConflict, gin.H{"error": gin.H{"code": "CONFLICT", "message": err.Error()}})
	default:
		c.JSON(http.StatusInternalServerError, gin.H{"error": gin.H{"code": "INTERNAL_ERROR", "message": "internal server error"}})
	}
}
