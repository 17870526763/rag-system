"""
BM25 关键词检索服务
用于与向量检索进行混合检索融合（RRF）
"""
from __future__ import annotations
import re
from typing import Optional

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi


class BM25Retriever:
    """轻量级 BM25 检索器实现"""

    def __init__(self):
        self._index: Optional[BM25Okapi] = None
        self._docs: list[Document] = []
        self._doc_ids: list[str] = []  # 向量存储中的 ID
        self._texts: list[str] = []  # 原始文本内容（用于构建真实 Document）
        self._tokenized_corpus: list[list[str]] = []

    def add_documents(self, texts: list[str], ids: list[str], metadatas: Optional[list[dict]] = None):
        """添加文档到 BM25 索引"""
        for i, (text, doc_id) in enumerate(zip(texts, ids)):
            tokens = self._tokenize(text)
            self._tokenized_corpus.append(tokens)
            self._doc_ids.append(doc_id)
            self._texts.append(text)
            # 存储元数据
            metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
            doc = Document(page_content=text, metadata=metadata)
            self._docs.append(doc)

        # 重建 BM25 索引
        self._index = BM25Okapi(self._tokenized_corpus)

    def search(
        self,
        query: str,
        n_results: int = 5,
        doc_ids: Optional[list[str]] = None,
    ) -> list[tuple[Document, float]]:
        """BM25 检索，返回 (Document, score) 列表"""
        if not self._index or not self._tokenized_corpus:
            return []

        query_tokens = self._tokenize(query)
        scores = self._index.get_scores(query_tokens)

        # 构建 doc_id -> (Document, score) 的映射，保留原始 metadata
        result_map: dict[str, tuple[Document, float]] = {}
        for i, did in enumerate(self._doc_ids):
            if doc_ids and did not in doc_ids:
                continue
            if did not in result_map:
                # 获取存储的文档元数据
                doc = self._docs[i] if i < len(self._docs) else Document(page_content=self._texts[i], metadata={})
                metadata = doc.metadata.copy()
                metadata["bm25_score"] = scores[i]
                result_map[did] = (
                    Document(page_content=self._texts[i], metadata=metadata),
                    float(scores[i]),
                )

        # 按分数降序取 Top-K
        sorted_results = sorted(result_map.values(), key=lambda x: x[1], reverse=True)
        return sorted_results[:n_results]

    def delete_by_doc_id(self, doc_id: str):
        """按 doc_id 删除（重建索引）"""
        to_remove = [i for i, did in enumerate(self._doc_ids) if did.startswith(doc_id)]
        # 从后往前删，避免索引错乱
        for i in sorted(to_remove, reverse=True):
            self._tokenized_corpus.pop(i)
            self._doc_ids.pop(i)
            self._texts.pop(i)
            if i < len(self._docs):
                self._docs.pop(i)

        if self._tokenized_corpus:
            self._index = BM25Okapi(self._tokenized_corpus)
        else:
            self._index = None

    def clear(self):
        """清空索引"""
        self._index = None
        self._docs = []
        self._doc_ids = []
        self._texts = []
        self._tokenized_corpus = []

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """简单分词：支持中英文混合"""
        # 英文按空白和标点分割，中文按字符分割
        text = text.lower()
        # 匹配中文字符串和英文单词
        tokens = re.findall(r'[一-鿿]|[a-z0-9]+', text)
        return [t for t in tokens if t.strip()]
