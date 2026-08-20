// Package apiclient is a Go client for bookmgr's REST API (/api/*),
// authenticating via the X-API-Key header. It has no dependency on the
// server's internal packages — only on the JSON shapes the API exposes.
package apiclient

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"time"
)

// Book mirrors the JSON shape returned by the server's REST API.
type Book struct {
	ID            int64   `json:"id"`
	Title         string  `json:"title"`
	Author        string  `json:"author"`
	Rating        *int    `json:"rating"`
	Memo          *string `json:"memo"`
	ISBN          *string `json:"isbn"`
	Publisher     *string `json:"publisher"`
	PublishedDate *string `json:"published_date"`
	CreatedAt     string  `json:"created_at"`
	UpdatedAt     string  `json:"updated_at"`
}

// BookInput is the request body for creating/updating a book.
type BookInput struct {
	Title         string  `json:"title"`
	Author        string  `json:"author"`
	Rating        *int    `json:"rating,omitempty"`
	Memo          *string `json:"memo,omitempty"`
	ISBN          *string `json:"isbn,omitempty"`
	Publisher     *string `json:"publisher,omitempty"`
	PublishedDate *string `json:"published_date,omitempty"`
}

type Pagination struct {
	Page     int `json:"page"`
	PageSize int `json:"page_size"`
	Total    int `json:"total"`
}

type ListResult struct {
	Books      []Book
	Pagination Pagination
}

// BookInfo mirrors the JSON shape returned by /api/isbn-lookup.
type BookInfo struct {
	Title         string `json:"title"`
	Author        string `json:"author"`
	Publisher     string `json:"publisher"`
	PublishedDate string `json:"published_date"`
	ISBN          string `json:"isbn"`
}

// APIError is returned when the server responds with a non-2xx status and a
// {"error": {"code", "message"}} body.
type APIError struct {
	StatusCode int
	Code       string
	Message    string
}

func (e *APIError) Error() string {
	return fmt.Sprintf("%s: %s (status %d)", e.Code, e.Message, e.StatusCode)
}

type Client struct {
	BaseURL    string
	APIKey     string
	HTTPClient *http.Client
}

func New(baseURL, apiKey string) *Client {
	return &Client{
		BaseURL:    baseURL,
		APIKey:     apiKey,
		HTTPClient: &http.Client{Timeout: 10 * time.Second},
	}
}

func (c *Client) List(ctx context.Context, q string, page, pageSize int) (*ListResult, error) {
	q2 := url.Values{}
	if q != "" {
		q2.Set("q", q)
	}
	if page > 0 {
		q2.Set("page", strconv.Itoa(page))
	}
	if pageSize > 0 {
		q2.Set("page_size", strconv.Itoa(pageSize))
	}

	var body struct {
		Data       []Book     `json:"data"`
		Pagination Pagination `json:"pagination"`
	}
	if err := c.do(ctx, http.MethodGet, "/api/books?"+q2.Encode(), nil, &body); err != nil {
		return nil, err
	}
	return &ListResult{Books: body.Data, Pagination: body.Pagination}, nil
}

func (c *Client) Get(ctx context.Context, id int64) (*Book, error) {
	var body struct {
		Data Book `json:"data"`
	}
	if err := c.do(ctx, http.MethodGet, "/api/books/"+strconv.FormatInt(id, 10), nil, &body); err != nil {
		return nil, err
	}
	return &body.Data, nil
}

func (c *Client) Create(ctx context.Context, input BookInput) (*Book, error) {
	var body struct {
		Data Book `json:"data"`
	}
	if err := c.do(ctx, http.MethodPost, "/api/books", input, &body); err != nil {
		return nil, err
	}
	return &body.Data, nil
}

func (c *Client) Update(ctx context.Context, id int64, input BookInput) (*Book, error) {
	var body struct {
		Data Book `json:"data"`
	}
	if err := c.do(ctx, http.MethodPut, "/api/books/"+strconv.FormatInt(id, 10), input, &body); err != nil {
		return nil, err
	}
	return &body.Data, nil
}

func (c *Client) Delete(ctx context.Context, id int64) error {
	return c.do(ctx, http.MethodDelete, "/api/books/"+strconv.FormatInt(id, 10), nil, nil)
}

func (c *Client) ISBNLookup(ctx context.Context, isbn string) (*BookInfo, error) {
	q := url.Values{}
	q.Set("isbn", isbn)

	var body struct {
		Data BookInfo `json:"data"`
	}
	if err := c.do(ctx, http.MethodGet, "/api/isbn-lookup?"+q.Encode(), nil, &body); err != nil {
		return nil, err
	}
	return &body.Data, nil
}

func (c *Client) do(ctx context.Context, method, path string, reqBody, out any) error {
	var bodyReader *bytes.Reader
	if reqBody != nil {
		b, err := json.Marshal(reqBody)
		if err != nil {
			return fmt.Errorf("encode request body: %w", err)
		}
		bodyReader = bytes.NewReader(b)
	} else {
		bodyReader = bytes.NewReader(nil)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.BaseURL+path, bodyReader)
	if err != nil {
		return fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("X-API-Key", c.APIKey)
	if reqBody != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return fmt.Errorf("call bookmgr api: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		var errBody struct {
			Error struct {
				Code    string `json:"code"`
				Message string `json:"message"`
			} `json:"error"`
		}
		_ = json.NewDecoder(resp.Body).Decode(&errBody)
		return &APIError{StatusCode: resp.StatusCode, Code: errBody.Error.Code, Message: errBody.Error.Message}
	}

	if out == nil || resp.StatusCode == http.StatusNoContent {
		return nil
	}
	if err := json.NewDecoder(resp.Body).Decode(out); err != nil {
		return fmt.Errorf("decode response: %w", err)
	}
	return nil
}
