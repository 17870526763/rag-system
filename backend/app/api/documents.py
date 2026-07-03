"""
文档管理 API：上传、列表、删除
"""
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.schemas import DocumentUploadResponse, DocumentInfo
from app.services import document_service, vector_store

router = APIRouter(prefix="/api/documents", tags=["文档管理"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    上传文档并进行向量化存储
    支持 PDF、TXT、Markdown、DOCX 格式
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    try:
        file_bytes = await file.read()

        # 保存并创建文档记录
        record, file_path = document_service.upload_document(file_bytes, file.filename)

        # 分块处理
        chunks = document_service.process_document(file_path)

        if not chunks:
            document_service.delete_document(record.doc_id)
            raise HTTPException(status_code=400, detail="文档内容为空或无法解析")

        # 向量化存储
        chunk_count = vector_store.add_documents(chunks, record.doc_id)

        # 更新分块数量
        document_service.update_chunk_count(record.doc_id, chunk_count)

        return DocumentUploadResponse(
            doc_id=record.doc_id,
            filename=record.filename,
            chunk_count=chunk_count,
            message=f"成功上传并处理 {chunk_count} 个文本块",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.get("/list", response_model=list[DocumentInfo])
async def list_documents():
    """获取已上传的文档列表"""
    docs = document_service.list_documents()
    return [
        DocumentInfo(
            doc_id=d.doc_id,
            filename=d.filename,
            upload_time=d.upload_time,
            chunk_count=d.chunk_count,
            file_size=d.file_size,
        )
        for d in docs
    ]


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """删除指定文档及其向量"""
    found = document_service.get_document(doc_id)
    if not found:
        raise HTTPException(status_code=404, detail="文档不存在")

    try:
        vector_store.delete_by_doc_id(doc_id)
        document_service.delete_document(doc_id)
        return {"message": f"文档 {found.filename} 已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.delete("/all")
async def delete_all_documents():
    """清空所有文档和向量数据"""
    try:
        vector_store.delete_all()
        for doc in document_service.list_documents():
            document_service.delete_document(doc.doc_id)
        return {"message": "所有文档数据已清空"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清空失败: {str(e)}")
