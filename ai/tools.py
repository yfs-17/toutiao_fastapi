from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langgraph.types import interrupt

from ai.context import AgentContext
from cache import favorite_cache, history_cache
from crud import favorite as favorite_crud
from crud import history as history_crud
from crud import news as news_crud

MAX_DESC_LEN = 60


def _clip(text: str | None, limit: int = MAX_DESC_LEN) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    return text if len(text) <= limit else text[:limit] + "..."


def _user(runtime: ToolRuntime[AgentContext]):
    return runtime.context.user


async def _news_title(db, news_id: int) -> str:
    detail = await news_crud.get_news_detail(db, news_id)
    return detail.title if detail else f"id 为 {news_id} 的新闻"


def _news_card(news) -> dict:
    """转成前端 NewsItem 组件需要的字段。"""
    return {
        "id": news.id,
        "title": news.title,
        "description": news.description,
        "image": news.image,
        "author": news.author,
        "publishTime": news.publish_time.strftime("%Y-%m-%d %H:%M") if news.publish_time else None,
        "views": news.views,
    }


def _push_card(runtime: ToolRuntime[AgentContext], news) -> None:
    """把新闻卡片旁路推给前端；非流式调用时没有 writer，静默跳过。"""
    writer = getattr(runtime, "stream_writer", None)
    if writer is None:
        return
    writer({"type": "news_card", "item": _news_card(news)})


# ---------------------------------------------------------------- 浏览新闻


@tool
async def get_news_categories(runtime: ToolRuntime[AgentContext] = None) -> str:
    """获取全部新闻分类。返回分类的 id 和名称，后续按分类查新闻时需要用到这个 id。"""
    categories = await news_crud.get_categories(runtime.context.db)
    if not categories:
        return "当前没有任何新闻分类。"
    return "\n".join(f"{c.id}: {c.name}" for c in categories)


@tool
async def get_news_list(
    category_id: int,
    page: int = 1,
    runtime: ToolRuntime[AgentContext] = None,
) -> str:
    """按分类分页查询新闻列表。

    Args:
        category_id: 分类 id，必须来自 get_news_categories 的返回值。
        page: 页码，从 1 开始，每页 10 条。
    """
    page = max(1, page)
    db = runtime.context.db
    offset = (page - 1) * 10
    rows = await news_crud.get_news_list(db, category_id, offset, 10)
    if not rows:
        return f"分类 {category_id} 的第 {page} 页没有新闻了。"
    total = await news_crud.get_news_total(db, category_id)
    lines = [f"{n.id} | {n.title} | {_clip(n.description)}" for n in rows]
    return f"分类 {category_id} 第 {page} 页（共 {total} 条）：\n" + "\n".join(lines)


@tool
async def get_news_detail(
    news_id: int,
    runtime: ToolRuntime[AgentContext] = None,
) -> str:
    """根据新闻 id 查询新闻详情。

    Args:
        news_id: 新闻 id，必须来自查询结果的返回值。
    """
    detail = await news_crud.get_news_detail(runtime.context.db, news_id)
    if not detail:
        return f"没有找到 id 为 {news_id} 的新闻。"
    _push_card(runtime, detail)
    return (
        f"id: {detail.id}\n"
        f"标题: {detail.title}\n"
        f"作者: {detail.author or '佚名'}\n"
        f"发布时间: {detail.publish_time.isoformat() if detail.publish_time else '未知'}\n"
        f"浏览量: {detail.views}\n"
        f"摘要: {_clip(detail.description, 200)}"
    )


@tool
async def search_news(
    keyword: str,
    runtime: ToolRuntime[AgentContext] = None,
) -> str:
    """按关键词搜索新闻，匹配标题和简介。用户问"有没有关于 XX 的新闻"时用这个。

    Args:
        keyword: 搜索关键词。
    """
    rows = await news_crud.search_news(runtime.context.db, keyword, 10)
    if not rows:
        return f'没有找到包含"{keyword}"的新闻。'
    lines = [f"{n.id} | {n.title} | {_clip(n.description)}" for n in rows]
    return f'搜索"{keyword}"的结果：\n' + "\n".join(lines)


# ---------------------------------------------------------------- 收藏


@tool
async def list_my_favorites(
    page: int = 1,
    runtime: ToolRuntime[AgentContext] = None,
) -> str:
    """查看当前用户收藏的新闻列表。

    Args:
        page: 页码，从 1 开始，每页 10 条。
    """
    ctx = runtime.context
    page = max(1, page)
    rows, total = await favorite_crud.get_favorite_list(ctx.db, ctx.user.id, page, 10)
    if not rows:
        return "你还没有收藏任何新闻。" if page == 1 else f"收藏列表第 {page} 页是空的。"
    lines = [f"{news.id} | {news.title}" for news, _favorite_time, _fid in rows]
    return f"你的收藏（共 {total} 条，第 {page} 页）：\n" + "\n".join(lines)


