from __future__ import annotations

from dataclasses import dataclass

import httpx


def _unwrap_standard_response(data):
    if isinstance(data, dict) and "data" in data:
        return data.get("data")
    return data


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
            return _unwrap_standard_response(response.json()) or {}

    async def search_notes(self, keyword: str, user_id: int | None = None, token: str | None = None) -> list[dict]:
        url = f"{self.base_url.rstrip('/')}/api/v1/search/notes"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        payload = {"keyword": keyword}
        if user_id is not None:
            payload["userId"] = user_id

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = _unwrap_standard_response(response.json())
            return data if isinstance(data, list) else []

    async def search_questions(self, keyword: str, token: str | None = None) -> list[dict]:
        url = f"{self.base_url.rstrip('/')}/api/v1/search/questions"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params={"keyword": keyword}, headers=headers)
            response.raise_for_status()
            data = _unwrap_standard_response(response.json())
            return data if isinstance(data, list) else []

    async def fetch_question_detail(self, question_id: str, token: str | None = None) -> dict:
        url = f"{self.base_url.rstrip('/')}/api/v1/qa/question/{question_id}"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return _unwrap_standard_response(response.json()) or {}

    async def fetch_note_comments(self, note_id: int, login_user_id: int, token: str | None = None) -> list[dict]:
        url = f"{self.base_url.rstrip('/')}/api/v1/remark/note/list"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params={"noteId": note_id, "loginUserId": login_user_id}, headers=headers)
            response.raise_for_status()
            data = _unwrap_standard_response(response.json())
            return data if isinstance(data, list) else []
