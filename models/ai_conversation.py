from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from models.users import User


class Base(DeclarativeBase):
    pass


class AiConversation(Base):
    """
    AI 会话表ORM模型

    只保存会话的元信息，具体的对话内容存在 Redis 的 checkpoint 里。
    """
    __tablename__ = 'ai_conversation'

    __table_args__ = (
        Index('fk_ai_conversation_user_idx', 'user_id'),
        Index('idx_ai_conversation_updated', 'updated_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="会话ID")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey(User.id), nullable=False, comment="用户ID")
    title: Mapped[str] = mapped_column(String(100), nullable=False, default='新对话', comment="会话标题")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now,
                                                 comment="更新时间")

    def __repr__(self):
        return f"<AiConversation(id={self.id}, user_id={self.user_id}, title='{self.title}')>"
