"""
向量存储服务：Chroma 向量数据库操作
支持文档向量化存储、语义检索、混合检索（向量 + BM25）
"""
from __future__ import annotations
from typing import Optional
import os
import json

import chromadb
from langchain.vectorstores import Chroma
from openai import OpenAI
from langchain.schema import Document

from app.core import (
    LLM_API_KEY, LLM_BASE_URL, LLM_EMBEDDING_MODEL,
    CHROMA_DIR, TOP_K, RRF_K
)
from app.services.bm25_service import BM25Retriever


class VectorStore:
    """Chroma 向量存储封装"""

    def __init__(self):
        # 初始化 OpenAI 客户端用于 embedding
        self._client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL
        )
        self._embedding_model = LLM_EMBEDDING_MODEL
        self._chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self._collection = self._chroma_client.get_or_create_collection(
            name="rag_documents",
            metadata={"hnsw:space": "cosine"},
        )
        self._bm25 = BM25Retriever()
        self._doc_count = self._collection.count()

    @property
    def doc_count(self) -> int:
        return self._doc_count

    def _get_embeddings(self, texts):
        """获取文本的 embedding 向量"""
        response = self._client.embeddings.create(
            input=texts,
            model=self._embedding_model
        )
        return [data.embedding for data in response.data]

    def add_documents(self, documents: list[Document], doc_id: str) -> int:
        """
        添加文档到向量存储
        返回添加的 chunk 数量
        """
        if not documents:
            return 0

        texts = [doc.page_content for doc in documents]
        metadatas = []
        for doc in documents:
            meta = doc.metadata.copy()
            meta["doc_id"] = doc_id
            metadatas.append(meta)
        ids = [f"{doc_id}_{i}" for i in range(len(texts))]

        # 获取 embeddings
        embeddings = self._get_embeddings(texts)

        # Chroma 批量添加（自动分批，每批最多 ~41665）
        batch_size = 500
        for i in range(0, len(texts), batch_size):
            self._collection.add(
                embeddings=embeddings[i:i + batch_size],
                documents=texts[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size],
                ids=ids[i:i + batch_size],
            )

        # 更新 BM25 索引
        self._bm25.add_documents(texts, ids, metadatas)
        self._doc_count = self._collection.count()
        return len(texts)

    def search(
        self,
        query: str,
        top_k: int = TOP_K,
        doc_ids: Optional[list[str]] = None,
    ) -> list[tuple[Document, float]]:
        """
        混合检索：向量相似度 + BM25 关键词，通过 RRF 融合排序
        """
        # 向量检索
        vector_results = self._vector_search(query, top_k * 2, doc_ids)

        # BM25 检索
        bm25_results = self._bm25_search(query, top_k * 2, doc_ids)

        # RRF (Reciprocal Rank Fusion) 融合
        return self._rrf_fusion(vector_results, bm25_results, top_k)

    def _vector_search(
        self,
        query: str,
        n_results: int,
        doc_ids: Optional[list[str]] = None,
    ) -> list[tuple[Document, float]]:
        """向量相似度检索"""
        where_filter = None
        if doc_ids:
            where_filter = {"doc_id": {"$in": doc_ids}}

        # 获取查询的 embedding
        query_embedding = self._get_embeddings([query])[0]

        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, self._doc_count or n_results),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        docs = []
        if result["documents"] and result["documents"][0]:
            for i, text in enumerate(result["documents"][0]):
                meta = result["metadatas"][0][i] if result["metadatas"] else {}
                distance = result["distances"][0][i] if result["distances"] else 1.0
                # Chroma 返回 cosine distance [0, 2]，转换为相似度分数 [0, 1]
                score = 1.0 - (distance / 2.0)
                docs.append((Document(page_content=text, metadata=meta), score))
        return docs

    def _bm25_search(
        self,
        query: str,
        n_results: int,
        doc_ids: Optional[list[str]] = None,
    ) -> list[tuple[Document, float]]:
        """BM25 关键词检索"""
        return self._bm25.search(query, n_results, doc_ids)

    @staticmethod
    def _rrf_fusion(
        vector_results: list[tuple[Document, float]],
        bm25_results: list[tuple[Document, float]],
        top_k: int,
        k: int = RRF_K,
    ) -> list[tuple[Document, float]]:
        """
        RRF (Reciprocal Rank Fusion) 融合排序
        RRF(d) = sum(1 / (k + rank_r(d))) for each rank r
        """
        scores: dict[str, tuple[Document, float]] = {}

        for rank, (doc, _) in enumerate(vector_results, 1):
            key = doc.page_content[:200]  # 使用内容前200字符作为唯一标识
            if key not in scores:
                scores[key] = (doc, 0.0)
            scores[key] = (doc, scores[key][1] + 1.0 / (k + rank))

        for rank, (doc, _) in enumerate(bm25_results, 1):
            key = doc.page_content[:200]
            if key not in scores:
                scores[key] = (doc, 0.0)
            scores[key] = (doc, scores[key][1] + 1.0 / (k + rank))

        # 按 RRF 分数降序排列，取 Top-K
        sorted_docs = sorted(scores.values(), key=lambda x: x[1], reverse=True)
        return sorted_docs[:top_k]

    def delete_by_doc_id(self, doc_id: str):
        """删除指定文档的所有向量"""
        # Chroma 支持 where 过滤删除
        self._collection.delete(where={"doc_id": doc_id})
        self._bm25.delete_by_doc_id(doc_id)
        self._doc_count = self._collection.count()

    def delete_all(self):
        """清空所有向量"""
        self._chroma_client.delete_collection("rag_documents")
        self._collection = self._chroma_client.create_collection(
            name="rag_documents",
            metadata={"hnsw:space": "cosine"},
        )
        self._bm25.clear()
        self._doc_count = 0


# 全局单例
vector_store = VectorStore()
