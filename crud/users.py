
import uuid

from datetime import datetime
from datetime import timedelta
from unittest import result

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import update

from models.users import User, UserToken
from schemas.users import UserRequest, UserUpdateRequest
from utils import security


#根据用户名查询数据库
async def get_user_by_username(db: AsyncSession, username: str):
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

#创建用户
async def create_user(db: AsyncSession, user_data: UserRequest):
    hash_password = security.get_password_hash(user_data.password)
    user = User(username=user_data.username, password=hash_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

#生成token
async def create_token(db: AsyncSession, user_id: int):
    token = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(minutes=7)
    query = select(UserToken).where(UserToken.user_id == user_id)
    result = await db.execute(query)
    user_token = result.scalar_one_or_none()

    if user_token:
        user_token.token = token
        user_token.expires_at = expires_at
    else:
        user_token = UserToken(user_id=user_id, token=token, expires_at=expires_at)
        db.add(user_token)
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

    if not db_token or db_token.expires_at < datetime.now():
        return None
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
    if security.verify_password(security.get_password_hash(old_password), user.password):
        return False
    hashed_password = security.get_password_hash(new_password)
    user.password = hashed_password
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return True

