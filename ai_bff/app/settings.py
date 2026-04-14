from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(slots=True)
class Settings:
    login_api_base_url: str = os.getenv("AI_LOGIN_API_BASE_URL", "http://localhost:8080")
    jwt_secret: str = os.getenv("AI_JWT_SECRET", "")
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
