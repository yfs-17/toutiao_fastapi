from config import cache_config

VERSION_KEY = "favorite:version:{user_id}"
LIST_KEY = "favorite:list:{user_id}:{version}:{page}:{page_size}"


# 获取用户收藏列表的缓存版本号
async def get_version(user_id: int) -> int:
    version = await cache_config.get_cache(VERSION_KEY.format(user_id=user_id))
    return int(version) if version else 0


# 收藏数据变更时，版本号 +1 使旧缓存失效
async def invalidate(user_id: int):
    return await cache_config.incr_cache(VERSION_KEY.format(user_id=user_id))


# 获取收藏列表缓存
async def get_cache_list(user_id: int, version: int, page: int, page_size: int):
    key = LIST_KEY.format(user_id=user_id, version=version, page=page, page_size=page_size)
    return await cache_config.get_cache_json(key)


# 写入收藏列表缓存
async def set_cache_list(user_id: int, version: int, page: int, page_size: int, value: dict, expire: int = 300):
    key = LIST_KEY.format(user_id=user_id, version=version, page=page, page_size=page_size)
    return await cache_config.set_cache(key, value, expire)
