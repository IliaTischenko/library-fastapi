import redis.asyncio as aioredis

REDIS_URL = "redis://redis:6379/0"

redis_client: aioredis.Redis | None = None

def get_redis_client() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    return redis_client


async def add_token_to_blacklist(token: str, expire_seconds: int):
    """
    Добавляет токен в черный список с ограничением по времени
    """
    client = get_redis_client()
    await client.set(name=f"blacklist:{token}", value="1", ex=expire_seconds)

async def is_token_blacklisted(token: str) -> bool:
    """
    Проверяет, находится ли токен в черном списке
    """
    client = get_redis_client()
    exists = await client.get(f"blacklist:{token}")

    if exists:
        return True

    return False

