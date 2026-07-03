"""
文档处理服务：加载、解析、分块
支持 PDF、TXT、Markdown、DOCX 多格式
"""
from __future__ import annotations
import os
import uuid
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    TextLoader,
    UnstructuredMarkdownLoader,
    PyMuPDFLoader,
    Docx2txtLoader,
)

from app.core import CHUNK_SIZE, CHUNK_OVERLAP, UPLOAD_DIR, SUPPORTED_EXTENSIONS
from app.models import DocumentRecord


class DocumentService:
    """文档管理服务"""

    # 文档元数据存储（生产环境替换为数据库）
    _metadata_file = UPLOAD_DIR / "documents.json"

    def __init__(self):
        self._documents: dict[str, DocumentRecord] = {}
        self._load_metadata()

    def _load_metadata(self):
        """加载文档元数据"""
        if self._metadata_file.exists():
            data = json.loads(self._metadata_file.read_text(encoding="utf-8"))
            for item in data:
                record = DocumentRecord(
                    doc_id=item["doc_id"],
                    filename=item["filename"],
                    upload_time=datetime.fromisoformat(item["upload_time"]),
                    chunk_count=item.get("chunk_count", 0),
                    file_size=item.get("file_size", 0),
                    file_path=item.get("file_path", ""),
                )
                self._documents[record.doc_id] = record

    def _save_metadata(self):
        """保存文档元数据"""
        data = []
        for doc in self._documents.values():
            data.append({
                "doc_id": doc.doc_id,
                "filename": doc.filename,
                "upload_time": doc.upload_time.isoformat(),
                "chunk_count": doc.chunk_count,
                "file_size": doc.file_size,
                "file_path": doc.file_path,
            })
        self._metadata_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def upload_document(self, file_bytes: bytes, filename: str) -> tuple[DocumentRecord, str]:
        """
        上传文档并返回记录和文件路径
        """
        # 检查文件类型
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的文件类型: {ext}，支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

        # 保存文件
        safe_name = f"{uuid.uuid4().hex[:12]}_{filename}"
        dest = UPLOAD_DIR / safe_name
        dest.write_bytes(file_bytes)

        # 创建记录
        record = DocumentRecord.create(
            filename=filename,
            file_path=str(dest),
            file_size=len(file_bytes),
        )
        self._documents[record.doc_id] = record
        self._save_metadata()

        return record, str(dest)

    def process_document(self, file_path: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP):
        """加载文档并进行文本分块"""
        loader = self._get_loader(file_path)
        documents = loader.load()

        # 为每个document添加来源元数据
        for doc in documents:
            doc.metadata["source_file"] = Path(file_path).name

        # 使用递归字符分割器进行分块
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", ".", "！", "!", "？", "?", "；", ";", "，", ",", " ", ""],
        )
        chunks = splitter.split_documents(documents)
        return chunks

    @staticmethod
    def _get_loader(file_path: str):
        """根据文件扩展名选择合适的文档加载器"""
        ext = Path(file_path).suffix.lower()
        loader_map = {
            ".pdf": lambda p: PyMuPDFLoader(p),
            ".txt": lambda p: TextLoader(p, encoding="utf-8"),
            ".md": lambda p: UnstructuredMarkdownLoader(p),
            ".markdown": lambda p: UnstructuredMarkdownLoader(p),
            ".docx": lambda p: Docx2txtLoader(p),
        }
        loader_cls = loader_map.get(ext)
        if loader_cls is None:
            raise ValueError(f"Unsupported file type: {ext}")
        return loader_cls(file_path)

    def get_document(self, doc_id: str) -> Optional[DocumentRecord]:
        """获取文档信息"""
        return self._documents.get(doc_id)

    def list_documents(self) -> list[DocumentRecord]:
        """列出所有文档"""
        return sorted(
            self._documents.values(),
            key=lambda d: d.upload_time,
            reverse=True,
        )

    def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        record = self._documents.pop(doc_id, None)
        if record:
            # 删除物理文件
            try:
                os.remove(record.file_path)
            except OSError:
                pass
            self._save_metadata()
            return True
        return False

    def update_chunk_count(self, doc_id: str, count: int):
        """更新文档的分块数量"""
        record = self._documents.get(doc_id)
        if record:
            record.chunk_count = count
            self._save_metadata()


# 全局单例
document_service = DocumentService()
