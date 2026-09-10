
import uuid

from datetime import datetime
from datetime import timedelta
from unittest import result

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import delete, update

from models.users import User, UserToken
from schemas.users import RegisterRequest, UserUpdateRequest
from utils import security

# 登录令牌有效期，剩余不足一半时会自动续期
TOKEN_TTL = timedelta(days=7)


#根据用户名查询数据库
async def get_user_by_username(db: AsyncSession, username: str):
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

#创建用户
async def create_user(db: AsyncSession, user_data: RegisterRequest):
    hash_password = security.get_password_hash(user_data.password)
    user = User(username=user_data.username, password=hash_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

#生成token
async def create_token(db: AsyncSession, user_id: int):
    token = str(uuid.uuid4())
    # 单设备登录：先清掉该用户的旧令牌，新登录即顶掉旧会话
    await db.execute(delete(UserToken).where(UserToken.user_id == user_id))
    db.add(UserToken(user_id=user_id, token=token, expires_at=datetime.now() + TOKEN_TTL))
    await db.commit()
    return token

#验证登录名和密码
async def get_user(db: AsyncSession, username: str,password: str):
    user = await get_user_by_username(db, username)
    if not user:
        return None
    if not security.verify_password(password,user.password):
        return None
    return user

#根据token查询用户
async def get_user_token(db: AsyncSession, token: str):
    query = select(UserToken).where(UserToken.token == token)
    result = await db.execute(query)
    db_token = result.scalar_one_or_none()

    now = datetime.now()
    if not db_token or db_token.expires_at < now:
        return None
    # 剩余有效期不足一半时才续期，避免每个请求都写库
    if db_token.expires_at - now < TOKEN_TTL / 2:
        db_token.expires_at = now + TOKEN_TTL
        await db.commit()
    stmt = select(User).where(User.id == db_token.user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

#修改用户信息
async def update_user(db: AsyncSession, username: str, user_data: UserUpdateRequest):
    query = update(User).where(User.username == username).values(**user_data.model_dump(
        exclude_unset=True,
        exclude_none=True,
    ))

    result = await db.execute(query)
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found")

    updated_user = await get_user_by_username(db,username)
    return updated_user

#修改密码
async def update_password(db: AsyncSession, user: User, new_password: str,old_password: str):
    # 先校验旧密码，之前把旧密码重新哈希后比对，导致校验形同虚设
    if not security.verify_password(old_password, user.password):
        return False
    user.password = security.get_password_hash(new_password)
    # 密码已变更，作废该用户的登录令牌，强制重新登录
    await db.execute(delete(UserToken).where(UserToken.user_id == user.id))
    await db.commit()
    return True


#删除令牌（退出登录）
async def delete_token(db: AsyncSession, token: str):
    result = await db.execute(delete(UserToken).where(UserToken.token == token))
    await db.commit()
    return result.rowcount > 0

