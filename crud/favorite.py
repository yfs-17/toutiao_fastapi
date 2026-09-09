
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import select, delete, join
from sqlalchemy.sql.functions import func

from models.favorite import Favorite
from models.news import News


#判断检查是否收藏
async def is_news_favorite(
        db: AsyncSession,
        user_id: int,
        news_id: int
):
    query = select(Favorite).where(Favorite.news_id == news_id,Favorite.user_id == user_id)
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


#添加收藏
async def add_favorite(
        db: AsyncSession,
        user_id: int,
        news_id: int
):
    favorite = Favorite(user_id=user_id, news_id=news_id)
    db.add(favorite)
    await db.commit()
    await db.refresh(favorite)
    return favorite

#取消收藏
async def delete_favorite(
        db: AsyncSession,
        user_id: int,
        news_id: int
):
    stmt = delete(Favorite).where(Favorite.news_id == news_id,Favorite.user_id == user_id)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0

#获取收藏列表
async def get_favorite_list(
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        page_size: int = 10
):
    count_query = select(func.count()).where(Favorite.user_id == user_id)
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    query = (select(News,Favorite.created_at.label("favorite_time"),Favorite.id.label("favorite_id"))
             .join(Favorite,Favorite.news_id == News.id)
             .where(Favorite.user_id == user_id)
             .offset(offset).limit(page_size)
             )
    result = await db.execute(query)
    row = result.all()
    return row, total

#清除收藏列表
async def clear_favorite(db: AsyncSession, user_id: int):
    query = delete(Favorite).where(Favorite.user_id == user_id)
    result = await db.execute(query)
    await db.commit()
    return result.rowcount or 0