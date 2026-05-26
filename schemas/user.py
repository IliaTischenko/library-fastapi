from pydantic import BaseModel, Field
from schemas import ReaderInput

class UserAuthSchema(BaseModel):
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


class UserChangePassword(BaseModel):
    old_password: str = Field(...,
                          min_length=8,
                          max_length=64,
                          description="Старый пароль",
                          examples=['old_secret_password_12345678']
                          )
    new_password: str = Field(...,
                          min_length=8,
                          max_length=64,
                          description="Новый пароль",
                          examples=['new_secret_password_12345678']
                          )



class UserResponse(BaseModel):
    id: int
    username: str

class UserReaderInput(UserAuthSchema, ReaderInput):
    pass