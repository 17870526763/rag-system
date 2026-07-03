"""Pydantic 数据模型定义"""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class DocumentUploadResponse(BaseModel):
    """文档上传成功响应"""
    doc_id: str
    filename: str
    chunk_count: int
    message: str


class DocumentInfo(BaseModel):
    """文档信息"""
    doc_id: str
    filename: str
    upload_time: datetime
    chunk_count: int
    file_size: int


class ChatRequest(BaseModel):
    """聊天请求"""
    query: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    doc_ids: list[str] = Field(default_factory=list, description="指定文档ID列表，为空则检索全部")
    conversation_id: Optional[str] = Field(default=None, description="会话ID，用于多轮对话")


class ChatChunk(BaseModel):
    """SSE流式响应块"""
    content: str
    is_end: bool = False


class ChatResponse(BaseModel):
    """非流式聊天响应（完整）"""
    answer: str
    sources: list[dict]
    conversation_id: str


class ConversationMessage(BaseModel):
    """对话消息"""
    role: str
    content: str
    timestamp: datetime


class Conversation(BaseModel):
    """对话会话"""
    conversation_id: str
    messages: list[ConversationMessage]
    created_at: datetime
