from pydantic import BaseModel, Field, conint

from schemas import AuthorResponse


class BookResponseShort(BaseModel):
    id: int
    title: str
    author: AuthorResponse
    pages: int

    class Config:
        from_attributes=True


class BookInput(BaseModel):
    title: str = Field(..., max_length=30, examples=["Grom"])
    author_id: int = Field(..., ge=0, examples=[1])
    readers_ids: list[conint(ge=0)] = Field(examples=[[0, 1]])
    pages: int = Field(..., ge=1, le=9999, examples=[110])


class BookResponse(BookResponseShort):
    readers: list["ReaderResponseShort"] = []



class BookUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=30, examples=["Grom"])
    author_id: int | None = Field(default=None, ge=0, examples=[1])
    readers_ids: list[conint(ge=0)] | None = Field(default=None, examples=[[0, 1]])
    pages: int | None = Field(default=None, ge=1, le=9999, examples=[110])

