from email.policy import default

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config.db_config import get_db
from crud import users


def parse_token(authorization: str) -> str:
    """取出口令部分，兼容 'Bearer xxx' 和直接传 token 两种写法。"""
    scheme, _, credential = authorization.partition(" ")
    return (credential if scheme.lower() == "bearer" else authorization).strip()


async def get_current_user(
        authorization: str = Header(None,alias="Authorization"),
        db: AsyncSession = Depends(get_db)
):
    # 没带令牌时返回 401（而不是参数校验的 422），前端才能据此判断登录失效
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="未登录")
    user = await users.get_user_token(db, parse_token(authorization))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="无效令牌")

    return user