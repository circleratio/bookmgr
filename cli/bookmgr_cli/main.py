from __future__ import annotations

import argparse
import json
import os
import sys

from .client import APIError, Client


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bookmgr-cli",
        description="Environment: BOOKMGR_API_URL (default http://localhost:8080), "
        "BOOKMGR_API_KEY (required)",
    )
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="list/search books")
    p_list.add_argument("--q", default="", help="free-word search on title/author")
    p_list.add_argument("--page", type=int, default=0, help="page number (1-based)")
    p_list.add_argument("--page-size", type=int, default=0, help="page size")

    p_get = sub.add_parser("get", help="get a book by id")
    p_get.add_argument("id", type=int)

    def add_book_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--title", default="", help="book title (required)")
        p.add_argument("--author", default="", help="author (required)")
        p.add_argument("--rating", type=int, default=0, help="rating 1-5 (0 = unset)")
        p.add_argument("--isbn", default="")
        p.add_argument("--publisher", default="")
        p.add_argument("--published-date", default="", help="YYYY-MM-DD")
        p.add_argument("--memo", default="")

    add_book_flags(sub.add_parser("create", help="create a book"))

    p_update = sub.add_parser("update", help="update a book")
    p_update.add_argument("id", type=int)
    add_book_flags(p_update)

    p_delete = sub.add_parser("delete", help="delete a book")
    p_delete.add_argument("id", type=int)

    p_isbn = sub.add_parser("isbn-lookup", help="look up book info by ISBN")
    p_isbn.add_argument("isbn")

    return parser


def book_input_from_args(args: argparse.Namespace) -> dict:
    input: dict = {"title": args.title, "author": args.author}
    if args.rating:
        input["rating"] = args.rating
    if args.memo:
        input["memo"] = args.memo
    if args.isbn:
        input["isbn"] = args.isbn
    if args.publisher:
        input["publisher"] = args.publisher
    if args.published_date:
        input["published_date"] = args.published_date
    return input


def print_json(value) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def print_table(rows: list[list[str]]) -> None:
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for row in rows:
        print("  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip())


def total_pages(pagination: dict) -> int:
    page_size = pagination.get("page_size") or 0
    if not page_size:
        return 1
    return max(1, -(-pagination["total"] // page_size))


def cmd_list(client: Client, args: argparse.Namespace) -> None:
    books, pagination = client.list(args.q, args.page, args.page_size)
    rows = [["ID", "TITLE", "AUTHOR", "RATING", "ISBN"]]
    for b in books:
        rows.append(
            [
                str(b["id"]),
                b["title"],
                b["author"],
                str(b["rating"]) if b.get("rating") is not None else "-",
                b.get("isbn") or "-",
            ]
        )
    print_table(rows)
    print(f"page {pagination['page']}/{total_pages(pagination)} (total {pagination['total']})")


def cmd_get(client: Client, args: argparse.Namespace) -> None:
    print_json(client.get(args.id))


def cmd_create(client: Client, args: argparse.Namespace) -> None:
    print_json(client.create(book_input_from_args(args)))


def cmd_update(client: Client, args: argparse.Namespace) -> None:
    print_json(client.update(args.id, book_input_from_args(args)))


def cmd_delete(client: Client, args: argparse.Namespace) -> None:
    client.delete(args.id)
    print(f"deleted book {args.id}")


def cmd_isbn_lookup(client: Client, args: argparse.Namespace) -> None:
    print_json(client.isbn_lookup(args.isbn))


_HANDLERS = {
    "list": cmd_list,
    "get": cmd_get,
    "create": cmd_create,
    "update": cmd_update,
    "delete": cmd_delete,
    "isbn-lookup": cmd_isbn_lookup,
}


def main(argv: list[str] | None = None) -> int:
    # Force UTF-8 on stdout/stderr regardless of the platform's default
    # console encoding (e.g. Windows' legacy codepages mangle Japanese text).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help(sys.stderr)
        print("Error: no command given", file=sys.stderr)
        return 1

    base_url = os.environ.get("BOOKMGR_API_URL", "http://localhost:8080")
    api_key = os.environ.get("BOOKMGR_API_KEY")
    if not api_key:
        print("Error: BOOKMGR_API_KEY environment variable is required", file=sys.stderr)
        return 1

    with Client(base_url, api_key) as client:
        try:
            _HANDLERS[args.command](client, args)
        except APIError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
