"""M2 local RAG facade.

The package is intentionally independent from the legacy top-level `rag/`
package so FastAPI can expose deterministic local retrieval without importing
LLM globals or requiring API credentials.
"""

