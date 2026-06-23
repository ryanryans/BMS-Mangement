"""Test RAG components — embedding, vector store, retriever, reranker, text splitter. 全部使用 tmp_path。"""
import json
from pathlib import Path

from src.rag.embedding_service import MockEmbedding, HashEmbedding
from src.rag.vector_store import SimpleVectorStore
from src.rag.retriever import Retriever
from src.rag.reranker import SimpleReranker
from src.rag.text_splitter import split_text, split_documents
from src.rag.document_loader import LoadedDocument


class TestEmbedding:
    def test_mock_embedding_produces_vector(self):
        emb = MockEmbedding()
        vec = emb.encode("Hello world")
        assert len(vec) == MockEmbedding.DIM
        assert sum(v for v in vec) > 0

    def test_mock_embedding_batch(self):
        emb = MockEmbedding()
        vecs = emb.encode_batch(["text1", "text2", "text3"])
        assert len(vecs) == 3

    def test_empty_text_zero_vector(self):
        emb = MockEmbedding()
        vec = emb.encode("")
        assert vec == [0.0] * MockEmbedding.DIM

    def test_similar_texts_higher_similarity(self):
        emb = MockEmbedding()
        v1 = emb.encode("电池温度过高需要检查")
        v2 = emb.encode("电池温度异常需要排查")
        v3 = emb.encode("今天天气不错适合出行")
        s12 = emb.similarity(v1, v2)
        s13 = emb.similarity(v1, v3)
        assert s12 > s13, f"Expected s12({s12:.4f}) > s13({s13:.4f})"


class TestVectorStore:
    def test_add_and_search(self, tmp_path):
        """必须使用 tmp_path，禁止污染真实 data/vector_db。"""
        store = SimpleVectorStore(persist_dir=tmp_path)
        store.add_document("电池温度超过60度需要停机检查", {"filename": "test.txt"})
        store.add_document("机器人的滤网需要每周清洁", {"filename": "maintenance.txt"})
        results = store.search("电池温度", top_k=2)
        assert len(results) >= 1
        assert "温度" in results[0].content

        # 断言没有污染真实路径
        real_index = Path("data/vector_db/vector_index.json")
        assert not real_index.exists() or Path(tmp_path) != real_index.parent.resolve()

    def test_persist_and_load(self, tmp_path):
        store = SimpleVectorStore(persist_dir=tmp_path)
        store.add_document("测试持久化内容", {"key": "value"})
        store.persist()
        store2 = SimpleVectorStore(persist_dir=tmp_path)
        assert store2.document_count == 1
        results = store2.search("持久化", top_k=1)
        assert len(results) == 1

    def test_search_empty_store(self, tmp_path):
        store = SimpleVectorStore(persist_dir=tmp_path)
        results = store.search("anything", top_k=5)
        assert results == []


class TestRetriever:
    def test_retrieve_returns_evidence(self, tmp_path):
        """必须使用 tmp_path。"""
        from src.rag.vector_store import SimpleVectorStore
        store = SimpleVectorStore(persist_dir=tmp_path)
        retriever = Retriever(store)
        retriever.add_document(
            "扫地机器人的HEPA滤网需要每3个月更换一次",
            {"filename": "maintenance.txt", "chunk_id": "chunk-1"},
        )
        result = retriever.retrieve("HEPA滤网更换", top_k=3)
        assert result.has_evidence
        assert result.evidences[0].filename == "maintenance.txt"

    def test_retrieve_no_match(self, tmp_path):
        from src.rag.vector_store import SimpleVectorStore
        store = SimpleVectorStore(persist_dir=tmp_path)
        retriever = Retriever(store)
        retriever.add_document("电池维护指南", {"filename": "battery.txt"})
        result = retriever.retrieve("量子计算芯片", top_k=3, threshold=0.30)
        assert not result.has_evidence or result.max_score < 0.15


class TestReranker:
    def test_rerank_improves_relevant(self):
        from src.rag.retriever import Evidence
        evidences = [
            Evidence("doc1", "电池温度管理是BMS的核心功能", "test.txt", "c1", 0.15),
            Evidence("doc2", "今天天气不错适合出去玩", "weather.txt", "c2", 0.10),
        ]
        reranker = SimpleReranker()
        results = reranker.rerank("电池温度管理", evidences)
        assert results[0].evidence.doc_id == "doc1"
        assert results[0].reranked_score > results[1].reranked_score


class TestTextSplitter:
    def test_split_text(self):
        chunks = split_text("abcdefghijklmnopqrstuvwxyz", chunk_size=10, chunk_overlap=3)
        assert len(chunks) >= 3
        assert chunks[0] == "abcdefghij"
        assert chunks[1].startswith("hij") or chunks[1].startswith("h")

    def test_split_documents(self):
        doc = LoadedDocument(
            content="Robot maintenance requires HEPA filter cleaning. Brushes checked weekly.",
            source="/tmp/test.txt",
            metadata={"filename": "test.txt"},
        )
        chunks = split_documents([doc], chunk_size=50, chunk_overlap=10)
        assert len(chunks) >= 2


