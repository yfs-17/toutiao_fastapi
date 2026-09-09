
import sqlalchemy
from fastapi import APIRouter,Depends,HTTPException,Query


from crud import news
from sqlalchemy.ext.asyncio import AsyncSession
from config.db_config import get_db
router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/categories")
async def get_categories(skip: int = 0, limit: int = 100,db: AsyncSession = Depends(get_db)):
    categories = await news.get_categories(db,skip, limit)
    return {
        "code": 200,
        "message": "success",
        "data": categories
    }

@router.get("/list")
async def get_news_list(
        category_id: int = Query(...,alias="categoryId"),
        db: AsyncSession = Depends(get_db),
        page: int = 1,
        page_size: int = Query(10, alias="pageSize",lt=100)
):
    offset = (page-1)*page_size
    new_list = await news.get_news_list(db,category_id,offset,page_size)
    total = await news.get_news_total(db,category_id)
    has_more = (offset + len(new_list))<total
    return {
        "code": 200,
        "message": "success",
        "data": {
            "list": new_list,
            "total": total,
            "hasMore": has_more
        }
    }

@router.get("/detail")
async def get_news_detail(
        news_id: int = Query(...,alias="id"),
        db: AsyncSession = Depends(get_db)
):
    news_detail = await news.get_news_detail(db,news_id)
    if not news_detail:
        raise HTTPException(status_code=404,detail="新闻不存在")
    view_res = await news.increase_news_view(db,news_id)
    if not view_res:
        raise HTTPException(status_code=404,detail="更新浏览量失败")
    related_news = await news.get_related_news(db,news_id,news_detail.category_id)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": news_detail.id,
            "title": news_detail.title,
            "content": news_detail.content,
            "image": news_detail.image,
            "author": news_detail.author,
            "publishTime": news_detail.publish_time,
            "categoryId": news_detail.category_id,
            "views": news_detail.views,
            "relatedNews":related_news#相关新闻列表
        }
    }