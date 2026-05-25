from fastapi import APIRouter, Response, status, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth_utils import verify_password, create_access_token, get_current_id_admin_stateless
from database import get_db_session
from models import Admin
from schemas import AdminAuthSchema



router = APIRouter(prefix="/auth", tags=['Authentication'])


@router.post(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Вход в систему для администрирования",
    responses={
        401: {"description": "Неверное имя пользователя или пароль"}
    }
)
async def login(
        login_data: AdminAuthSchema,
        response: Response,
        db_session: AsyncSession = Depends(get_db_session)
):
    """
    Вход в систему.
    Проверка пароля, создание jwt токена,
    установка куки авторизации для доступа к защищённым роутам.
    - **login_data**: Данные для входа (логин, пароль)
    """
    query = select(Admin).where(Admin.username == login_data.username)
    result = await db_session.execute(query)
    db_admin = result.scalar_one_or_none()

    if db_admin is None or not verify_password(login_data.password, db_admin.hashed_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong username or password"
        )

    token = create_access_token(db_admin.id)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=86400,
        samesite="lax",
        secure=False
    )

    return {"detail": "Login success"}


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Выход из системы",
    responses={
        401: {"description": "токен отсутствует или просрочен"}
    }
)
async def logout(response: Response, current_admin_id = Depends(get_current_id_admin_stateless)):
    """
    Разлогинивает администратора.
    Удаляет токен из куки.
        """
    response.delete_cookie(key="access_token")
    return {"detail": "logout success"}