from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import select, update, delete
from sqlalchemy.sql.functions import func

from models.history import History
from models.news import News


#查询历史记录
async def get_history(
        db: AsyncSession,
        user_id: int,
        news_id: int
):
    stmt = select(History).where(History.user_id == user_id, History.news_id == news_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


#新增历史记录
async def add_history(
        db: AsyncSession,
        user_id: int,
        news_id: int
):
    history = History(user_id=user_id, news_id=news_id)
    db.add(history)
    await db.commit()
    await db.refresh(history)
    return history

#更新浏览时间
async def update_history_time(
        db: AsyncSession,
        user_id: int,
        news_id: int
):
    stmt = update(History).where(History.user_id == user_id, History.news_id == news_id).values(view_time=datetime.now())
    await db.execute(stmt)
    await db.commit()
    result = await get_history(db, user_id, news_id)
    return result

#获取浏览记录列表
async def get_history_list(
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        page_size: int = 10
):
    count_query = select(func.count()).where(History.user_id == user_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    query = (select(News,History.view_time)
             .join(History,History.news_id == News.id)
             .where(History.user_id == user_id)
             .offset(offset).limit(page_size)
             )
    result = await db.execute(query)
    row = result.all()
    return row, total

async def delete_history(
        db: AsyncSession,
        history_id: int,
        user_id: int
):
    stmt = delete(History).where(History.user_id == user_id, History.news_id == history_id)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0

async def clear_history(
        db: AsyncSession,
        user_id: int
):
    stmt = delete(History).where(History.user_id == user_id)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0
