from pydantic import BaseModel, Field, conint
from datetime import date


class ReaderInput(BaseModel):
    full_name: str = Field(..., max_length=30, examples=['Kirill Ryabov'])
    #books_ids: list[conint(ge=0)] = Field(examples=[[0, 1]])
    issue_date: date = Field(default_factory=date.today)


class ReaderResponse(BaseModel):
    id: int
    full_name: str
    #books: bookschema
    issue_date: date

    class Config:
        from_attributes = True


class ReaderUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=30, examples=['Kirill Ryabov'])
    books_ids: list[conint(ge=0)] | None = Field(default=None, min_length=1, examples=[[0, 1]])
    issue_date: date | None = Field(default_factory=date.today, examples=["2025-07-10"])