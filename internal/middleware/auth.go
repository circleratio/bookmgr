package middleware

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

const SessionCookieName = "session"

// APIKeyAuth authenticates REST API requests via the X-API-Key header.
func APIKeyAuth(apiKey string) gin.HandlerFunc {
	return func(c *gin.Context) {
		if c.GetHeader("X-API-Key") != apiKey {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{
				"error": gin.H{"code": "UNAUTHORIZED", "message": "invalid or missing API key"},
			})
			return
		}
		c.Next()
	}
}

// WebAuth authenticates SSR screen requests via the session cookie,
// redirecting to /login when absent or invalid.
func WebAuth(apiKey string) gin.HandlerFunc {
	return func(c *gin.Context) {
		cookie, err := c.Cookie(SessionCookieName)
		if err != nil || cookie != apiKey {
			c.Redirect(http.StatusFound, "/login")
			c.Abort()
			return
		}
		c.Next()
	}
}
