
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import update

from models.news import Category,News


# 将 Category ORM 对象转为可 JSON 序列化的 dict
def serialize_category(category: Category) -> dict:
    return {
        "id": category.id,
        "name": category.name,
        "sort_order": category.sort_order,
        "created_at": category.created_at.isoformat() if category.created_at else None,
        "updated_at": category.updated_at.isoformat() if category.updated_at else None,
    }


# 将 News ORM 对象转为可 JSON 序列化的 dict
def serialize_news(news: News) -> dict:
    return {
        "id": news.id,
        "title": news.title,
        "description": news.description,
        "content": news.content,
        "image": news.image,
        "author": news.author,
        "category_id": news.category_id,
        "views": news.views,
        "publish_time": news.publish_time.isoformat() if news.publish_time else None,
        "created_at": news.created_at.isoformat() if news.created_at else None,
        "updated_at": news.updated_at.isoformat() if news.updated_at else None,
    }

#获取分类名称
async def get_categories(db: AsyncSession, skip: int = 0, limit: int = 100):
    stmt = select(Category).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

#获取新闻分类列表
async def get_news_list(db: AsyncSession,category_id: int, skip: int = 0, limit: int = 10):
    stmt = select(News).where(News.category_id == category_id).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

#获取分类新闻的总数
async def get_news_total(db: AsyncSession, category_id: int):
    stmt = select(func.count(News.id)).where(News.category_id == category_id)
    result = await db.execute(stmt)
    return result.scalar_one()

#根据新闻id查询详情
async def get_news_detail(db: AsyncSession, news_id: int):
    stmt = select(News).where(News.id == news_id)
    result = await db.execute(stmt)
    return result.scalar_one()

#更新浏览量
async def increase_news_view(db: AsyncSession, news_id: int):
    stmt = update(News).where(News.id == news_id).values(views = News.views + 1)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0

#获取相关新闻
async def get_related_news(db: AsyncSession, category_id: int, news_id: int,limit: int = 5):
    stmt = select(News).where(
        News.category_id == category_id,
        News.id != news_id
    ).order_by(
        News.views.desc(),
        News.publish_time.desc()
    ).limit(limit)
    result = await db.execute(stmt)
    related_news = result.scalars().all()
    return [{
        "id": news_detail.id,
        "title": news_detail.title,
        "content": news_detail.content,
        "image": news_detail.image,
        "author": news_detail.author,
        "publishTime": news_detail.publish_time.isoformat() if news_detail.publish_time else None,
        "categoryId": news_detail.category_id,
        "views": news_detail.views,
    } for news_detail in related_news]