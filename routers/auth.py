from fastapi import APIRouter, Response, status

from schemas import AdminAuthSchema


router = APIRouter(prefix="/auth", tags=['Authentication'])


@router.post(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Вход в систему для администрирования"
)
async def login(login_data: AdminAuthSchema):
    """
    Вход в систему.
    Установка куки авторизации для доступа к защищённым роутам.
    - **login_data**: Данные для входа (логин, пароль)
    """
    token = "make jwt"
    return {"detail": "Login success"}


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Выход из системы"
)
async def logout(response: Response):
    """
    Разлогинивает администратора.
    Удаляет токен из куки.
        """
    #response.delete_cookie(key="access_token")
    return {"detail": "logout success"}