package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"strconv"
	"text/tabwriter"

	"bookmgr/internal/apiclient"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "Error:", err)
		os.Exit(1)
	}
}

func run(args []string) error {
	if len(args) == 0 {
		printUsage()
		return errors.New("no command given")
	}

	baseURL := os.Getenv("BOOKMGR_API_URL")
	if baseURL == "" {
		baseURL = "http://localhost:8080"
	}
	apiKey := os.Getenv("BOOKMGR_API_KEY")
	if apiKey == "" {
		return errors.New("BOOKMGR_API_KEY environment variable is required")
	}
	client := apiclient.New(baseURL, apiKey)
	ctx := context.Background()

	switch args[0] {
	case "list":
		return cmdList(ctx, client, args[1:])
	case "get":
		return cmdGet(ctx, client, args[1:])
	case "create":
		return cmdCreate(ctx, client, args[1:])
	case "update":
		return cmdUpdate(ctx, client, args[1:])
	case "delete":
		return cmdDelete(ctx, client, args[1:])
	case "isbn-lookup":
		return cmdISBNLookup(ctx, client, args[1:])
	case "-h", "--help", "help":
		printUsage()
		return nil
	default:
		printUsage()
		return fmt.Errorf("unknown command: %s", args[0])
	}
}

func printUsage() {
	fmt.Fprintln(os.Stderr, `Usage: bookmgr-cli <command> [flags]

Environment:
  BOOKMGR_API_URL   Server base URL (default http://localhost:8080)
  BOOKMGR_API_KEY   API key (required)

Commands:
  list [--q QUERY] [--page N] [--page-size N]
  get <id>
  create --title T --author A [--rating 1-5] [--isbn ISBN] [--publisher P] [--published-date YYYY-MM-DD] [--memo M]
  update <id> --title T --author A [--rating 1-5] [--isbn ISBN] [--publisher P] [--published-date YYYY-MM-DD] [--memo M]
  delete <id>
  isbn-lookup <isbn>`)
}

func cmdList(ctx context.Context, client *apiclient.Client, args []string) error {
	fs := flag.NewFlagSet("list", flag.ContinueOnError)
	q := fs.String("q", "", "free-word search on title/author")
	page := fs.Int("page", 0, "page number (1-based)")
	pageSize := fs.Int("page-size", 0, "page size")
	if err := fs.Parse(args); err != nil {
		return err
	}

	result, err := client.List(ctx, *q, *page, *pageSize)
	if err != nil {
		return err
	}

	tw := tabwriter.NewWriter(os.Stdout, 0, 2, 2, ' ', 0)
	fmt.Fprintln(tw, "ID\tTITLE\tAUTHOR\tRATING\tISBN")
	for _, b := range result.Books {
		fmt.Fprintf(tw, "%d\t%s\t%s\t%s\t%s\n", b.ID, b.Title, b.Author, ratingString(b.Rating), stringOr(b.ISBN, "-"))
	}
	tw.Flush()
	fmt.Printf("page %d/%d (total %d)\n", result.Pagination.Page, totalPages(result.Pagination), result.Pagination.Total)
	return nil
}

func cmdGet(ctx context.Context, client *apiclient.Client, args []string) error {
	if len(args) != 1 {
		return errors.New("usage: bookmgr-cli get <id>")
	}
	id, err := strconv.ParseInt(args[0], 10, 64)
	if err != nil {
		return fmt.Errorf("invalid id: %s", args[0])
	}
	book, err := client.Get(ctx, id)
	if err != nil {
		return err
	}
	return printJSON(book)
}

func cmdCreate(ctx context.Context, client *apiclient.Client, args []string) error {
	fs := flag.NewFlagSet("create", flag.ContinueOnError)
	input := bindBookFlags(fs)
	if err := fs.Parse(args); err != nil {
		return err
	}
	book, err := client.Create(ctx, input.build())
	if err != nil {
		return err
	}
	return printJSON(book)
}

func cmdUpdate(ctx context.Context, client *apiclient.Client, args []string) error {
	if len(args) < 1 {
		return errors.New("usage: bookmgr-cli update <id> [flags]")
	}
	id, err := strconv.ParseInt(args[0], 10, 64)
	if err != nil {
		return fmt.Errorf("invalid id: %s", args[0])
	}
	fs := flag.NewFlagSet("update", flag.ContinueOnError)
	input := bindBookFlags(fs)
	if err := fs.Parse(args[1:]); err != nil {
		return err
	}
	book, err := client.Update(ctx, id, input.build())
	if err != nil {
		return err
	}
	return printJSON(book)
}

func cmdDelete(ctx context.Context, client *apiclient.Client, args []string) error {
	if len(args) != 1 {
		return errors.New("usage: bookmgr-cli delete <id>")
	}
	id, err := strconv.ParseInt(args[0], 10, 64)
	if err != nil {
		return fmt.Errorf("invalid id: %s", args[0])
	}
	if err := client.Delete(ctx, id); err != nil {
		return err
	}
	fmt.Printf("deleted book %d\n", id)
	return nil
}

func cmdISBNLookup(ctx context.Context, client *apiclient.Client, args []string) error {
	if len(args) != 1 {
		return errors.New("usage: bookmgr-cli isbn-lookup <isbn>")
	}
	info, err := client.ISBNLookup(ctx, args[0])
	if err != nil {
		return err
	}
	return printJSON(info)
}

// bookFlags holds the raw flag values for create/update, since flag.String
// et al. need addressable destinations before parsing.
type bookFlags struct {
	title         *string
	author        *string
	rating        *int
	memo          *string
	isbn          *string
	publisher     *string
	publishedDate *string
}

func bindBookFlags(fs *flag.FlagSet) *bookFlags {
	return &bookFlags{
		title:         fs.String("title", "", "book title (required)"),
		author:        fs.String("author", "", "author (required)"),
		rating:        fs.Int("rating", 0, "rating 1-5 (0 = unset)"),
		memo:          fs.String("memo", "", "memo"),
		isbn:          fs.String("isbn", "", "ISBN"),
		publisher:     fs.String("publisher", "", "publisher"),
		publishedDate: fs.String("published-date", "", "published date (YYYY-MM-DD)"),
	}
}

func (f *bookFlags) build() apiclient.BookInput {
	input := apiclient.BookInput{Title: *f.title, Author: *f.author}
	if *f.rating != 0 {
		input.Rating = f.rating
	}
	if *f.memo != "" {
		input.Memo = f.memo
	}
	if *f.isbn != "" {
		input.ISBN = f.isbn
	}
	if *f.publisher != "" {
		input.Publisher = f.publisher
	}
	if *f.publishedDate != "" {
		input.PublishedDate = f.publishedDate
	}
	return input
}

func printJSON(v any) error {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	enc.SetEscapeHTML(false)
	return enc.Encode(v)
}

func ratingString(r *int) string {
	if r == nil {
		return "-"
	}
	return strconv.Itoa(*r)
}

func stringOr(s *string, fallback string) string {
	if s == nil || *s == "" {
		return fallback
	}
	return *s
}

func totalPages(p apiclient.Pagination) int {
	if p.PageSize == 0 {
		return 1
	}
	pages := (p.Total + p.PageSize - 1) / p.PageSize
	if pages < 1 {
		pages = 1
	}
	return pages
}
