import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Cookie, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserRole
from app.redis_client import is_token_blacklisted

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
    """
    Создаёт первого админа в бд если его нет, credentials в .env
    """
    query = select(User).where(User.role == UserRole.ADMIN)
    result = await db_session.execute(query)
    existing_admin = result.scalars().first()

    if existing_admin is None:
        default_username = os.getenv("FIRST_ADMIN")
        default_password = os.getenv("FIRST_ADMIN_PASSWORD")
        hashed_password = get_password_hash(default_password)
        first_admin = User(username=default_username, hashed_pass=hashed_password, role=UserRole.ADMIN)
        db_session.add(first_admin)
        await db_session.commit()


def create_access_token(user_id: int, role: str) -> str:
    """
    Генерирует Stateless JWT-токен на 1 день.
    """
    days=int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", "1"))
    expire = datetime.now(timezone.utc) + timedelta(days=days)

    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire
    }

    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt

#OLD
def get_current_user_stateless(access_token: str | None = Cookie(default=None)) -> dict:
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

    current_user = {
        "id":  int(payload["sub"]),
        "role": payload["role"]
    }
    return current_user




class RoleChecker:
    def __init__(self, requre_roles: tuple[str, ...] = ()):
        self.requre_roles = requre_roles

    def __eq__(self, other):
        return isinstance(other, RoleChecker) and self.requre_roles == other.requre_roles

    def __hash__(self):
        return hash(self.requre_roles)

    async def __call__(self, access_token: str | None = Cookie(default=None)):
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated. (Cookie missing)"
            )

        if await is_token_blacklisted(access_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session revoked. Please log in again. (Token is blacklisted)"
            )


        try:
            payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")

        current_user = {
            "id": int(payload["sub"]),
            "role": payload["role"],
            "exp": int(payload["exp"]),
            "token_str": access_token
        }

        if self.requre_roles and current_user["role"] not in self.requre_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient rights"
            )

        return current_user


#OLD
def requre_roles(roles: list[str] = None):
    """
        Проверяет JWT-токен, который пришёл в куках
        извлекает payloads, проверяет роль текущего пользователя с требуемой ролью
        - **access_token**: строка токена
        - **roles**: список ролей для получения доступа к роуту

         Возвращает ID юзера, роль, строку токена и его время жизни
        """
    if roles is None:
        roles = []

    async def dependency(access_token: str | None = Cookie(default=None)):
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated (Cookie missing/Token in blacklist)"
            )

        if await is_token_blacklisted(access_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session revoked. Please log in again."
            )


        try:
            payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")

        current_user = {
            "id": int(payload["sub"]),
            "role": payload["role"],
            "exp": int(payload["exp"]),
            "token_str": access_token
        }

        if roles and current_user["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient rights"
            )

        return current_user

    return dependency