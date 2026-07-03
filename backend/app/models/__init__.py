"""应用内部数据模型"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class DocumentRecord:
    """文档记录"""
    doc_id: str
    filename: str
    upload_time: datetime
    chunk_count: int = 0
    file_size: int = 0
    file_path: str = ""

    @classmethod
    def create(cls, filename: str, file_path: str, file_size: int = 0) -> "DocumentRecord":
        return cls(
            doc_id=str(uuid.uuid4())[:8],
            filename=filename,
            upload_time=datetime.now(),
            file_path=file_path,
            file_size=file_size,
        )
