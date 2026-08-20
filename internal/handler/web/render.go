package web

import (
	"html/template"
	"net/http"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"
)

// pageSpecs maps a page name to the template files that make up that page.
// layout.html is shared; login.html is a standalone page without the nav layout.
var pageSpecs = map[string][]string{
	"login.html":      {"login.html"},
	"books/list.html": {"layout.html", "books/list.html"},
	"books/form.html": {"layout.html", "books/form.html"},
}

type Renderer struct {
	templates map[string]*template.Template
}

func NewRenderer(dir string) (*Renderer, error) {
	funcs := template.FuncMap{
		"stars":   stars,
		"strVal":  strVal,
		"intVal":  intVal,
		"orDash":  orDash,
		"add":     func(a, b int) int { return a + b },
		"sub":     func(a, b int) int { return a - b },
		"ratings": func() []int { return []int{1, 2, 3, 4, 5} },
	}

	r := &Renderer{templates: make(map[string]*template.Template)}
	for name, files := range pageSpecs {
		paths := make([]string, len(files))
		for i, f := range files {
			paths[i] = filepath.Join(dir, f)
		}
		tmpl, err := template.New(filepath.Base(paths[0])).Funcs(funcs).ParseFiles(paths...)
		if err != nil {
			return nil, err
		}
		r.templates[name] = tmpl
	}
	return r, nil
}

func (r *Renderer) HTML(c *gin.Context, status int, name string, data gin.H) {
	tmpl, ok := r.templates[name]
	if !ok {
		c.String(http.StatusInternalServerError, "template not found: %s", name)
		return
	}
	root := "content"
	if name == "login.html" {
		root = "login"
	} else {
		root = "layout"
	}
	c.Status(status)
	c.Header("Content-Type", "text/html; charset=utf-8")
	if err := tmpl.ExecuteTemplate(c.Writer, root, data); err != nil {
		c.String(http.StatusInternalServerError, "template render error: %v", err)
	}
}

func stars(r *int) string {
	if r == nil {
		return "未評価"
	}
	n := *r
	if n < 0 {
		n = 0
	}
	if n > 5 {
		n = 5
	}
	return strings.Repeat("★", n) + strings.Repeat("☆", 5-n)
}

func strVal(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}

func intVal(i *int) string {
	if i == nil {
		return ""
	}
	return strconv.Itoa(*i)
}

func orDash(s *string) string {
	if s == nil || *s == "" {
		return "-"
	}
	return *s
}
