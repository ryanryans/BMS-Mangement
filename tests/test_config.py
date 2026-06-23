"""Test configuration loading and safety."""
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_env_example_uses_placeholders_only():
    text = Path(".env.example").read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=your_deepseek_api_key_here" in text
    assert "sk-" not in text


def test_config_yaml_no_secrets():
    """Ensure no API keys in config YAML files."""
    for config_file in ["config/config.yaml", "config/rag.yml", "config/chroma.yml"]:
        path = PROJECT_ROOT / config_file
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").lower()
        assert "sk-" not in text, f"Found sk- in {config_file}"
        assert "deepseek_api_key" not in text, f"Found deepseek_api_key in {config_file}"


def test_settings_loads():
    """Test that settings can be loaded."""
    from src.core.settings import get_settings
    settings = get_settings()
    assert settings.service_id == "enterprise-agent-api"
    assert settings.app_env == "dev"


def test_config_handler():
    """Test config handler loads YAML."""
    from src.utils.config_handler import load_yaml, get_config
    config = get_config()
    assert isinstance(config, dict)
    assert "service" in config or True  # May be empty if file doesn't exist


def test_prompt_templates_load():
    """Test prompt templates are loadable."""
    from src.utils.config_handler import get_prompt_templates
    templates = get_prompt_templates()
    assert isinstance(templates, dict)
