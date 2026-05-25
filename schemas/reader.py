from datetime import date

from pydantic import BaseModel, Field, conint



class ReaderResponseShort(BaseModel):
    id: int
    full_name: str
    issue_date: date

    class Config:
        from_attributes = True


class ReaderInput(BaseModel):
    full_name: str = Field(..., max_length=30, examples=['Kirill Ryabov'], description="Полное имя читателя")
    books_ids: list[conint(ge=0)] = Field(examples=[[0, 1]], description="список ID книг (>0)")
    issue_date: date = Field(default_factory=date.today, description="Дата выдачи книги в формате YYYY-MM-DD")


class ReaderResponse(ReaderResponseShort):
    books: list["BookResponseShort"] = []



class ReaderUpdate(BaseModel):
    full_name: str | None = Field(
        default=None,
        max_length=30,
        examples=['Kirill Ryabov'],
        description="Полное имя читателя"
    )
    books_ids: list[conint(ge=0)] | None = Field(
        default=None,
        min_length=1,
        examples=[[0, 1]],
        description="список ID книг (>0)"
    )
    issue_date: date | None = Field(
        default_factory=date.today,
        examples=["2025-07-10"],
        description="Дата выдачи книги в формате YYYY-MM-DD"
    )

