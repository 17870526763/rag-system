"""
LLM 问答服务：基于检索结果生成回答
支持流式输出（SSE）、Prompt 模板、Few-shot 示例注入
"""
from __future__ import annotations
from typing import AsyncGenerator, Optional
from openai import AsyncOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.documents import Document

from app.core import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


# System Prompt 模板 — 通过工程化优化回答质量
SYSTEM_PROMPT = """\
你是一个专业的知识问答助手，基于提供的文档内容回答用户问题。

请遵循以下原则：
1. 严格基于提供的文档内容回答，不要编造文档中未提及的信息
2. 如果文档内容不足以回答问题，请明确告知用户
3. 回答应当准确、简洁、有条理，适当使用列表或分点说明
4. 引用文档中的关键信息时，可以提及来源文件名
5. 使用与用户提问相同的语言进行回答
6. 如果问题与文档内容无关，请引导用户提供相关文档

以下是相关的参考上下文：
{context}
"""

# Few-shot 示例 — 注入到 prompt 中提升回答质量
FEW_SHOT_EXAMPLES = [
    {"role": "user", "content": "这个系统的主要功能是什么？"},
    {"role": "assistant", "content": (
        "根据文档内容，该系统的主要功能包括：\n"
        "1. 智能知识问答 — 基于RAG架构，通过语义检索理解用户问题的真实意图\n"
        "2. 文档管理 — 支持上传PDF、TXT、Markdown等格式的文档\n"
        "3. 语义检索 — 使用向量相似度匹配，超越传统关键词搜索的局限\n\n"
        "以上信息来源于您上传的文档。"
    )},
    {"role": "user", "content": "如何使用这个系统？"},
    {"role": "assistant", "content": (
        "使用步骤如下：\n"
        "1. **上传文档** — 点击上传按钮，选择PDF/TXT/Markdown格式的文档\n"
        "2. **等待处理** — 系统会自动进行文本分块和向量化存储\n"
        "3. **开始问答** — 在对话框中输入问题，系统会基于文档内容生成回答\n\n"
        "提示：上传的文档越多，系统能回答的问题范围就越广。"
    )},
]


class ChatService:
    """LLM 对话服务"""

    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL
        )
        self._model = LLM_MODEL

    def _build_messages(self, context: str, question: str) -> list:
        """构建包含 Few-shot 示例的 Messages"""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT.format(context=context)}
        ]

        # 注入 Few-shot 示例
        for example in FEW_SHOT_EXAMPLES:
            messages.append(example)

        messages.append({"role": "user", "content": question})
        return messages

    async def stream_answer(
        self,
        query: str,
        context_docs: list[Document],
        conversation_history: Optional[list[dict]] = None,
    ) -> AsyncGenerator[str, None]:
        """流式生成回答，通过 SSE 逐 token 输出"""
        # 构建上下文文本
        context = self._format_context(context_docs)

        messages = self._build_messages(context, query)

        # 流式调用
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.3,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def full_answer(
        self,
        query: str,
        context_docs: list[Document],
    ) -> str:
        """非流式获取完整回答"""
        context = self._format_context(context_docs)
        messages = self._build_messages(context, query)

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.3,
            stream=False,
        )

        return response.choices[0].message.content if response.choices else ""

    @staticmethod
    def _format_context(docs: list[Document]) -> str:
        """格式化检索结果为上下文字符串"""
        parts = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source_file", "未知文档")
            page = doc.metadata.get("page", "")
            source_info = f"[来源: {source}" + (f", 第{page}页" if page else "") + "]"
            parts.append(f"--- 文档片段 {i} {source_info} ---\n{doc.page_content}")
        return "\n\n".join(parts)


# 全局单例
chat_service = ChatService()
