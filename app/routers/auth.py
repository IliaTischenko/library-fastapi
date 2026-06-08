import os
import time
from typing import Any

from fastapi import APIRouter, Response, status, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_utils import verify_password, create_access_token, RoleChecker
from app.database import get_db_session
from app.models import User
from app.schemas import UserAuthSchema
from app.redis_client import add_token_to_blacklist

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    summary="Вход в систему",
    responses={401: {"description": "Неверное имя пользователя или пароль"}},
)
async def login(
    login_data: UserAuthSchema,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    Вход в систему.
    Проверка пароля, создание jwt токена,
    установка куки авторизации для доступа к защищённым роутам.
    - **login_data**: Данные для входа (логин, пароль)
    """
    query = select(User).where(User.username == login_data.username)
    result = await db_session.execute(query)
    db_user = result.scalar_one_or_none()

    if db_user is None or not verify_password(login_data.password, db_user.hashed_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong username or password",
        )

    token = create_access_token(user_id=db_user.id, role=db_user.role)

    # seconds a day
    max_age = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", "1")) * 86400

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=max_age,
        samesite="lax",
        secure=not os.getenv("DEBUG"),
    )

    return {"detail": "Login success"}


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Выход из системы",
    responses={401: {"description": "токен отсутствует или просрочен"}},
)
async def logout(response: Response, payload: dict[str, Any] = Depends(RoleChecker())):
    """
    Выход из системы.
    Заносим токен в блеклист (Redis)
    Удаляет токен из куки.
    """

    current_time = int(time.time())
    remain_seconds = payload["exp"] - current_time

    await add_token_to_blacklist(
        token=payload["token_str"], expire_seconds=remain_seconds
    )
    response.delete_cookie(key="access_token")

    return {"detail": "Logout success"}
