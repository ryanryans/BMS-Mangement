-- Enterprise Agentic RAG System: full database schema for SQLite

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    doc_name TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    content_type TEXT DEFAULT 'text_knowledge',
    file_path TEXT,
    file_hash TEXT,
    file_size INTEGER DEFAULT 0,
    summary TEXT,
    upload_time TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    content TEXT NOT NULL,
    content_type TEXT DEFAULT 'text',
    page INTEGER DEFAULT 0,
    section TEXT,
    metadata_json TEXT DEFAULT '{}',
    embedding_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    user_id TEXT DEFAULT 'anonymous',
    question TEXT NOT NULL,
    answer TEXT,
    used_docs_json TEXT DEFAULT '[]',
    used_tools_json TEXT DEFAULT '[]',
    latency_ms INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memories (
    memory_id TEXT PRIMARY KEY,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    importance INTEGER DEFAULT 3,
    source TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feedback (
    feedback_id TEXT PRIMARY KEY,
    conversation_id TEXT,
    feedback_type TEXT DEFAULT 'rating',
    comment TEXT,
    corrected_answer TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tool_logs (
    tool_call_id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    input_json TEXT DEFAULT '{}',
    output_json TEXT DEFAULT '{}',
    status TEXT DEFAULT 'success',
    latency_ms INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS error_cases (
    case_id TEXT PRIMARY KEY,
    question TEXT,
    wrong_answer TEXT,
    error_type TEXT DEFAULT 'unknown',
    correction TEXT,
    fix_strategy TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_enabled ON memories(enabled);
CREATE INDEX IF NOT EXISTS idx_feedback_conversation_id ON feedback(conversation_id);
CREATE INDEX IF NOT EXISTS idx_tool_logs_tool_name ON tool_logs(tool_name);
