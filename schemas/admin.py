from pydantic import BaseModel, Field


class AdminAuthSchema(BaseModel):
    username: str = Field(...,
                          min_length=5,
                          max_length=24,
                          description="username для администратора",
                          examples=["Admin"])

    password: str = Field(...,
                          min_length=8,
                          max_length=64,
                          description="Пароль",
                          examples=['12345678']
                          )


class AdminChangePassword(BaseModel):
    password: str = Field(...,
                          min_length=8,
                          max_length=64,
                          description="Новый пароль",
                          examples=['new_secret_password_12345678']
                          )


class AdminResponse(BaseModel):
    id: int
    username: str