<template>
  <el-container class="app-container">
    <!-- 侧边栏：文档管理 -->
    <el-aside width="300px" class="sidebar">
      <div class="sidebar-header">
        <h2>📚 RAG 知识问答</h2>
      </div>

      <!-- 文档上传 -->
      <div class="sidebar-section">
        <h3>📄 文档管理</h3>
        <el-upload
          class="upload-area"
          drag
          action="/api/documents/upload"
          :show-file-list="false"
          :on-success="handleUploadSuccess"
          :on-error="handleUploadError"
          :before-upload="beforeUpload"
          accept=".pdf,.txt,.md,.markdown,.docx"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">拖拽或 <em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">支持 PDF / TXT / Markdown / DOCX</div>
          </template>
        </el-upload>

        <!-- 文档列表 -->
        <div class="document-list">
          <div v-if="documents.length === 0" class="empty-hint">
            暂无文档，请先上传
          </div>
          <div
            v-for="doc in documents"
            :key="doc.doc_id"
            class="document-item"
            :class="{ active: selectedDocs.includes(doc.doc_id) }"
            @click="toggleDoc(doc.doc_id)"
          >
            <el-icon class="doc-icon"><Document /></el-icon>
            <div class="doc-info">
              <span class="doc-name" :title="doc.filename">{{ doc.filename }}</span>
              <span class="doc-meta">{{ doc.chunk_count }} 块 · {{ formatDate(doc.upload_time) }}</span>
            </div>
            <el-button
              type="danger"
              :icon="Delete"
              size="small"
              text
              @click.stop="deleteDoc(doc.doc_id)"
            />
          </div>
        </div>
      </div>

      <!-- 对话历史 -->
      <div class="sidebar-section">
        <h3>💬 对话历史</h3>
        <el-button type="primary" class="new-chat-btn" @click="newConversation">
          <el-icon><Plus /></el-icon> 新对话
        </el-button>
        <div class="conversation-list">
          <div
            v-for="conv in conversations"
            :key="conv.conversation_id"
            class="conversation-item"
            :class="{ active: currentConversationId === conv.conversation_id }"
            @click="selectConversation(conv.conversation_id)"
          >
            <span class="conv-preview">{{ conv.preview || '新对话' }}</span>
          </div>
        </div>
      </div>
    </el-aside>

    <!-- 主内容区：聊天 -->
    <el-main class="chat-main">
      <!-- 消息列表 -->
      <div class="messages-container" ref="messagesContainer">
        <div v-if="messages.length === 0" class="welcome-screen">
          <div class="welcome-icon">🤖</div>
          <h1>RAG 智能知识问答系统</h1>
          <p>上传文档后，开始自然语言问答</p>
          <div class="tips">
            <el-tag size="small" type="info">语义检索</el-tag>
            <el-tag size="small" type="info">流式输出</el-tag>
            <el-tag size="small" type="info">混合检索</el-tag>
            <el-tag size="small" type="info">多格式文档</el-tag>
          </div>
        </div>

        <div
          v-for="(msg, index) in messages"
          :key="index"
          class="message"
          :class="msg.role"
        >
          <div class="message-avatar">
            {{ msg.role === 'user' ? '👤' : '🤖' }}
          </div>
          <div class="message-content">
            <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
            <div v-if="msg.sources && msg.sources.length" class="message-sources">
              <span class="source-label">📎 参考来源：</span>
              <el-tag
                v-for="(src, i) in msg.sources"
                :key="i"
                size="small"
                type="success"
                class="source-tag"
              >
                {{ src.source }} ({{ src.score }})
              </el-tag>
            </div>
          </div>
        </div>

        <!-- 加载动画 -->
        <div v-if="isStreaming" class="message assistant streaming">
          <div class="message-avatar">🤖</div>
          <div class="message-content">
            <div class="message-text">
              {{ streamingContent }}
              <span class="cursor">▌</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入框 -->
      <div class="input-area">
        <el-input
          v-model="userInput"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 4 }"
          placeholder="输入你的问题... (Shift+Enter 换行，Enter 发送)"
          @keydown="handleKeydown"
          :disabled="isStreaming"
          resize="none"
        />
        <el-button
          type="primary"
          :icon="Promotion"
          :loading="isStreaming"
          @click="sendMessage"
          :disabled="!userInput.trim() || isStreaming"
          circle
          class="send-btn"
        />
      </div>
    </el-main>
  </el-container>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Document, Delete, Plus, Promotion } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import { api } from './api'