@tool
async def add_favorite(
    news_id: int,
    runtime: ToolRuntime[AgentContext] = None,
) -> str:
    """收藏一条新闻。

    Args:
        news_id: 要收藏的新闻 id，必须来自查询结果的返回值。
    """
    ctx = runtime.context
    detail = await news_crud.get_news_detail(ctx.db, news_id)
    if not detail:
        return f"没有找到 id 为 {news_id} 的新闻，无法收藏。"
    if await favorite_crud.is_news_favorite(ctx.db, ctx.user.id, news_id):
        return f"《{detail.title}》已经在你的收藏里了。"
    await favorite_crud.add_favorite(ctx.db, ctx.user.id, news_id)
    await favorite_cache.invalidate(ctx.user.id)
    return f"已收藏《{detail.title}》。"


@tool
async def remove_favorite(
    news_id: int,
    runtime: ToolRuntime[AgentContext] = None,
) -> str:
    """取消收藏一条新闻。

    Args:
        news_id: 要取消收藏的新闻 id，必须来自查询结果或收藏列表的返回值。
    """
    ctx = runtime.context
    title = await _news_title(ctx.db, news_id)
    removed = await favorite_crud.delete_favorite(ctx.db, ctx.user.id, news_id)
    await favorite_cache.invalidate(ctx.user.id)
    if not removed:
        return f"《{title}》不在你的收藏里。"
    return f"已取消收藏《{title}》。"


# ---------------------------------------------------------------- 浏览历史


@tool
async def list_my_history(
    page: int = 1,
    runtime: ToolRuntime[AgentContext] = None,
) -> str:
    """查看当前用户的浏览历史。

    Args:
        page: 页码，从 1 开始，每页 10 条。
    """
    ctx = runtime.context
    page = max(1, page)
    rows, total = await history_crud.get_history_list(ctx.db, ctx.user.id, page, 10)
    if not rows:
        return "你还没有浏览记录。" if page == 1 else f"浏览历史第 {page} 页是空的。"
    lines = [f"{news.id} | {news.title}" for news, _view_time in rows]
    return f"你的浏览历史（共 {total} 条，第 {page} 页）：\n" + "\n".join(lines)


@tool
async def delete_history_item(
    news_id: int,
    runtime: ToolRuntime[AgentContext] = None,
) -> str:
    """删除某条新闻的浏览记录。

    Args:
        news_id: 要删除浏览记录的新闻 id，必须来自浏览历史列表的返回值。
    """
    ctx = runtime.context
    title = await _news_title(ctx.db, news_id)
    removed = await history_crud.delete_history(ctx.db, news_id, ctx.user.id)
    await history_cache.invalidate(ctx.user.id)
    if not removed:
        return f"浏览历史里没有《{title}》这条记录。"
    return f"已从浏览历史中删除《{title}》。"


# ---------------------------------------------------------------- 需要二次确认的操作


@tool
async def clear_history(runtime: ToolRuntime[AgentContext] = None) -> str:
    """清空当前用户的全部浏览历史。此操作不可恢复，执行前会暂停并向用户确认。"""
    decision = interrupt(
        {
            "action": "clear_history",
            "question": "确定要清空全部浏览历史吗？此操作不可恢复。",
        }
    )
    if decision is not True:
        return "用户取消了操作，浏览历史没有变动。"
    ctx = runtime.context
    count = await history_crud.clear_history(ctx.db, ctx.user.id)
    await history_cache.invalidate(ctx.user.id)
    return f"已清空 {count} 条浏览历史。"


@tool
async def clear_favorites(runtime: ToolRuntime[AgentContext] = None) -> str:
    """清空当前用户的全部收藏。此操作不可恢复，执行前会暂停并向用户确认。"""
    decision = interrupt(
        {
            "action": "clear_favorites",
            "question": "确定要清空全部收藏吗？此操作不可恢复。",
        }
    )
    if decision is not True:
        return "用户取消了操作，收藏没有变动。"
    ctx = runtime.context
    count = await favorite_crud.clear_favorite(ctx.db, ctx.user.id)
    await favorite_cache.invalidate(ctx.user.id)
    return f"已清空 {count} 条收藏。"


ALL_TOOLS = [
    get_news_categories,
    get_news_list,
    get_news_detail,
    search_news,
    list_my_favorites,
    add_favorite,
    remove_favorite,
    list_my_history,
    delete_history_item,
    clear_history,
    clear_favorites,
]
