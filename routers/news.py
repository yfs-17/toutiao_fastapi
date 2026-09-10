
from fastapi import APIRouter,Depends,HTTPException,Query


from crud import news
from cache import news_cache
from sqlalchemy.ext.asyncio import AsyncSession
from config.db_config import get_db
from utils.response import success_response
router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/categories")
async def get_categories(skip: int = 0, limit: int = 100,db: AsyncSession = Depends(get_db)):
    # 先查缓存
    cached = await news_cache.get_cache_categories()
    if cached is not None:
        return success_response(data=cached)
    # 未命中，查数据库
    categories = await news.get_categories(db,skip, limit)
    data = [news.serialize_category(c) for c in categories]
    # 写入缓存
    await news_cache.set_cache_categories(data)
    return success_response(data=data)

@router.get("/list")
async def get_news_list(
        category_id: int = Query(...,alias="categoryId"),
        db: AsyncSession = Depends(get_db),
        page: int = 1,
        page_size: int = Query(10, alias="pageSize",lt=100)
):
    # 先查缓存
    cached = await news_cache.get_cache_news_list(category_id, page, page_size)
    if cached is not None:
        return success_response(data=cached)
    # 未命中，查数据库
    offset = (page-1)*page_size
    new_list = await news.get_news_list(db,category_id,offset,page_size)
    total = await news.get_news_total(db,category_id)
    has_more = (offset + len(new_list))<total
    data = {
        "list": [news.serialize_news(n) for n in new_list],
        "total": total,
        "hasMore": has_more
    }
    # 写入缓存
    await news_cache.set_cache_news_list(category_id, page, page_size, data)
    return success_response(data=data)

@router.get("/detail")
async def get_news_detail(
        news_id: int = Query(...,alias="id"),
        db: AsyncSession = Depends(get_db)
):
    # 先查缓存
    cached = await news_cache.get_cache_news_detail(news_id)
    if cached is not None:
        # 浏览量仍需实时累计
        await news.increase_news_view(db, news_id)
        cached["views"] += 1
        await news_cache.set_cache_news_detail(news_id, cached)
        return success_response(data=cached)
    # 未命中，查数据库
    news_detail = await news.get_news_detail(db,news_id)
    if not news_detail:
        raise HTTPException(status_code=404,detail="新闻不存在")
    view_res = await news.increase_news_view(db,news_id)
    if not view_res:
        raise HTTPException(status_code=404,detail="更新浏览量失败")
    related_news = await news.get_related_news(db,news_id,news_detail.category_id)
    data = {
        "id": news_detail.id,
        "title": news_detail.title,
        "content": news_detail.content,
        "image": news_detail.image,
        "author": news_detail.author,
        "publishTime": news_detail.publish_time.isoformat() if news_detail.publish_time else None,
        "categoryId": news_detail.category_id,
        "views": news_detail.views + 1,
        "relatedNews": related_news  # 相关新闻列表
    }
    # 写入缓存
    await news_cache.set_cache_news_detail(news_id, data)
    return success_response(data=data)