const md = new MarkdownIt({ breaks: true })

// State
const documents = ref([])
const conversations = ref([])
const messages = ref([])
const userInput = ref('')
const isStreaming = ref(false)
const streamingContent = ref('')
const currentConversationId = ref(null)
const selectedDocs = ref([])
const messagesContainer = ref(null)

// Lifecycle
onMounted(async () => {
  await loadDocuments()
  await loadConversations()
})

// Scroll to bottom
async function scrollToBottom() {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

watch(messages, () => scrollToBottom(), { deep: true })
watch(streamingContent, () => scrollToBottom())

// API calls
async function loadDocuments() {
  try {
    const res = await api.get('/api/documents/list')
    documents.value = res.data
  } catch (e) {
    console.error('加载文档失败', e)
  }
}

async function loadConversations() {
  try {
    const res = await api.get('/api/chat/conversations')
    conversations.value = res.data
  } catch (e) {
    console.error('加载对话失败', e)
  }
}

// Upload handlers
function beforeUpload(file) {
  const allowed = ['.pdf', '.txt', '.md', '.markdown', '.docx']
  const ext = '.' + file.name.split('.').pop().toLowerCase()
  if (!allowed.includes(ext)) {
    ElMessage.error(`不支持的文件类型: ${ext}`)
    return false
  }
  return true
}

function handleUploadSuccess(res) {
  ElMessage.success(`✅ ${res.message}`)
  loadDocuments()
}

function handleUploadError() {
  ElMessage.error('❌ 上传失败，请重试')
}

// Document actions
async function deleteDoc(docId) {
  try {
    await ElMessageBox.confirm('确定删除此文档？', '确认', { type: 'warning' })
    await api.delete(`/api/documents/${docId}`)
    selectedDocs.value = selectedDocs.value.filter(id => id !== docId)
    ElMessage.success('已删除')
    loadDocuments()
  } catch (e) {
    if (e !== 'cancel') console.error('删除失败', e)
  }
}

function toggleDoc(docId) {
  const idx = selectedDocs.value.indexOf(docId)
  if (idx >= 0) {
    selectedDocs.value.splice(idx, 1)
  } else {
    selectedDocs.value.push(docId)
  }
}

// Conversation actions
function newConversation() {
  messages.value = []
  currentConversationId.value = null
  streamingContent.value = ''
}

async function selectConversation(convId) {
  try {
    const res = await api.get(`/api/chat/conversations/${convId}`)
    currentConversationId.value = convId
    messages.value = res.data.messages.map(m => ({
      role: m.role,
      content: m.content,
    }))
  } catch (e) {
    ElMessage.error('加载对话失败')
  }
}

// Chat
async function sendMessage() {
  const text = userInput.value.trim()
  if (!text || isStreaming.value) return

  // 添加用户消息
  messages.value.push({ role: 'user', content: text })
  userInput.value = ''
  isStreaming.value = true
  streamingContent.value = ''

  try {
    // 建立 SSE 连接
    const params = new URLSearchParams({
      query: text,
      conversation_id: currentConversationId.value || '',
    })
    if (selectedDocs.value.length > 0) {
      selectedDocs.value.forEach(id => params.append('doc_ids', id))
    }

    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: text,
        conversation_id: currentConversationId.value || undefined,
        doc_ids: selectedDocs.value.length > 0 ? selectedDocs.value : undefined,
      }),
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentEvent = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        // 处理 event: 行
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
          continue
        }
        // 处理 data: 行
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.content) {
              streamingContent.value += data.content
            }
            if (data.is_end) {
              if (data.conversation_id) {
                currentConversationId.value = data.conversation_id
              }
              // 将完整回答添加到消息列表
              messages.value.push({
                role: 'assistant',
                content: streamingContent.value,
                sources: data.sources || [],
              })
              streamingContent.value = ''
              loadConversations()
            }
          } catch (e) {
            // 忽略 SSE 非 JSON 数据行
          }
        }
        // 空行：重置当前事件
        if (line.trim() === '') {
          currentEvent = ''
        }
      }
    }
  } catch (e) {
    ElMessage.error('请求失败: ' + e.message)
    messages.value.push({
      role: 'assistant',
      content: '❌ 请求失败，请检查网络连接后重试',
    })
  } finally {
    isStreaming.value = false
  }
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

function renderMarkdown(text) {
  return md.render(text)
}

