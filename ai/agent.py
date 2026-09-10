import os

import redis.asyncio as aioredis
from langchain.agents import create_agent

from ai.context import AgentContext
from ai.llm import get_llm
from ai.prompts import SYSTEM_PROMPT
from ai.redis_checkpointer import AsyncRedisCheckpointer
from ai.tools import ALL_TOOLS

DEFAULT_REDIS_URL = "redis://127.0.0.1:6379/2"
CHECKPOINT_TTL_DAYS = 30

_client: aioredis.Redis | None = None
_saver: AsyncRedisCheckpointer | None = None


def get_redis_client() -> aioredis.Redis:
    """checkpoint 专用连接，单独用 db 2 与业务缓存（db 1）隔离。"""
    global _client
    if _client is None:
        _client = aioredis.from_url(
            os.getenv("AI_REDIS_URL", DEFAULT_REDIS_URL),
            decode_responses=True,
        )
    return _client


def get_saver() -> AsyncRedisCheckpointer:
    """惰性创建 checkpointer。TTL 30 天，每次写入刷新，活跃会话不会被回收。"""
    global _saver
    if _saver is None:
        _saver = AsyncRedisCheckpointer(
            get_redis_client(),
            ttl_seconds=CHECKPOINT_TTL_DAYS * 24 * 60 * 60,
        )
    return _saver


async def build_agent():
    """按当前配置组装 agent 图。"""
    return create_agent(
        get_llm(),
        ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        context_schema=AgentContext,
        checkpointer=get_saver(),
    )
