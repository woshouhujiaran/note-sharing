from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from .login_api_client import LoginApiClient
from .schemas import ChatRequest, KeywordRequest, SimilarQuestionRequest


class AgentState(TypedDict, total=False):
    request: dict[str, Any]
    auth_token: str | None
    facts: list[str]
    answer: str
    route: dict[str, Any] | None
    citations: list[dict[str, Any]]


def _get_context(request: dict[str, Any]) -> dict[str, Any]:
    context = request.get("context")
    if isinstance(context, dict):
        return context
    return {}


def _extract_keywords(text: str) -> list[str]:
    raw_parts = [
        part.strip(" ,，。！？!?\n\t")
        for part in text.replace("/", " ").replace("、", " ").split()
    ]
    candidates: list[str] = []
    for item in raw_parts:
        if len(item) < 2:
            continue
        if item not in candidates:
            candidates.append(item)
    return candidates[:8] or ["知识整理", "AI 协作", "笔记助手"]


async def _collect_facts(state: AgentState, client: LoginApiClient) -> AgentState:
    request = state.get("request", {})
    context = _get_context(request)
    facts: list[str] = []

    note_id = context.get("page", {}).get("viewingNoteId") or context.get("page", {}).get("noteId")
    if note_id:
        try:
            preview = await client.fetch_note_preview(int(note_id), state.get("auth_token"))
            facts.append(f"已连接笔记 {note_id}")
            if isinstance(preview, dict):
                facts.append(f"笔记预览已取回: {preview.get('title') or preview.get('message') or 'unknown'}")
        except Exception as exc:  # noqa: BLE001
            facts.append(f"笔记预览回退到本地模式: {exc.__class__.__name__}")

    keyword = context.get("page", {}).get("searchKeyword")
    if keyword:
        try:
            questions = await client.search_questions(str(keyword), state.get("auth_token"))
            facts.append(f"检索到 {len(questions)} 条问答候选")
        except Exception as exc:  # noqa: BLE001
            facts.append(f"问答检索回退到本地模式: {exc.__class__.__name__}")

    if not facts:
        facts.append("未命中远端上下文，使用本地稳定规则回复")

    return {**state, "facts": facts}


def _draft_answer(state: AgentState) -> AgentState:
    request = state.get("request", {})
    message = str(request.get("message") or "")
    facts = state.get("facts", [])
    context = _get_context(request)
    page = context.get("page", {})

    if any(keyword in message for keyword in ("标题", "起标题", "title")):
        answer = "标题候选：1. 结构化整理 2. 站内引用摘要 3. 可执行知识卡片"
    elif any(keyword in message for keyword in ("关键词", "keywords")):
        answer = f"关键词：{'、'.join(_extract_keywords(message))}"
    elif any(keyword in message for keyword in ("相似", "重复", "问题")):
        answer = "我会先做相似问题检索，当前返回的是稳定占位列表，后续可替换成站内搜索结果。"
    elif any(keyword in message for keyword in ("总结", "摘要", "summary")):
        answer = f"页面摘要：{page.get('tab') or 'unknown'} / {page.get('searchKeyword') or 'no-keyword'}。"
    else:
        answer = f"已收到请求：{message}\n\n上下文事实：\n- " + "\n- ".join(facts)

    citations = []
    if page.get("viewingNoteId"):
        citations.append({
            "type": "note",
            "noteId": page.get("viewingNoteId"),
            "title": page.get("pageLabel") or "当前笔记"
        })

    route = None
    if "搜索" in message or "search" in message.lower():
        route = {"path": "/main", "query": {"tab": "search", "keyword": page.get("searchKeyword") or ""}}
    elif "问答" in message or "qa" in message.lower():
        route = {"path": "/main", "query": {"tab": "circle"}}

    return {**state, "answer": answer, "citations": citations, "route": route}


class AgentRuntime:
    def __init__(self, login_api_client: LoginApiClient):
        self._login_api_client = login_api_client
        self._graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AgentState)
        
        async def collect_facts(state: AgentState) -> AgentState:
            return await _collect_facts(state, self._login_api_client)

        builder.add_node("collect_facts", collect_facts)
        builder.add_node("draft_answer", _draft_answer)
        builder.set_entry_point("collect_facts")
        builder.add_edge("collect_facts", "draft_answer")
        builder.add_edge("draft_answer", END)
        return builder.compile()

    async def run(self, request: ChatRequest, auth_token: str | None = None) -> dict[str, Any]:
        result = await self._graph.ainvoke({"request": request.model_dump(), "auth_token": auth_token})
        return {
            "answer": result.get("answer", ""),
            "citations": result.get("citations", []),
            "route": result.get("route"),
            "ai_generated": True,
            "source": "langgraph",
        }

    async def keywords(self, request: KeywordRequest, auth_token: str | None = None) -> dict[str, Any]:
        keywords = _extract_keywords(request.text)
        return {
            "keywords": keywords,
            "explain": f"根据当前文本和上下文提取 {len(keywords)} 个候选关键词",
            "ai_generated": True,
        }

    async def similar_questions(self, request: SimilarQuestionRequest, auth_token: str | None = None) -> dict[str, Any]:
        keywords = _extract_keywords(request.question)
        items = []
        for index, keyword in enumerate(keywords[: request.limit or 3], start=1):
            items.append(
                {
                    "questionId": 1000 + index,
                    "title": f"与「{keyword}」相关的相似问题",
                    "link": f"/main?tab=qa-detail&questionId={1000 + index}",
                }
            )

        return {"items": items[: request.limit or 3], "ai_generated": True}
