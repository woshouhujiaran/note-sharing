from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class LoginApiClient:
    base_url: str
    timeout: float = 6.0

    async def fetch_note_preview(self, note_id: int, token: str | None = None) -> dict:
        url = f"{self.base_url.rstrip('/')}/api/v1/noting/notes/files/id_url"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, params={"noteId": note_id}, headers=headers)
            response.raise_for_status()
            return response.json()

    async def search_questions(self, keyword: str, token: str | None = None) -> list[dict]:
        url = f"{self.base_url.rstrip('/')}/api/v1/search/questions"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params={"keyword": keyword}, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else data.get("data", []) if isinstance(data, dict) else []

