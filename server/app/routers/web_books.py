from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import require_web_session
from ..errors import AppError, NotFoundError, ValidationError
from ..schemas import BookInput
from ..services.book_service import BookService
from ..services.isbn_lookup_service import ISBNLookupService

router = APIRouter(dependencies=[Depends(require_web_session)])


def get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


def get_service(request: Request) -> BookService:
    return request.app.state.book_service


def get_lookup_service(request: Request) -> ISBNLookupService:
    return request.app.state.isbn_lookup_service


def _parse_id_or_none(id: str) -> int | None:
    try:
        return int(id)
    except ValueError:
        return None


def _parse_rating(rating: str) -> int | None:
    if not rating:
        return None
    try:
        return int(rating)
    except ValueError:
        return None


def _empty_values() -> dict:
    return {
        "title": "",
        "author": "",
        "rating": None,
        "memo": "",
        "isbn": "",
        "publisher": "",
        "published_date": "",
    }


def _values_from_form(
    title: str, author: str, rating: int | None, memo: str, isbn: str,
    publisher: str, published_date: str,
) -> dict:
    return {
        "title": title,
        "author": author,
        "rating": rating,
        "memo": memo,
        "isbn": isbn,
        "publisher": publisher,
        "published_date": published_date,
    }


@router.get("/books/isbn-lookup")
def isbn_lookup_web(isbn: str = "", service: ISBNLookupService = Depends(get_lookup_service)):
    try:
        info = service.lookup(isbn)
    except ValidationError as e:
        return JSONResponse(status_code=400, content={"error": e.message})
    except NotFoundError:
        return JSONResponse(status_code=404, content={"error": "該当する書籍が見つかりませんでした"})
    except AppError:
        return JSONResponse(status_code=502, content={"error": "書誌情報の取得に失敗しました"})
    return {"data": info.model_dump()}


@router.get("/")
def list_books(request: Request, q: str = "", page: int = 0, service: BookService = Depends(get_service)):
    templates = get_templates(request)
    books, pagination = service.list(q, page, 0)

    total_pages = max(1, -(-pagination.total // pagination.page_size))
    return templates.TemplateResponse(
        request,
        "books/list.html",
        {
            "books": books,
            "query": q,
            "page": pagination.page,
            "total_pages": total_pages,
            "total": pagination.total,
            "error": None,
        },
    )


@router.get("/books/new")
def new_form(request: Request):
    return get_templates(request).TemplateResponse(
        request,
        "books/form.html",
        {"is_new": True, "id": 0, "values": _empty_values(), "error": None},
    )


@router.post("/books")
def create_book(
    request: Request,
    title: str = Form(""),
    author: str = Form(""),
    rating: str = Form(""),
    memo: str = Form(""),
    isbn: str = Form(""),
    publisher: str = Form(""),
    published_date: str = Form(""),
    service: BookService = Depends(get_service),
):
    rating_val = _parse_rating(rating)
    input = BookInput(
        title=title, author=author, rating=rating_val, memo=memo,
        isbn=isbn, publisher=publisher, published_date=published_date,
    )
    try:
        book = service.create(input)
    except AppError as e:
        return get_templates(request).TemplateResponse(
            request,
            "books/form.html",
            {
                "is_new": True,
                "id": 0,
                "error": e.message,
                "values": _values_from_form(title, author, rating_val, memo, isbn, publisher, published_date),
            },
            status_code=e.status_code,
        )
    return RedirectResponse(f"/books/{book.id}/edit", status_code=302)


@router.get("/books/{id}/edit")
def edit_form(id: str, request: Request, service: BookService = Depends(get_service)):
    book_id = _parse_id_or_none(id)
    if book_id is None:
        return RedirectResponse("/", status_code=302)

    templates = get_templates(request)
    try:
        book = service.get(book_id)
    except AppError as e:
        return templates.TemplateResponse(
            request,
            "books/form.html",
            {"is_new": False, "id": book_id, "error": e.message, "values": _empty_values()},
            status_code=e.status_code,
        )
    return templates.TemplateResponse(
        request,
        "books/form.html",
        {"is_new": False, "id": book_id, "values": book.model_dump(), "error": None},
    )


@router.post("/books/{id}")
def update_book(
    id: str,
    request: Request,
    title: str = Form(""),
    author: str = Form(""),
    rating: str = Form(""),
    memo: str = Form(""),
    isbn: str = Form(""),
    publisher: str = Form(""),
    published_date: str = Form(""),
    service: BookService = Depends(get_service),
):
    book_id = _parse_id_or_none(id)
    if book_id is None:
        return RedirectResponse("/", status_code=302)

    rating_val = _parse_rating(rating)
    input = BookInput(
        title=title, author=author, rating=rating_val, memo=memo,
        isbn=isbn, publisher=publisher, published_date=published_date,
    )
    try:
        book = service.update(book_id, input)
    except AppError as e:
        return get_templates(request).TemplateResponse(
            request,
            "books/form.html",
            {
                "is_new": False,
                "id": book_id,
                "error": e.message,
                "values": _values_from_form(title, author, rating_val, memo, isbn, publisher, published_date),
            },
            status_code=e.status_code,
        )
    return RedirectResponse(f"/books/{book.id}/edit", status_code=302)


@router.post("/books/{id}/delete")
def delete_book(id: str, service: BookService = Depends(get_service)):
    book_id = _parse_id_or_none(id)
    if book_id is not None:
        try:
            service.delete(book_id)
        except AppError:
            pass
    return RedirectResponse("/", status_code=302)
