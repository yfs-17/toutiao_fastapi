from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from models.users import User


@dataclass
class AgentContext:
    """每次请求注入给 agent 的运行时上下文，工具函数通过 ToolRuntime 取用。

    不放在 contextvars 里，是因为 langgraph 的工具签名原生支持运行时上下文注入，
    且同一进程内多个请求各自持有独立的 context，天然隔离。
    """

    db: AsyncSession
    user: User
