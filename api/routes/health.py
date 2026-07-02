from fastapi import APIRouter
import redis.asyncio as aioredis
import os
from sqlalchemy import text

from api.database import AsyncSessionLocal

router = APIRouter()

@router.get("")
async def health():
    # check Redis
    try:
        r = aioredis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        await r.ping()
        close = getattr(r, "aclose", None) or getattr(r, "close", None)
        if close:
            await close()
        redis_status = "ok"
    except Exception as e:
        redis_status = f"error: {str(e)[:50]}"

    # check PostgreSQL
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)[:50]}"

    overall = "ok" if redis_status == "ok" and db_status == "ok" else "degraded"

    return {
        "status": overall,
        "redis": redis_status,
        "database": db_status,
    }