package model

import "time"

type Book struct {
	ID            int64     `json:"id"`
	Title         string    `json:"title"`
	Author        string    `json:"author"`
	Rating        *int      `json:"rating"`
	Memo          *string   `json:"memo"`
	ISBN          *string   `json:"isbn"`
	Publisher     *string   `json:"publisher"`
	PublishedDate *string   `json:"published_date"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}
