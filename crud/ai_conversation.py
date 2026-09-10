from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai_conversation import AiConversation


# 新建会话
async def create_conversation(db: AsyncSession, user_id: int, title: str = "新对话"):
    conversation = AiConversation(user_id=user_id, title=title)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


# 按 id 查询会话，同时校验归属，防止越权访问他人会话
async def get_conversation(db: AsyncSession, user_id: int, conversation_id: int):
    stmt = select(AiConversation).where(
        AiConversation.id == conversation_id,
        AiConversation.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# 获取用户的全部会话，最近活跃的排前面
async def get_conversations(db: AsyncSession, user_id: int):
    stmt = (
        select(AiConversation)
        .where(AiConversation.user_id == user_id)
        .order_by(AiConversation.updated_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# 刷新会话的活跃时间，让它排到列表前面
async def touch_conversation(db: AsyncSession, user_id: int, conversation_id: int):
    stmt = (
        update(AiConversation)
        .where(AiConversation.id == conversation_id, AiConversation.user_id == user_id)
        .values(updated_at=datetime.now())
    )
    await db.execute(stmt)
    await db.commit()


# 重命名会话
async def rename_conversation(db: AsyncSession, user_id: int, conversation_id: int, title: str):
    stmt = (
        update(AiConversation)
        .where(AiConversation.id == conversation_id, AiConversation.user_id == user_id)
        .values(title=title)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0


# 删除会话
async def delete_conversation(db: AsyncSession, user_id: int, conversation_id: int):
    stmt = delete(AiConversation).where(
        AiConversation.id == conversation_id,
        AiConversation.user_id == user_id,
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0
