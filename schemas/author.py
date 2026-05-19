from pydantic import BaseModel, Field, conint


class AuthorInput(BaseModel):
    full_name: str = Field(..., max_length=30, examples=["Viktor Sila"])
    book_id: int = Field(..., ge=0, examples=[1])


class AuthorResponse(BaseModel):
    id: int
    full_name: str
    #book:

    class Config:
        from_attributes = True


class AuthorUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=30, examples=["Viktor Sila"])
    book_id: int | None = Field(default=None,ge=0, examples=[1])