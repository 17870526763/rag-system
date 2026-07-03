"""
对话管理服务：维护多轮对话会话历史
使用内存存储（生产环境可替换为 Redis/数据库）
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional

from app.schemas import ConversationMessage, Conversation


class ConversationManager:
    """对话会话管理器"""

    def __init__(self, max_history: int = 20):
        self._conversations: dict[str, Conversation] = {}
        self._max_history = max_history

    def create_conversation(self) -> str:
        """创建新会话，返回 conversation_id"""
        cid = str(uuid.uuid4())[:12]
        self._conversations[cid] = Conversation(
            conversation_id=cid,
            messages=[],
            created_at=datetime.now(),
        )
        return cid

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
    ) -> Conversation:
        """添加消息到会话"""
        conv = self._conversations.get(conversation_id)
        if not conv:
            conv = Conversation(
                conversation_id=conversation_id,
                messages=[],
                created_at=datetime.now(),
            )
            self._conversations[conversation_id] = conv

        conv.messages.append(ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
        ))

        # 限制历史消息数量
        if len(conv.messages) > self._max_history:
            conv.messages = conv.messages[-self._max_history:]

        return conv

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """获取会话"""
        return self._conversations.get(conversation_id)

    def list_conversations(self) -> list[Conversation]:
        """列出所有会话"""
        return sorted(
            self._conversations.values(),
            key=lambda c: c.created_at,
            reverse=True,
        )

    def delete_conversation(self, conversation_id: str):
        """删除会话"""
        self._conversations.pop(conversation_id, None)

    def get_history_messages(
        self,
        conversation_id: str,
        n: int = 6,
    ) -> list[dict]:
        """获取最近 N 条历史消息（用于 LLM 上下文）"""
        conv = self._conversations.get(conversation_id)
        if not conv:
            return []
        messages = []
        for msg in conv.messages[-n:]:
            messages.append({"role": msg.role, "content": msg.content})
        return messages


# 全局单例
conversation_manager = ConversationManager()
