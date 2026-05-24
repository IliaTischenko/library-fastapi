import os

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import Admin


def get_password_hash(password: str) -> str:
    """
    Генерирует хэш для пароля
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password_bytes = bcrypt.hashpw(password_bytes, salt)
    return hashed_password_bytes.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Сравнивает введенный пользователем пароль с хэшем из бд
    возвращает True/False
    """
    password_bytes = plain_password.encode('utf-8')
    hashed_password = hashed_password.encode('utf-8')

    return bcrypt.checkpw(password_bytes, hashed_password)


async def create_first_admin_if_not_exists(db_session: AsyncSession):
    query = select(Admin)
    result = await db_session.execute(query)
    existing_admin = result.scalars().first()

    if existing_admin is None:
        default_username = os.getenv("FIRST_ADMIN")
        default_password = os.getenv("FIRST_ADMIN_PASSWORD")
        hashed_password = get_password_hash(default_password)
        first_admin = Admin(username=default_username, hashed_pass=hashed_password)
        db_session.add(first_admin)
        await db_session.commit()

