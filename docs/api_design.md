# API 接口设计文档

## 通用返回格式

```json
{
  "success": true,
  "message": "操作描述",
  "data": {},
  "error": null
}
```

失败时:
```json
{
  "success": false,
  "message": "操作失败",
  "data": null,
  "error": "具体错误信息"
}
```

## 接口列表

### 1. GET /health

健康检查。

**返回**:
```json
{
  "status": "ok",
  "service": "enterprise-agent-api",
  "version": "0.2.0",
  "environment": "dev"
}
```

### 2. POST /chat

智能问答（Agentic RAG）。

**请求**:
```json
{
  "message": "如何维护HEPA滤网？",
  "conversation_id": "conv-abc123"
}
```

**返回**:
```json
{
  "success": true,
  "data": {
    "answer": "根据知识库资料，HEPA滤网需要每3个月更换...",
    "question_type": "knowledge_qa",
    "confidence": "high",
    "sources": [
      {
        "filename": "maintenance.txt",
        "chunk_id": "chunk-1",
        "score": 0.85,
        "preview": "HEPA滤网需要每3个月更换..."
      }
    ],
    "tools_used": ["rag_search"],
    "latency_ms": 125.5,
    "evidence_count": 1,
    "needs_refusal": false
  }
}
```

### 3. POST /upload

文件上传。

**请求**: multipart/form-data, field: `file`

**支持的格式**: .txt, .md, .pdf, .docx, .csv, .xlsx, .png, .jpg, .jpeg

**返回**:
```json
{
  "success": true,
  "data": {
    "filename": "guide.txt",
    "extension": ".txt",
    "size_bytes": 1234,
    "ingested": true,
    "chunk_count": 5,
    "saved_path": "data/raw_documents/guide.txt"
  }
}
```

### 4. GET /knowledge_base

知识库状态。

**返回**:
```json
{
  "success": true,
  "data": {
    "name": "enterprise_kb",
    "status": "ready",
    "document_count": 5,
    "chunk_count": 42,
    "vector_store_ready": true,
    "ingestion_enabled": true
  }
}
```

### 5. POST /knowledge_base/query

知识库检索。

**请求**:
```json
{
  "query": "电池温度管理",
  "top_k": 5
}
```

**返回**:
```json
{
  "success": true,
  "data": {
    "answer": "根据知识库...",
    "sources": [...],
    "top_k": 5,
    "confidence": "medium",
    "evidence_count": 3,
    "max_score": 0.15
  }
}
```

### 6. DELETE /knowledge_base/{doc_id}

删除知识库文档。

### 7. GET /memory

获取所有长期记忆。

### 8. DELETE /memory/{memory_id}

删除指定记忆。

### 9. POST /feedback

提交反馈。

**请求**:
```json
{
  "target": "answer-1",
  "rating": 4,
  "comment": "回答很有帮助",
  "conversation_id": "conv-abc123"
}
```

### 10. POST /report

生成报告。

**请求**:
```json
{
  "topic": "月度电池测试",
  "report_type": "battery_test",
  "month": "2026-06"
}
```
