# RAG 智能知识问答系统

基于 RAG（检索增强生成）架构的智能知识问答系统，支持用户上传文档后进行自然语言问答，解决传统搜索无法理解语义的问题。

## 技术栈

| 层次 | 技术 |
|------|------|
| **后端框架** | FastAPI + Uvicorn |
| **RAG Pipeline** | LangChain（文档加载、分块、Embedding、LLM 调用） |
| **向量数据库** | ChromaDB（本地持久化存储） |
| **关键词检索** | BM25（rank-bm25） |
| **检索融合** | RRF（Reciprocal Rank Fusion） |
| **前端框架** | Vue 3 + Element Plus |
| **构建工具** | Vite |
| **流式输出** | SSE（Server-Sent Events） |
| **LLM 支持** | 通义千问（DashScope）/ OpenAI / 任意 OpenAI 兼容 API |

## 功能特性

- **多格式文档支持** — PDF、TXT、Markdown、DOCX
- **混合检索** — 向量相似度 + BM25 关键词双路召回，RRF 融合排序
- **流式输出** — SSE 逐 token 输出，实时打字机效果
- **对话管理** — 多轮会话、历史记录、上下文保留
- **来源溯源** — 回答附带检索来源与相关性分数
- **Markdown 渲染** — 支持代码块、表格、列表等富文本格式

## 项目结构

```
rag-system/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI 路由
│   │   │   ├── documents.py  # 文档管理 API
│   │   │   └── chat.py       # 聊天问答 API
│   │   ├── core/             # 配置与全局状态
│   │   │   └── __init__.py   # 全局配置（LLM/RAG/Server）
│   │   ├── models/           # 内部数据模型
│   │   │   └── __init__.py   # DocumentRecord
│   │   ├── schemas/          # Pydantic 请求/响应模型
│   │   │   └── __init__.py   # ChatRequest, ChatResponse 等
│   │   ├── services/         # 业务逻辑服务
│   │   │   ├── document_service.py  # 文档处理
│   │   │   ├── vector_store.py      # 向量存储与混合检索
│   │   │   ├── bm25_service.py       # BM25 关键词检索
│   │   │   ├── chat_service.py       # LLM 问答服务
│   │   │   └── conversation_service.py # 对话管理
│   │   └── main.py           # FastAPI 应用入口
│   ├── requirements.txt      # Python 依赖
│   └── .env.example          # 环境变量模板
├── frontend/
│   ├── src/
│   │   ├── api/              # Axios API 封装
│   │   ├── router/           # Vue Router 配置
│   │   ├── App.vue           # 主界面组件
│   │   └── main.js           # 入口
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- LLM API Key（通义千问 DashScope 或 OpenAI）

### 后端启动

```bash
cd rag-system/backend

# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key

# 4. 启动服务
python -m app.main
```

后端将运行在 `http://localhost:8000`，API 文档访问 `http://localhost:8000/docs`。

### 前端启动

```bash
cd rag-system/frontend

# 1. 安装依赖
npm install

# 2. 启动开发服务器
npm run dev
```

前端将运行在 `http://localhost:3000`，自动代理 `/api` 请求到后端。

## 配置说明

### 环境变量（`.env`）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | LLM API 密钥 | **必填** |
| `LLM_BASE_URL` | API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_MODEL` | 对话模型 | `qwen-turbo` |
| `LLM_EMBEDDING_MODEL` | 向量模型 | `text-embedding-v3` |
| `CHUNK_SIZE` | 文本分块大小 | `500` |
| `CHUNK_OVERLAP` | 分块重叠大小 | `50` |
| `TOP_K` | 检索返回数量 | `5` |
| `RRF_K` | RRF 融合参数 | `60` |

### 切换为 OpenAI

将 `.env` 中的配置修改为：

```
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_EMBEDDING_MODEL=text-embedding-ada-002
```

## API 接口

### 文档管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/documents/upload` | 上传文档并处理 |
| `GET` | `/api/documents/list` | 文档列表 |
| `DELETE` | `/api/documents/{doc_id}` | 删除文档 |
| `DELETE` | `/api/documents/all` | 清空所有文档 |

### 聊天问答

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat/stream` | 流式问答（SSE） |
| `POST` | `/api/chat/query` | 非流式问答 |
| `GET` | `/api/chat/conversations` | 对话列表 |
| `GET` | `/api/chat/conversations/{id}` | 对话详情 |
| `DELETE` | `/api/chat/conversations/{id}` | 删除对话 |

### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/health` | 服务状态 |

## 架构说明

```
用户上传文档
    ↓
DocumentService（解析 → 分块 → 元数据管理）
    ↓
    ├──→ VectorStore（Chroma 向量化存储）
    └──→ BM25Retriever（关键词索引）
              ↓
         用户提问
              ↓
    VectorStore.search() — 双路召回
    ├── 向量相似度检索（cosine）
    └── BM25 关键词检索
              ↓
    RRF (Reciprocal Rank Fusion) 融合排序
              ↓
    ChatService（Prompt 构建 → LLM 流式调用）
              ↓
    SSE 流式输出 → 前端展示
```

## 性能指标

- 问答响应时间 < 3 秒（流式首 token < 1 秒）
- Top-1 检索准确率 > 85%
- 支持文档格式：PDF / TXT / Markdown / DOCX
- 文本分块：递归字符分割，500 tokens/chunk，50 overlap