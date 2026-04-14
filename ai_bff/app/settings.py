from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(slots=True)
class Settings:
    login_api_base_url: str = os.getenv("AI_LOGIN_API_BASE_URL", "http://localhost:8080")
    jwt_secret: str = os.getenv("AI_JWT_SECRET", "")
    model_provider: str = os.getenv("AI_MODEL_PROVIDER", "openai_compatible")
    model_base_url: str = os.getenv("AI_MODEL_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3")
    model_api_key: str = os.getenv("AI_MODEL_API_KEY", "")
    model_name: str = os.getenv("AI_MODEL_NAME", "")
    model_temperature: float = float(os.getenv("AI_MODEL_TEMPERATURE", "0.3"))
    model_max_tokens: int = int(os.getenv("AI_MODEL_MAX_TOKENS", "1200"))
    model_timeout: float = float(os.getenv("AI_MODEL_TIMEOUT", "30"))
    host: str = os.getenv("AI_BFF_HOST", "0.0.0.0")
    port: int = int(os.getenv("AI_BFF_PORT", "8000"))
    app_name: str = os.getenv("AI_APP_NAME", "folio-ai-bff")
    allowed_origins: list[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "AI_ALLOWED_ORIGINS",
                "http://localhost:8080,http://127.0.0.1:8080",
            ).split(",")
            if origin.strip()
        ]
    )


settings = Settings()
