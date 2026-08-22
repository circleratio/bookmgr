from pydantic import BaseModel


class BookInput(BaseModel):
    """Request body for creating/updating a book.

    Fields default to empty/None rather than being required, matching the
    Go handler's gin.ShouldBindJSON which does not enforce "required" tags;
    presence/format validation happens in the service layer instead.
    """

    title: str = ""
    author: str = ""
    rating: int | None = None
    memo: str | None = None
    isbn: str | None = None
    publisher: str | None = None
    published_date: str | None = None


class Book(BaseModel):
    id: int
    title: str
    author: str
    rating: int | None
    memo: str | None
    isbn: str | None
    publisher: str | None
    published_date: str | None
    created_at: str
    updated_at: str


class BookInfo(BaseModel):
    title: str
    author: str
    publisher: str
    published_date: str
    isbn: str
