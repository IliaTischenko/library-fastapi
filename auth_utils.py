import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Cookie, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Admin

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "12345678")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

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


async def create_first_admin_if_not_exists(db_session: AsyncSession) -> None:
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


def create_access_token(user_id: int) -> str:
    """
    Генерирует Stateless JWT-токен на 1 день.
    """
    days=int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", "1"))
    expire = datetime.now(timezone.utc) + timedelta(days=days)

    payload = {
        "sub": str(user_id),
        "exp": expire
    }

    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def get_current_id_admin_stateless(access_token: str | None = Cookie(default=None)) -> int:
    """
    Проверяет JWT-токен, который пришёл в куках
    - **access_token** - строка токена
    """
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (Cookie missing)"
        )

    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    return int(payload["sub"])