"""Diagnose LLM config: .env, key detection, provider selection, real API test.

Usage: python scripts/diagnose_llm_config.py
"""
import os, sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(str(PROJECT_ROOT))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def main():
    print("=== LLM Configuration Diagnostic ===\n")

    # 1. .env
    env_path = PROJECT_ROOT / ".env"
    print(f"1. .env exists: {env_path.exists()}")
    if env_path.exists():
        print(f"   path: {env_path}")

    # 2. Settings
    from src.core.settings import get_settings, has_deepseek_api_key
    settings = get_settings()
    print(f"2. Settings loaded:")
    print(f"   env_exists: {settings.env_exists}")
    print(f"   env_path: {settings.env_path}")
    print(f"   deepseek_api_key_present: {settings.deepseek_api_key_present}")
    print(f"   deepseek_base_url: {settings.deepseek_base_url}")
    print(f"   chat_model_name: {settings.chat_model_name}")

    # 3. Key check (no value exposure)
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    key_exists = bool(api_key)
    is_empty = key_exists and len(api_key.strip()) == 0
    is_placeholder = "your_deepseek_api_key_here" in api_key
    print(f"\n3. DEEPSEEK_API_KEY:")
    print(f"   exists: {key_exists}")
    if key_exists:
        print(f"   empty: {is_empty}")
        print(f"   placeholder: {is_placeholder}")
        if not is_empty and not is_placeholder:
            print(f"   prefix: {api_key[:8]}... (hidden)")
            print(f"   length: {len(api_key)}")

    # 4. Model status
    from src.models.model_factory import get_model_status
    status = get_model_status()
    print(f"\n4. get_model_status():")
    for k, v in status.items():
        print(f"   {k}: {v}")

    # 5. Provider selection
    from src.models.llm_service import get_llm, get_llm_provider_name, get_llm_call_info, reset_llm
    reset_llm()
    llm = get_llm()
    provider = get_llm_provider_name(llm)
    call_info = get_llm_call_info(llm)
    print(f"\n5. Selected provider: {provider}")
    print(f"   call_info: {call_info}")

    # 6. Real API test (only if key configured)
    print(f"\n6. Real API test:")
    if has_deepseek_api_key():
        print(f"   DeepSeek key detected, attempting minimal call...")
        try:
            answer = llm.generate("请用一句话回答：RAG的核心流程是什么？")
            if hasattr(llm, 'last_call_succeeded') and llm.last_call_succeeded:
                print(f"   real_llm_called: True")
                print(f"   real_llm_success: True")
                print(f"   DeepSeek minimal call succeeded.")
                print(f"   Response[:200]: {answer[:200]}")
            else:
                print(f"   real_llm_called: True")
                print(f"   real_llm_success: False")
                error = getattr(llm, 'last_error', 'unknown')
                print(f"   error_summary: {error}")
        except Exception as e:
            print(f"   real_llm_called: True")
            print(f"   real_llm_success: False")
            print(f"   error_summary: {type(e).__name__}")
    else:
        print(f"   No real API key configured.")
        print(f"   real_llm_called: False")
        print(f"   real_llm_success: False")
        print(f"   Currently using RuleBasedLLM (mock).")

    # 7. Summary
    print(f"\n=== Summary ===")
    if has_deepseek_api_key():
        print("DeepSeek API key IS configured.")
        call_ok = hasattr(llm, 'last_call_succeeded') and llm.last_call_succeeded
        if call_ok:
            print("Real API call: SUCCESS")
        else:
            print("Real API call: FAILED (check base_url, model_name, network)")
    else:
        print("No DeepSeek API key -> MockLLM mode.")
        print("Create .env with DEEPSEEK_API_KEY=your-key to enable real LLM.")

    reset_llm()

if __name__ == "__main__":
    main()