function formatDate(dateStr) {
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.app-container {
  height: 100vh;
}

/* Sidebar */
.sidebar {
  background: #1a1a2e;
  color: #eee;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}

.sidebar-header h2 {
  font-size: 18px;
  color: #fff;
}

.sidebar-section {
  padding: 16px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}

.sidebar-section h3 {
  font-size: 14px;
  color: #aaa;
  margin-bottom: 12px;
}

/* Upload */
.upload-area { margin-bottom: 12px; }
.upload-area .el-upload { width: 100%; }
.upload-area .el-upload-dragger {
  padding: 16px;
  background: rgba(255,255,255,0.05);
  border-color: rgba(255,255,255,0.15);
}
.upload-area .el-upload__text { color: #aaa; font-size: 13px; }
.upload-area .el-upload__text em { color: #409eff; font-style: normal; }
.upload-area .el-upload__tip { color: #666; font-size: 12px; margin-top: 4px; }
.upload-area .el-icon--upload { color: #409eff; font-size: 28px; }

/* Document list */
.document-list { max-height: 200px; overflow-y: auto; }
.document-item {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  margin-bottom: 4px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
  font-size: 13px;
}
.document-item:hover { background: rgba(255,255,255,0.08); }
.document-item.active { background: rgba(64,158,255,0.2); }
.doc-icon { margin-right: 8px; color: #409eff; }
.doc-info { flex: 1; min-width: 0; }
.doc-name { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-meta { display: block; font-size: 11px; color: #888; }
.empty-hint { color: #666; font-size: 13px; text-align: center; padding: 16px; }

/* Conversation list */
.new-chat-btn { width: 100%; margin-bottom: 8px; }
.conversation-list { max-height: 150px; overflow-y: auto; }
.conversation-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conversation-item:hover { background: rgba(255,255,255,0.08); }
.conversation-item.active { background: rgba(64,158,255,0.2); }
.conv-preview { color: #ccc; }

/* Chat main */
.chat-main {
  display: flex;
  flex-direction: column;
  padding: 0;
  background: #f5f5f5;
}

/* Messages */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.welcome-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
}
.welcome-icon { font-size: 64px; margin-bottom: 16px; }
.welcome-screen h1 { font-size: 24px; color: #333; margin-bottom: 8px; }
.welcome-screen p { font-size: 14px; margin-bottom: 16px; }
.tips { display: flex; gap: 8px; }

.message {
  display: flex;
  margin-bottom: 16px;
  max-width: 800px;
  margin-left: auto;
  margin-right: auto;
}
.message.user { flex-direction: row-reverse; }
.message-avatar { font-size: 32px; flex-shrink: 0; }
.message-content {
  margin: 0 12px;
  max-width: 70%;
}
.message-text {
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}
.message.user .message-text {
  background: #409eff;
  color: white;
  border-bottom-right-radius: 4px;
}
.message.assistant .message-text {
  background: white;
  color: #333;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.message-sources { margin-top: 8px; font-size: 12px; }
.source-label { color: #999; margin-right: 4px; }
.source-tag { margin-right: 4px; }

.cursor { animation: blink 1s infinite; color: #409eff; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

/* Input */
.input-area {
  display: flex;
  align-items: flex-end;
  padding: 16px 20px;
  background: white;
  border-top: 1px solid #eee;
  gap: 12px;
}
.input-area .el-textarea { flex: 1; }
.input-area .el-textarea__inner {
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 14px;
  border: 1px solid #ddd;
}
.input-area .el-textarea__inner:focus { border-color: #409eff; }
.send-btn { flex-shrink: 0; width: 40px; height: 40px; }

/* Markdown rendering */
.message-text :deep(p) { margin: 4px 0; }
.message-text :deep(ul), .message-text :deep(ol) { margin: 4px 0; padding-left: 20px; }
.message-text :deep(code) {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}
.message-text :deep(pre) {
  background: #282c34;
  color: #abb2bf;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}
.message-text :deep(pre code) { background: none; color: inherit; padding: 0; }
.message-text :deep(blockquote) {
  border-left: 3px solid #409eff;
  padding-left: 12px;
  color: #666;
  margin: 8px 0;
}
.message-text :deep(table) { border-collapse: collapse; margin: 8px 0; width: 100%; }
.message-text :deep(th), .message-text :deep(td) {
  border: 1px solid #ddd;
  padding: 6px 10px;
  font-size: 13px;
}
.message-text :deep(th) { background: #f5f5f5; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #ccc; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #999; }
</style>
