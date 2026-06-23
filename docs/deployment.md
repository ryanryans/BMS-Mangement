# 閮ㄧ讲鏂囨。

## 鏈湴寮€鍙戣繍琛?
### 鐜瑕佹眰

- Python 3.10+
- pip

### 瀹夎姝ラ

```powershell
# 1. 鍏嬮殕椤圭洰
cd "椤圭洰鐩綍"

# 2. 鍒涘缓铏氭嫙鐜
python -m venv venv

# 3. 婵€娲昏櫄鎷熺幆澧?venv\Scripts\Activate.ps1

# 4. 瀹夎渚濊禆
pip install -r requirements.txt

# 5. 閰嶇疆鐜鍙橀噺
Copy-Item .env.example .env
# 缂栬緫 .env锛岃缃?DEEPSEEK_API_KEY锛堝彲閫夛紝涓嶈缃垯浣跨敤 MockModel锛?
# 6. 杩愯娴嬭瘯
python -m pytest -q

# 7. 鍚姩 FastAPI
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 8. 鍚姩 Streamlit Demo锛堝彟涓€涓粓绔級
streamlit run app.py
```

### 璁块棶鍦板潃

- FastAPI Swagger 鏂囨。: http://127.0.0.1:8000/docs
- FastAPI 鍋ュ悍妫€鏌? http://127.0.0.1:8000/health
- Streamlit Demo: http://127.0.0.1:8501

### 鏃?API Key 杩愯

椤圭洰榛樿浣跨敤 MockModel / RuleBasedLLM锛屾棤闇€浠讳綍 API Key 鍗冲彲杩愯瀹屾暣娴佺▼銆?
閰嶇疆鐪熷疄 LLM 鍙渶鍦?`.env` 涓缃?
```
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

绯荤粺浼氳嚜鍔ㄥ垏鎹㈠埌 DeepSeek API銆?
## Docker 閮ㄧ讲

### 鏋勫缓鍜岃繍琛?
```powershell
# 鏋勫缓闀滃儚
docker build -t enterprise-agent-api .

# 杩愯
docker-compose up -d
```

### Docker Compose 閰嶇疆

```yaml
services:
  api:
    build: .
    env_file:
      - .env
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
```

## 鐢熶骇閮ㄧ讲寤鸿

### 鏋舵瀯

```
Nginx (鍙嶅悜浠ｇ悊 + HTTPS)
  鈹溾攢鈹€ FastAPI (uvicorn + gunicorn)
  鈹?  鈹斺攢鈹€ src/
  鈹溾攢鈹€ SQLite / PostgreSQL
  鈹溾攢鈹€ ChromaDB (鍚戦噺鏁版嵁搴?
  鈹斺攢鈹€ 鏂囦欢瀛樺偍
```

### 鐜鍙橀噺

| 鍙橀噺 | 璇存槑 | 榛樿鍊?|
|------|------|--------|
| APP_ENV | 杩愯鐜 | dev |
| LOG_LEVEL | 鏃ュ織绾у埆 | INFO |
| SQLITE_DB_PATH | 鏁版嵁搴撹矾寰?| data/app.db |
| DEEPSEEK_API_KEY | DeepSeek API瀵嗛挜 | - |
| DEEPSEEK_BASE_URL | API鍦板潃 | https://api.deepseek.com |
| CHAT_MODEL_NAME | 妯″瀷鍚嶇О | deepseek-chat |

### Nginx 閰嶇疆绀轰緥

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

