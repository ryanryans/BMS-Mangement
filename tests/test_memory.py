"""Test memory module: store, extract, retrieve, manage."""
import tempfile
from pathlib import Path

# Override settings for testing
import os
os.environ["SQLITE_DB_PATH"] = "data/test_memory.db"


class TestMemoryStore:
    def test_save_and_list(self):
        from src.memory.memory_store import MemoryStore
        store = MemoryStore()

        mid = store.save("user_preference", "喜欢简短的回答", importance=4)
        assert mid.startswith("mem-")

        items = store.list("user_preference")
        assert len(items) >= 1
        assert any("简短" in i.content for i in items)

    def test_search(self):
        from src.memory.memory_store import MemoryStore
        store = MemoryStore()

        store.save("user_preference", "偏好电池测试报告", importance=5)
        store.save("project_context", "项目A使用三元锂电池", importance=4)

        results = store.search("电池")
        assert len(results) >= 2

    def test_disable(self):
        from src.memory.memory_store import MemoryStore
        store = MemoryStore()

        mid = store.save("task_history", "完成电池循环测试", importance=3)
        assert store.disable(mid) is True

    def test_delete(self):
        from src.memory.memory_store import MemoryStore
        store = MemoryStore()

        mid = store.save("feedback_memory", "用户对温度分析满意", importance=3)
        assert store.delete(mid) is True


class TestMemoryExtractor:
    def test_extract_preferences(self):
        from src.memory.memory_extractor import MemoryExtractor
        extractor = MemoryExtractor()

        candidates = extractor.extract_candidates(
            "我喜欢每天上午查看电池测试报告",
            "好的，我会记住你的偏好。",
        )
        assert len(candidates) >= 1
        assert candidates[0].memory_type == "user_preference"

    def test_extract_project_context(self):
        from src.memory.memory_extractor import MemoryExtractor
        extractor = MemoryExtractor()

        candidates = extractor.extract_candidates(
            "电池项目BMS版本3.2的测试什么时候完成？",
            "BMS版本3.2测试预计下周完成。",
        )
        assert len(candidates) >= 1
        assert candidates[0].memory_type == "project_context"

    def test_extract_no_match(self):
        from src.memory.memory_extractor import MemoryExtractor
        extractor = MemoryExtractor()

        candidates = extractor.extract_candidates(
            "今天天气怎么样？",
            "今天是晴天。",
        )
        assert len(candidates) == 0  # No relevant keywords


class TestMemoryManager:
    def test_process_conversation(self):
        from src.memory.memory_manager import MemoryManager
        manager = MemoryManager()

        ids = manager.process_conversation(
            "我需要每周收到电池状态报告",
            "好的，我会每周生成电池状态报告。",
        )
        # May or may not save depending on keywords
        assert isinstance(ids, list)

    def test_context_for_query(self):
        from src.memory.memory_manager import MemoryManager
        manager = MemoryManager()

        ctx = manager.get_context_for_query("电池测试")
        assert "relevant_memories" in ctx
        assert "user_preferences" in ctx
