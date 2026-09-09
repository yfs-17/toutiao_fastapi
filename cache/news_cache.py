from typing import Any, List

from config import cache_config

CATEGORIES_KEY = "news:categories"


#获取分类缓存
async def get_cache_categories():
    return await cache_config.get_cache(CATEGORIES_KEY)

#写入新闻分类缓存
async def set_cache_categories(value: List[dict[str,Any]],expire: int = 3600):
    return await cache_config.set_cache(CATEGORIES_KEY,value,expire)



