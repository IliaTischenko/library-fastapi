from pydantic import BaseModel, Field, ConfigDict

from app.schemas import AuthorResponse


class BookResponse(BaseModel):
    id: int
    title: str
    author: AuthorResponse
    pages: int
    model_config = ConfigDict(from_attributes=True)


class BookInput(BaseModel):
    title: str = Field(..., max_length=30, examples=["Grom"], description="Название книги")
    author_id: int = Field(..., ge=0, examples=[1], description="ID автора (>0)")
    pages: int = Field(..., ge=1, le=9999, examples=[110], description="Число страниц")



class BookUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=30, examples=["Grom"], description="Название книги")
    author_id: int | None = Field(default=None, ge=0, examples=[1], description="ID автора (>0)")
    pages: int | None = Field(default=None, ge=1, le=9999, examples=[110], description="Число страниц")

