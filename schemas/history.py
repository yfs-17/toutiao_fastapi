from datetime import datetime

from pydantic import BaseModel, Field

from schemas.base import NewsItemBase


class AddHistoryResponse(BaseModel):
    news_id: int = Field(...,alias="newsId")


class HistoryList(NewsItemBase):
    view_time: datetime = Field(...,alias="viewTime")


class HistoryListResponse(BaseModel):
    list: list[HistoryList]
    total: int
    has_more: bool = Field(...,alias="hasMore")