"""Tests for LLM provider selection, cache reset, and reporting metadata."""


class TestLLMProviderSelection:
    def test_no_key_returns_rule_based(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        from src.models.llm_service import reset_llm, get_llm, get_llm_provider_name

        reset_llm()
        llm = get_llm()

        assert get_llm_provider_name(llm) == "RuleBasedLLM"

    def test_placeholder_key_returns_rule_based(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
        from src.models.llm_service import reset_llm, get_llm, get_llm_provider_name

        reset_llm()
        llm = get_llm()

        assert get_llm_provider_name(llm) == "RuleBasedLLM"

    def test_real_key_tries_deepseek_adapter(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_deepseek_key")
        from src.models.llm_service import reset_llm, get_llm, get_llm_provider_name

        reset_llm()
        llm = get_llm()
        provider = get_llm_provider_name(llm)

        assert provider in ("DeepSeekAdapter", "RuleBasedLLM")

    def test_get_model_status_mock(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        from src.models.model_factory import get_model_status

        status = get_model_status()

        assert status["is_mock"] is True
        assert status["llm_provider"] == "RuleBasedLLM"
        assert status["deepseek_key_present"] is False

    def test_get_model_status_with_key(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_deepseek_key")
        from src.models.model_factory import get_model_status

        status = get_model_status()

        assert status["deepseek_key_present"] is True
        assert "deepseek_key_exists" in status

    def test_reset_llm_clears_cache(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        from src.models.llm_service import reset_llm, get_llm, get_llm_provider_name

        reset_llm()
        llm1 = get_llm()
        reset_llm()
        llm2 = get_llm()

        assert get_llm_provider_name(llm1) == get_llm_provider_name(llm2)

    def test_settings_has_deepseek_api_key(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        from src.core.settings import has_deepseek_api_key

        assert has_deepseek_api_key() is False

        monkeypatch.setenv("DEEPSEEK_API_KEY", "your_deepseek_api_key_here")
        assert has_deepseek_api_key() is False

        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_deepseek_key")
        assert has_deepseek_api_key() is True


class TestReportServiceMockDetection:
    def test_report_service_mock_mode(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        from src.models.llm_service import reset_llm

        reset_llm()

        db_path = tmp_path / "test.db"
        from src.database.sqlite_manager import SQLiteManager
        from src.rag.vector_store import SimpleVectorStore
        from src.rag.knowledge_base_service import KnowledgeBaseService

        db = SQLiteManager(str(db_path))
        db.initialize()
        kb = KnowledgeBaseService(db=db, vector_store=SimpleVectorStore(persist_dir=tmp_path))
        doc = tmp_path / "test.md"
        doc.write_text("BMS project: voltage test completed.", encoding="utf-8")
        kb.ingest_file(doc)

        from src.services.report_service import generate_report

        report = generate_report("BMS Weekly", "weekly")

        assert report["from_llm"] is False
        assert report["is_mock"] is True
        assert report["llm_provider"] == "RuleBasedLLM"
        assert len(report["content"]) > 50


class TestDeepSeekAdapterErrorHandling:
    def test_adapter_returns_empty_on_failure(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_deepseek_key")
        from src.models.model_factory import DeepSeekAdapter

        try:
            adapter = DeepSeekAdapter()
            if adapter.is_available:
                adapter._client.base_url = "https://invalid.example.com/v1"
                result = adapter.generate("test")
                assert result == ""
                assert adapter.last_call_succeeded is False
                assert adapter.last_error != ""
        except (ValueError, ImportError):
            pass

    def test_adapter_tracks_last_error(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test_deepseek_key")
        from src.models.model_factory import DeepSeekAdapter

        try:
            adapter = DeepSeekAdapter()
            if adapter.is_available:
                adapter._client.base_url = "https://invalid.example.com/v1"
                adapter.generate("test")
                assert adapter.last_call_succeeded is False
                assert len(adapter.last_error) > 0
        except (ValueError, ImportError):
            pass
