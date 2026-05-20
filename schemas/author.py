from pydantic import BaseModel, Field, conint


class AuthorInput(BaseModel):
    full_name: str = Field(..., max_length=30, examples=["Viktor Sila"])


class AuthorResponse(BaseModel):
    id: int
    full_name: str
    #books:

    class Config:
        from_attributes = True


class AuthorUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=30, examples=["Viktor Sila"])