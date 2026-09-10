
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from schemas.favorite import FavoriteCheckResponse, FavoriteAdd, FavoriteListResponse
from utils.response import success_response
from crud import favorite
from cache import favorite_cache
from config.db_config import get_db
from models.users import User
from utils.auth import get_current_user

router = APIRouter(prefix="/api/favorite",tags=["favorite"])


@router.get("/check")
async def check_favorite(
        news_id: int = Query(...,alias = "newsId"),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    query = await favorite.is_news_favorite(db, user.id,news_id)
    return success_response(message="检查收藏状态成功",data=FavoriteCheckResponse(isFavorite=query))

@router.post("/add")
async def add_favorite(
        favorite_add: FavoriteAdd,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    favorite_data = await favorite.add_favorite(db, user.id,favorite_add.news_id)
    await favorite_cache.invalidate(user.id)
    return success_response(message="添加收藏成功",data=favorite_data)

@router.delete("/remove")
async def remove_favorite(
        news_id: int = Query(...,alias="newsId"),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result = await favorite.delete_favorite(db, user.id, news_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="取消收藏失败")
    await favorite_cache.invalidate(user.id)
    return success_response(message="取消收藏成功")

@router.get("/list")
async def list_favorite(
        page: int = Query(default=1,ge=1),
        page_size: int = Query(default=10,ge=1,le=10,alias="pageSize"),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    version = await favorite_cache.get_version(user.id)
    cached = await favorite_cache.get_cache_list(user.id, version, page, page_size)
    if cached is not None:
        return success_response(message="收藏新闻列表获取成功", data=cached)
    row,total = await favorite.get_favorite_list(db, user.id, page, page_size)
    favorite_list = [{
        **news.__dict__,
        "favorite_id": favorite_id,
        "favorite_time": favorite_time
    } for news,favorite_time,favorite_id in row]
    has_more = total > page * page_size
    data = FavoriteListResponse(list = favorite_list,total=total,hasMore = has_more )
    await favorite_cache.set_cache_list(user.id, version, page, page_size, data.model_dump(by_alias=True, mode="json"))
    return success_response(message="收藏新闻列表获取成功",data=data)

@router.delete("/clear")
async def clear_favorite(
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    count = await favorite.clear_favorite(db, user.id)
    await favorite_cache.invalidate(user.id)
    return success_response(f"成功清除{count}收藏记录")