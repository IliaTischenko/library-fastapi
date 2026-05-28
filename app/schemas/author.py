from datetime import date

from pydantic import BaseModel, Field


class AuthorInput(BaseModel):
    full_name: str = Field(
        ...,
        max_length=30,
        description="Полное имя автора. Должно быть уникальным.",
        examples=["Viktor Sila"]
    )
    country: str = Field(
        ...,
        max_length=30,
        description="Страна",
        examples=['China']
    )
    birth_date: date = Field(
        ...,
        description="Дата рождения автора в формате YYYY-MM-DD",
        examples=["1980-09-12"]
    )


class AuthorResponse(BaseModel):
    id: int
    full_name: str
    country: str
    birth_date: date

    class Config:
        from_attributes = True


class AuthorUpdate(BaseModel):
    full_name: str | None = Field(
        default=None,
        max_length=30,
        description="Полное имя автора. Должно быть уникальным.",
        examples=["Viktor Sila"]
    )
    country: str | None = Field(
        default=None,
        max_length=30,
        description="Страна",
        examples=['China']
    )
    birth_date: date | None = Field(
        default=None,
        examples=["1980-09-12"],
        description="Дата рождения автора в формате YYYY-MM-DD"
    )