from fastapi import APIRouter, Depends, Request

from ..auth import require_api_key
from ..services.isbn_lookup_service import ISBNLookupService

router = APIRouter(dependencies=[Depends(require_api_key)])


def get_lookup_service(request: Request) -> ISBNLookupService:
    return request.app.state.isbn_lookup_service


@router.get("/isbn-lookup")
def lookup_isbn(isbn: str = "", service: ISBNLookupService = Depends(get_lookup_service)):
    info = service.lookup(isbn)
    return {"data": info.model_dump()}
