package web

import (
	"net/http"

	"github.com/gin-gonic/gin"

	"bookmgr/internal/middleware"
)

type AuthHandler struct {
	apiKey   string
	renderer *Renderer
}

func NewAuthHandler(apiKey string, renderer *Renderer) *AuthHandler {
	return &AuthHandler{apiKey: apiKey, renderer: renderer}
}

func (h *AuthHandler) Register(r gin.IRouter) {
	r.GET("/login", h.LoginForm)
	r.POST("/login", h.Login)
	r.POST("/logout", h.Logout)
}

func (h *AuthHandler) LoginForm(c *gin.Context) {
	h.renderer.HTML(c, http.StatusOK, "login.html", gin.H{})
}

func (h *AuthHandler) Login(c *gin.Context) {
	apiKey := c.PostForm("api_key")
	if apiKey != h.apiKey {
		h.renderer.HTML(c, http.StatusUnauthorized, "login.html", gin.H{
			"Error": "APIキーが正しくありません",
		})
		return
	}
	c.SetSameSite(http.SameSiteLaxMode)
	c.SetCookie(middleware.SessionCookieName, apiKey, 0, "/", "", false, true)
	c.Redirect(http.StatusFound, "/")
}

func (h *AuthHandler) Logout(c *gin.Context) {
	c.SetSameSite(http.SameSiteLaxMode)
	c.SetCookie(middleware.SessionCookieName, "", -1, "/", "", false, true)
	c.Redirect(http.StatusFound, "/login")
}
