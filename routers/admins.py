from fastapi import APIRouter, status, HTTPException, Depends

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from auth_utils import get_password_hash
from database import get_db_session
from models import Admin
from schemas import AdminAuthSchema, AdminResponse, AdminChangePassword


router = APIRouter(prefix="/admins", tags=['Администраторы'])

@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=list[AdminResponse],
    summary="Получить список админов"
)
async def get_admins(db_session:AsyncSession = Depends(get_db_session)):
    """
    Возвращает список админов, без пароля.
    """
    query = select(Admin)
    result = await db_session.execute(query)
    admins = result.scalars().all()

    return admins



@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminResponse,
    summary="Создать нового админа",
    responses={
        400: {"description": "Админ с таким именем уже существует"}
    })
async def post_admin(admin_data: AdminAuthSchema, db_session: AsyncSession = Depends(get_db_session)):
    """
    Создание нового админа.
    Принимает JSON-объект с данными админа, валидирует их, проверяет username на уникальность
    хеширует пароль и сохраняет в БД

    - **admin_data**: Данные для создания админа(схема AdminInput)

    Возвращает объект созданного админа с присвоенным ID из БД
    """
    query = select(Admin).where(func.lower(Admin.username) == admin_data.username.lower())
    result = await db_session.execute(query)
    existing_admin = result.scalar_one_or_none()
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin with this username already exists"
        )

    hashed_pass = get_password_hash(admin_data.password)

    db_admin = Admin(username=admin_data.username, hashed_pass=hashed_pass)
    db_session.add(db_admin)
    await db_session.refresh(db_admin)

    return db_admin


@router.patch(
    "/{admin_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminResponse,
    summary="Смена пароля админу по указанному ID",
    responses={
        404: {"description": "Админ с указанным ID не найден"}
    }
)
async def change_pass_admin(
        admin_id: int,
        admin_data: AdminChangePassword,
        db_session: AsyncSession = Depends(get_db_session)
):
    """
    Принимает JSON-объект с новым паролем, хеширует его и заменяет.
    - **admin_data**: Данные для изменения админа(схема AdminChangePassword)
    Возвращает объект админа без пароля.

    """
    db_admin = await db_session.get(Admin, admin_id)
    if db_admin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin with tis ID not found"
        )

    hashed_pass = get_password_hash(admin_data.password)

    db_admin.hashed_pass = hashed_pass
    await db_session.commit()

    return db_admin


@router.delete(
    "/{admin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить объект по указанному ID",
    responses={
        404: {"description": "Админ с указанным ID не найден"}
    })
async def delete_admin(admin_id: int, db_session: AsyncSession = Depends(get_db_session)):
    """
    Удалить админа по указанному id, защищенный(только Администратор)
    - **admin_id**: ID администратора
    """
    db_admin = await db_session.get(Admin, admin_id)
    if db_admin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin with tis ID not found"
        )

    await db_session.delete(db_admin)
    await db_session.commit()
