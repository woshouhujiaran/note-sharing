# FOLIO AI BFF

独立的 AI BFF 与 Agent 运行时。

## 目标

- 只通过 Login_api 的公开接口读取内容
- 对外提供稳定的 AI 聊天、关键词抽取、相似问题提示
- 为 `Login_ui` 的 iframe 壳提供宿主页面

## 环境变量

- `AI_LOGIN_API_BASE_URL`：默认 `http://localhost:8080`
- `AI_MODEL_PROVIDER`：默认 `openai_compatible`
- `AI_MODEL_BASE_URL`：默认 `https://ark.cn-beijing.volces.com/api/coding/v3`
- `AI_MODEL_API_KEY`：默认留空，接入时填你的 API Key
- `AI_MODEL_NAME`：默认留空，填写你要使用的模型名
- `AI_MODEL_TEMPERATURE`：默认 `0.3`
- `AI_MODEL_MAX_TOKENS`：默认 `1200`
- `AI_MODEL_TIMEOUT`：默认 `30`
- `AI_BFF_HOST`：默认 `0.0.0.0`
- `AI_BFF_PORT`：默认 `8000`
- `AI_JWT_SECRET`：可选，用于验证 HS256 JWT
- `AI_ALLOWED_ORIGINS`：逗号分隔的前端来源

## 火山方舟接入示例

```env
AI_MODEL_PROVIDER=openai_compatible
AI_MODEL_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3
AI_MODEL_API_KEY=
AI_MODEL_NAME=
AI_MODEL_TEMPERATURE=0.3
AI_MODEL_MAX_TOKENS=1200
AI_MODEL_TIMEOUT=30
```

## 启动

```bash
pip install -r ai_bff/requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
