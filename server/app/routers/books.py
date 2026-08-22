from fastapi import APIRouter, Depends, Request, Response

from ..auth import require_api_key
from ..errors import ValidationError
from ..schemas import Book, BookInput
from ..services.book_service import BookService

router = APIRouter(dependencies=[Depends(require_api_key)])


def get_service(request: Request) -> BookService:
    return request.app.state.book_service


def _parse_id(id: str) -> int:
    try:
        return int(id)
    except ValueError as exc:
        raise ValidationError("id must be a number") from exc


def _parse_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except ValueError:
        return default


@router.get("/books")
def list_books(
    q: str = "",
    page: str = "0",
    page_size: str = "0",
    service: BookService = Depends(get_service),
):
    books, pagination = service.list(q, _parse_int(page), _parse_int(page_size))
    return {
        "data": [b.model_dump() for b in books],
        "pagination": {
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total": pagination.total,
        },
    }


@router.get("/books/by-isbn/{isbn}")
def get_book_by_isbn(isbn: str, service: BookService = Depends(get_service)):
    book = service.get_by_isbn(isbn)
    return {"data": book.model_dump()}


@router.get("/books/{id}")
def get_book(id: str, service: BookService = Depends(get_service)):
    book = service.get(_parse_id(id))
    return {"data": book.model_dump()}


@router.post("/books", status_code=201)
def create_book(body: BookInput, service: BookService = Depends(get_service)):
    book = service.create(body)
    return {"data": book.model_dump()}


@router.put("/books/{id}")
def update_book(id: str, body: BookInput, service: BookService = Depends(get_service)):
    book = service.update(_parse_id(id), body)
    return {"data": book.model_dump()}


@router.delete("/books/{id}", status_code=204)
def delete_book(id: str, service: BookService = Depends(get_service)):
    service.delete(_parse_id(id))
    return Response(status_code=204)
