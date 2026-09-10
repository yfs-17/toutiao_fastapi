import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ai.agent import build_agent, get_saver
from ai.context import AgentContext
from config.db_config import get_db
from crud import ai_conversation as conversation_crud
from models.users import User
from utils.auth import get_current_user
from utils.response import success_response

router = APIRouter(prefix="/api/ai", tags=["ai"])

DEFAULT_TITLE = "新对话"
TITLE_MAX_LEN = 20
TOKEN_FLUSH_LEN = 12


class ChatRequest(BaseModel):
    conversation_id: int = Field(..., alias="conversationId")
    message: str | None = None
    resume: bool | None = Field(None, description="对上一次 interrupt 的确认结果，传值时 message 可省略")

    model_config = ConfigDict(populate_by_name=True)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _text_of(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def _serialize(conversation) -> dict:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "createdAt": conversation.created_at.isoformat() if conversation.created_at else None,
        "updatedAt": conversation.updated_at.isoformat() if conversation.updated_at else None,
    }


@router.get("/conversations")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversations = await conversation_crud.get_conversations(db, user.id)
    return success_response("获取会话列表成功", data=[_serialize(c) for c in conversations])


@router.post("/conversations")
async def create_conversation(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = await conversation_crud.create_conversation(db, user.id)
    return success_response("创建会话成功", data=_serialize(conversation))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    removed = await conversation_crud.delete_conversation(db, user.id, conversation_id)
    if not removed:
        raise HTTPException(status_code=404, detail="会话不存在")
    # 一并清掉 Redis 里的对话状态，避免留下孤儿数据
    await get_saver().adelete_thread(f"conv:{conversation_id}")
    return success_response("会话已删除")


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = await conversation_crud.get_conversation(db, user.id, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")

    checkpoint = await get_saver().aget_tuple(
        {"configurable": {"thread_id": f"conv:{conversation_id}"}}
    )
    if not checkpoint:
        return success_response("获取对话记录成功", data=[])

    # checkpoint 里存的是完整的图状态，这里只挑出能展示给用户的问答
    history = []
    for message in checkpoint.checkpoint.get("channel_values", {}).get("messages", []):
        kind = type(message).__name__
        if kind == "HumanMessage":
            history.append({"role": "user", "content": _text_of(message)})
        elif kind == "AIMessage" and not getattr(message, "tool_calls", None):
            text = _text_of(message)
            if text:
                history.append({"role": "assistant", "content": text})
    return success_response("获取对话记录成功", data=history)


@router.post("/chat")
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = await conversation_crud.get_conversation(db, user.id, body.conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")

    thread_id = f"conv:{conversation.id}"

    async def event_stream():
        try:
            # 首条消息落地后，用它的前 20 个字当会话标题
            if body.message and conversation.title == DEFAULT_TITLE:
                await conversation_crud.rename_conversation(
                    db, user.id, conversation.id, body.message[:TITLE_MAX_LEN]
                )

            agent = await build_agent()
            context = AgentContext(db=db, user=user)
            config = {"configurable": {"thread_id": thread_id}}
            payload = (
                Command(resume=body.resume)
                if body.resume is not None
                else {"messages": [("user", body.message)]}
            )

            buffer = ""
            async for mode, chunk in agent.astream(
                payload,
                config=config,
                context=context,
                stream_mode=["messages", "updates", "custom"],
            ):
                if mode == "messages":
                    message, meta = chunk
                    if meta.get("langgraph_node") != "model":
                        continue
                    text = _text_of(message)
                    if text:
                        buffer += text
                        if len(buffer) >= TOKEN_FLUSH_LEN:
                            yield sse("token", {"text": buffer})
                            buffer = ""
                elif mode == "custom":
                    # 工具通过 stream_writer 旁路推来的结构化数据（如新闻卡片）
                    if isinstance(chunk, dict) and chunk.get("type") == "news_card":
                        yield sse("news", chunk["item"])
                elif "__interrupt__" in chunk:
                    if buffer:
                        yield sse("token", {"text": buffer})
                        buffer = ""
                    for item in chunk["__interrupt__"]:
                        value = item.value if hasattr(item, "value") else item
                        yield sse(
                            "interrupt",
                            {
                                "question": value.get("question"),
                                "action": value.get("action"),
                            },
                        )
                else:
                    for node, update in chunk.items():
                        messages = update.get("messages", []) if isinstance(update, dict) else []
                        for message in messages:
                            if node == "model":
                                for call in getattr(message, "tool_calls", None) or []:
                                    yield sse(
                                        "tool_start",
                                        {"name": call["name"], "args": call["args"]},
                                    )
                            elif node == "tools":
                                yield sse("tool_end", {"name": getattr(message, "name", "")})

            if buffer:
                yield sse("token", {"text": buffer})
            await conversation_crud.touch_conversation(db, user.id, conversation.id)
            yield sse("done", {})
        except Exception as exc:  # noqa: BLE001 - 必须把异常转成 SSE 事件推给前端
            yield sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
