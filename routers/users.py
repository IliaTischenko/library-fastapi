from fastapi import APIRouter, status, HTTPException, Depends

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from auth_utils import get_password_hash, verify_password, get_current_user_stateless
from database import get_db_session
from models import User, UserRole, Reader, Book
from schemas import UserAuthSchema, UserResponse, UserChangePassword, UserReaderInput, ReaderResponse


router = APIRouter(prefix="/users", tags=['Пользователи'])

@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=list[UserResponse],
    summary="Получить список пользователей"
)
async def get_users(
        db_session:AsyncSession = Depends(get_db_session),
        payloads: dict = Depends(get_current_user_stateless)):
    """
    Возвращает список пользователей
    Защищенный, только администраторы
    """
    if payloads['role'] != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have sufficient rights to perform this action."
        )



    query = select(User)
    result = await db_session.execute(query)
    users = result.scalars().all()

    return users



@router.post(
    "/register-admin",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    summary="Регистрация нового админа",
    responses={
        400: {"description": "Админ с таким именем уже существует"}
    })
async def create_admin(user_data: UserAuthSchema, db_session: AsyncSession = Depends(get_db_session)):
    """
    Создание нового админа.
    Принимает JSON-объект с данными админа, валидирует их, проверяет username на уникальность
    хеширует пароль и сохраняет в БД

    - **admin_data**: Данные для создания админа(схема AdminInput)

    Возвращает объект созданного админа с присвоенным ID из БД
    """
    query = select(User).where(func.lower(User.username) == user_data.username.lower())
    result = await db_session.execute(query)
    existing_admin = result.scalar_one_or_none()
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin with this username already exists"
        )

    hashed_pass = get_password_hash(user_data.password)

    db_admin = User(username=user_data.username, hashed_pass=hashed_pass, role=UserRole.ADMIN)
    db_session.add(db_admin)

    await db_session.commit()
    await db_session.refresh(db_admin)

    return db_admin


@router.post(
    "/register-reader",
    status_code=status.HTTP_201_CREATED,
    response_model=ReaderResponse,
    summary="Регистрация нового читателя",
    responses={
        400: {"description": "Юзер с таким username уже существует"}
    }
)
async def create_reader(
        reader_data: UserReaderInput,
        db_session: AsyncSession = Depends(get_db_session)
):
    """
    Создание нового читателя.

    Принимает JSON-объект с данными читателя и юзера, валидирует их
    проверяет наличие username на уникальность,
    проверяет наличие указанных книг в БД,
    добавляет только существующие книги.

    - **reader_data**: Данные для создания читателя(схема UserReaderInput)

    Возвращает объект созданного читателя с присвоенным ID из БД,
     подтягивает его книги(mtm связь) и их авторов(Book.author 1tm связь)
    """
    query = select(User).where(func.lower(User.username) == reader_data.username.lower())
    result = await db_session.execute(query)
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this username already exists"
        )

    hashed_pass = get_password_hash(reader_data.password)

    db_user = User(username=reader_data.username, hashed_pass=hashed_pass, role=UserRole.READER)
    db_session.add(db_user)

    await db_session.commit()
    await db_session.refresh(db_user)



    data_dict = reader_data.model_dump(exclude={"username", "password"})
    books_ids = data_dict.pop("books_ids", [])
    new_reader = Reader(**data_dict)

    if books_ids:
        query = select(Book).where(Book.id.in_(books_ids))
        result = await db_session.execute(query)
        books = result.scalars().all()
        new_reader.books = books

    new_reader.user = db_user

    db_session.add(new_reader)
    await db_session.commit()

    result = await db_session.execute(
        select(Reader)
        .options(selectinload(Reader.books).joinedload(Book.author))
        .where(Reader.id == new_reader.id)
    )
    reader_with_relations = result.scalar_one()



    return reader_with_relations




@router.patch(
    "/{admin_id}",
    status_code=status.HTTP_200_OK,
    response_model=UserResponse,
    summary="Смена пароля текущему юзеру",
    responses={
        401: {"description": "Неверный старый пароль"}
    }
)
async def change_pass(
        user_id: int,
        user_data: UserChangePassword,
        db_session: AsyncSession = Depends(get_db_session),
        payloads: dict = Depends(get_current_user_stateless)
):
    """
    Принимает JSON-объект с новым паролем, хеширует его и заменяет.
    - **admin_data**: Данные для изменения пароля (схема UserChangePassword)
    Возвращает объект юзера.

    """
    existing_user = await db_session.get(User, payloads["id"])
    if existing_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with tis ID not found"
        )

    current_hash = str(existing_user.hashed_pass)

    if not verify_password(user_data.old_password, current_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong old password"
        )

    hashed_new_pass = get_password_hash(user_data.old_password)

    existing_user.hashed_pass = hashed_new_pass
    await db_session.commit()

    return existing_user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить юзера по указанному ID",
    responses={
        404: {"description": "Юзер с указанным ID не найден"}
    })
async def delete_admin(user_id: int, db_session: AsyncSession = Depends(get_db_session)):
    """
    Удалить юзера по указанному id, защищенный (только Администратор)
    - **user_id**: ID пользователя
    """
    db_user = await db_session.get(User, user_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with tis ID not found"
        )

    await db_session.delete(db_user)
    await db_session.commit()
