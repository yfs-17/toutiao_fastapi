from typing import Any, List

from config import cache_config

CATEGORIES_KEY = "news:categories"
NEWS_LIST_KEY = "news:list:{category_id}:{page}:{page_size}"
NEWS_DETAIL_KEY = "news:detail:{news_id}"


# 获取分类缓存
async def get_cache_categories():
    return await cache_config.get_cache_json(CATEGORIES_KEY)


# 写入新闻分类缓存
async def set_cache_categories(value: List[dict[str, Any]], expire: int = 3600):
    return await cache_config.set_cache(CATEGORIES_KEY, value, expire)


# 获取新闻列表缓存
async def get_cache_news_list(category_id: int, page: int, page_size: int):
    key = NEWS_LIST_KEY.format(category_id=category_id, page=page, page_size=page_size)
    return await cache_config.get_cache_json(key)


# 写入新闻列表缓存
async def set_cache_news_list(category_id: int, page: int, page_size: int, value: dict, expire: int = 300):
    key = NEWS_LIST_KEY.format(category_id=category_id, page=page, page_size=page_size)
    return await cache_config.set_cache(key, value, expire)


# 获取新闻详情缓存
async def get_cache_news_detail(news_id: int):
    key = NEWS_DETAIL_KEY.format(news_id=news_id)
    return await cache_config.get_cache_json(key)


# 写入新闻详情缓存
async def set_cache_news_detail(news_id: int, value: dict, expire: int = 600):
    key = NEWS_DETAIL_KEY.format(news_id=news_id)
    return await cache_config.set_cache(key, value, expire)
