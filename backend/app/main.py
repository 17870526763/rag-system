"""
RAG 智能知识问答系统 — FastAPI 应用主入口
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

load_dotenv()

from app.api import documents, chat
from app.core import HOST, PORT, DEBUG


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # Startup
    print("=" * 60)
    print("  RAG 智能知识问答系统 启动中...")
    print("=" * 60)
    from app.services import vector_store
    print(f"  向量数据库已加载，当前文档数: {vector_store.doc_count}")
    print(f"  服务地址: http://{HOST}:{PORT}")
    print("=" * 60)
    yield
    # Shutdown
    print("系统关闭")


app = FastAPI(
    title="RAG 智能知识问答系统",
    description="基于 RAG（检索增强生成）架构的智能知识问答系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(documents.router)
app.include_router(chat.router)


@app.get("/api/health")
async def health_check():
    """健康检查"""
    from app.services import vector_store
    return {
        "status": "ok",
        "vector_store_docs": vector_store.doc_count,
    }


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "RAG 智能知识问答系统",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info",
    )
