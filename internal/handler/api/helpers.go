package api

import (
	"strconv"

	"github.com/gin-gonic/gin"

	"bookmgr/internal/apperr"
)

func parseID(c *gin.Context) (int64, error) {
	id, err := strconv.ParseInt(c.Param("id"), 10, 64)
	if err != nil {
		return 0, apperr.NewValidationError("id must be a number")
	}
	return id, nil
}

func badRequestErr(err error) error {
	return apperr.NewValidationError("invalid request body: " + err.Error())
}
