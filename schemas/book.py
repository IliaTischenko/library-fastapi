from pydantic import BaseModel, Field, conint
from datetime import date


class BookInput(BaseModel):
    title: str = Field(..., max_length=30)
    authors_ids: list[conint(ge=0)] = Field(..., min_length=1)
    pages: int = Field(..., ge=1)


class BookResponse(BaseModel):
    id: int
    title: str
    #authors:
    pages: int

    class Config:
        from_attributes = True


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=30)
    authors_ids: list[conint(ge=0)] | None = Field(default=None, min_length=1)
    pages: int | None = Field(default=None, ge=1)

