from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from schemas.favorite import FavoriteCheckResponse, FavoriteAdd, FavoriteListResponse
from schemas.history import AddHistoryResponse, HistoryListResponse
from utils.response import success_response
from config.db_config import get_db
from models.users import User
from utils.auth import get_current_user
from crud import history



router = APIRouter(prefix="/api/history",tags=["history"])



@router.post("/add")
async def add_history(
        history_news: AddHistoryResponse,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    history_result = await history.get_history(db,user.id,history_news.news_id)
    if history_result:
        result = await history.update_history_time(db,user.id,history_news.news_id)
    else:
        result = await history.add_history(db,user.id,history_news.news_id)
    return success_response("成功获取新闻记录",data=result)

@router.get("/list")
async def list_history(
page: int = Query(default=1,ge=1),
        page_size: int = Query(default=10,ge=1,le=10,alias="pageSize"),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    row, total = await history.get_history_list(db, user.id, page, page_size)
    history_list = [{
        **news.__dict__,
        "view_time": view_time
    } for news, view_time in row]
    has_more = total > page * page_size
    data = HistoryListResponse(list=history_list, total=total, hasMore=has_more)
    return success_response("获取历史浏览记录成功",data=data)

@router.delete("/delete/{history_id}")
async def delete_history(
        history_id: int,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result = await history.delete_history(db,history_id,user.id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="删除失败")
    return success_response("删除浏览历史成功")

@router.delete("/clear")
async def clear_history(
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    result = await history.clear_history(db,user.id)
    return success_response(f"清空{result}历史记录成功")