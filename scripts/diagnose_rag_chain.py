"""Diagnose RAG chain with Chinese battery doc. Run: python scripts/diagnose_rag_chain.py"""
import os, sys, tempfile
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(str(PROJECT_ROOT))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def main():
    print("=== RAG Chain Diagnostic ===\n")
    tmp = Path(tempfile.mkdtemp())
    os.environ['SQLITE_DB_PATH'] = str(tmp / 'test.db')
    from src.database.sqlite_manager import SQLiteManager
    from src.rag.vector_store import SimpleVectorStore
    from src.rag.knowledge_base_service import KnowledgeBaseService
    db = SQLiteManager(str(tmp / 'test.db'))
    db.initialize()
    kb = KnowledgeBaseService(db=db, vector_store=SimpleVectorStore(persist_dir=tmp))
    # Chinese battery knowledge doc
    doc = tmp / "battery_knowledge.md"
    doc.write_text(
        "低温快充可能导致负极析锂风险增加。"
        "在低温环境下，锂离子扩散能力下降，电荷转移阻抗增大，极化加剧。"
        "电池管理系统需要实时监测电池温度、电压和电流。"
        "温度超过60度时需要立即停机检查。"
        "建议在零下10度以下禁止快充，防止电池安全风险。"
        "快充过程中温度需控制在15-45度之间。"
        "电池容量衰减过快通常与高温存储和低温快充有关。",
        encoding="utf-8")
    r = kb.ingest_file(doc)
    print(f"Ingested: chunks={r.chunk_count}\n")
    queries = [
        "低温快充可能带来什么风险？",
        "低温有什么影响？",
        "电池有什么风险？",
        "价格是多少？",
    ]
    for q in queries:
        r = kb.query(q, prefer_content_type="text_knowledge")
        s = r["sources"]
        dbg = r.get("retrieval_debug", {})
        kw = dbg.get("keywords", [])
        print(f"Q: {q}")
        print(f"  evidence={r['evidence_count']} conf={r['confidence']} max_score={r['max_score']:.4f}")
        print(f"  llm_called={r['llm_called']} sources={list(set(x['filename'] for x in s))}")
        print(f"  keywords(count={len(kw)}): {kw[:10]}...")
        if s:
            for x in s:
                print(f"    [{x['filename']}] score={x['score']:.4f} | {x['preview'][:100]}")
        else:
            print(f"  (no evidence above threshold={dbg.get('threshold','?')})")
            # check if any candidate exists
            alt = kb.query(q, top_k=5)
            if alt['sources']:
                top = alt['sources'][0]
                print(f"  top candidate: [{top['filename']}] score={top['score']:.4f} (below threshold)")
            else:
                print(f"  no candidates at all")
        print(f"  answer[:200]: {r['answer'][:200]}\n")
    print("=== Done ===")
if __name__ == "__main__":
    main()
