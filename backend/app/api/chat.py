"""
聊天问答 API：支持流式 SSE 和非流式响应
"""
from __future__ import annotations
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.schemas import ChatRequest, ChatResponse
from app.services import vector_store, chat_service, conversation_manager

router = APIRouter(prefix="/api/chat", tags=["聊天问答"])


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    流式聊天接口（SSE）
    逐 token 返回 LLM 生成的内容
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    # 如果没有传入 conversation_id，创建新会话
    conversation_id = request.conversation_id
    if not conversation_id:
        conversation_id = conversation_manager.create_conversation()

    # 保存用户问题
    conversation_manager.add_message(conversation_id, "user", request.query)

    # 检索相关文档
    docs_with_scores = vector_store.search(
        query=request.query,
        doc_ids=request.doc_ids if request.doc_ids else None,
    )

    if not docs_with_scores:
        # 无匹配文档时返回提示
        async def no_doc_stream():
            yield {"event": "chunk", "data": json.dumps({"content": "未找到相关文档内容，请先上传文档后再试。"})}
            yield {"event": "end", "data": json.dumps({"is_end": True})}
        return EventSourceResponse(no_doc_stream())

    retrieved_docs = [doc for doc, _ in docs_with_scores]

    async def generate():
        """SSE 生成器"""
        full_answer = ""
        try:
            async for chunk in chat_service.stream_answer(
                query=request.query,
                context_docs=retrieved_docs,
            ):
                full_answer += chunk
                yield {"event": "chunk", "data": json.dumps({"content": chunk})}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
            return

        # 保存回答
        conversation_manager.add_message(conversation_id, "assistant", full_answer)

        # 发送结束信号和来源信息
        sources = [
            {
                "content": doc.page_content[:200],
                "source": doc.metadata.get("source_file", "未知"),
                "score": round(score, 4),
            }
            for doc, score in docs_with_scores[:3]
        ]
        yield {
            "event": "end",
            "data": json.dumps({
                "is_end": True,
                "conversation_id": conversation_id,
                "sources": sources,
            }),
        }

    return EventSourceResponse(generate())


@router.post("/query", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    """
    非流式聊天接口（一次性返回完整回答）
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    conversation_id = request.conversation_id
    if not conversation_id:
        conversation_id = conversation_manager.create_conversation()

    conversation_manager.add_message(conversation_id, "user", request.query)

    docs_with_scores = vector_store.search(
        query=request.query,
        doc_ids=request.doc_ids if request.doc_ids else None,
    )

    if not docs_with_scores:
        answer = "未找到相关文档内容，请先上传文档后再试。"
        sources = []
    else:
        retrieved_docs = [doc for doc, _ in docs_with_scores]
        answer = await chat_service.full_answer(
            query=request.query,
            context_docs=retrieved_docs,
        )
        conversation_manager.add_message(conversation_id, "assistant", answer)
        sources = [
            {
                "content": doc.page_content[:200],
                "source": doc.metadata.get("source_file", "未知"),
                "score": round(score, 4),
            }
            for doc, score in docs_with_scores
        ]

    return ChatResponse(
        answer=answer,
        sources=sources,
        conversation_id=conversation_id,
    )


@router.get("/conversations")
async def list_conversations():
    """列出所有对话会话"""
    conversations = conversation_manager.list_conversations()
    return [
        {
            "conversation_id": c.conversation_id,
            "message_count": len(c.messages),
            "created_at": c.created_at.isoformat(),
            "preview": c.messages[-1].content[:100] if c.messages else "",
        }
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """获取指定会话的历史消息"""
    conv = conversation_manager.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "conversation_id": conv.conversation_id,
        "messages": [
            {"role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()}
            for m in conv.messages
        ],
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除指定会话"""
    conversation_manager.delete_conversation(conversation_id)
    return {"message": "会话已删除"}
