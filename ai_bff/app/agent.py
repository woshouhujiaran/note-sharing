from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from .login_api_client import LoginApiClient
from .schemas import (
    ChatRequest,
    KeywordRequest,
    NoteSummaryRequest,
    NoteSummaryResponse,
    QuestionReferenceRequest,
    QuestionReferenceResponse,
    SimilarQuestionRequest,
)


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


def _get_resource(context: dict[str, Any]) -> dict[str, Any]:
    resource = context.get("resource")
    if isinstance(resource, dict):
        return resource
    return {}


def _preview_text(value: Any, limit: int = 180) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _resource_label(resource: dict[str, Any], fallback: str = "当前内容") -> str:
    return str(resource.get("title") or fallback)


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
    resource = _get_resource(context)
    message = str(request.get("message") or "")
    facts: list[str] = []
    citations: list[dict[str, Any]] = list(state.get("citations", []))

    resource_kind = str(resource.get("kind") or "").lower()
    resource_title = _resource_label(resource)
    resource_preview = _preview_text(resource.get("contentPreview") or resource.get("content") or "", 240)

    if resource_preview:
        facts.append(f"当前内容片段: 《{resource_title}》 {resource_preview}")
        if resource.get("contentLength"):
            facts.append(f"内容长度约 {resource.get('contentLength')} 字符")
        if resource.get("reason") == "typing":
            facts.append("这是编辑中的实时内容片段，而不是静态页面信息")
        if resource_kind == "note-editor":
            facts.append("当前处于笔记编辑态，反馈应聚焦结构、表达和可修改点")
        elif resource_kind == "note-detail":
            facts.append("当前处于笔记查看态，反馈应聚焦摘要、观点和补充信息")
        elif resource_kind == "qa-detail":
            facts.append("当前处于问答查看态，反馈应聚焦问题清晰度和回答方向")

    note_id = context.get("page", {}).get("viewingNoteId") or context.get("page", {}).get("noteId")
    if note_id:
        try:
            preview = await client.fetch_note_preview(int(note_id), state.get("auth_token"))
            facts.append(f"已连接笔记 {note_id}")
            if isinstance(preview, dict):
                facts.append(f"笔记预览已取回: {preview.get('title') or preview.get('message') or 'unknown'}")

                if any(keyword in message for keyword in ("总结", "摘要", "标题", "续写", "知识整理")):
                    keyword_hint = context.get("page", {}).get("searchKeyword") or preview.get("title") or str(note_id)
                    related_notes = await client.search_notes(str(keyword_hint), token=state.get("auth_token"))
                    summary_source = preview.get("contentSummary")
                    if not summary_source and related_notes:
                        summary_source = related_notes[0].get("contentSummary")
                    facts.append(
                        str(summary_source or f"当前笔记《{preview.get('title') or '未命名笔记'}》已接入只读代理，后续可继续接入正文摘要。")
                    )
                    citations.extend(
                        [
                            {
                                "type": "note",
                                "noteId": preview.get("id") or note_id,
                                "title": preview.get("title") or "未命名笔记",
                                "url": preview.get("url"),
                                "fileType": preview.get("fileType"),
                            }
                        ]
                    )
                    for item in related_notes[:3]:
                        citations.append(
                            {
                                "type": "related-note",
                                "noteId": item.get("noteId"),
                                "title": item.get("title"),
                                "summary": item.get("contentSummary"),
                            }
                        )
        except Exception as exc:  # noqa: BLE001
            facts.append(f"笔记预览回退到本地模式: {exc.__class__.__name__}")

    keyword = context.get("page", {}).get("searchKeyword")
    if keyword:
        try:
            questions = await client.search_questions(str(keyword), state.get("auth_token"))
            facts.append(f"检索到 {len(questions)} 条问答候选")
        except Exception as exc:  # noqa: BLE001
            facts.append(f"问答检索回退到本地模式: {exc.__class__.__name__}")

    question_id = context.get("page", {}).get("questionId") or context.get("route", {}).get("query", {}).get("questionId")
    if question_id and any(keyword in message for keyword in ("问答", "问题", "引用", "相似", "回答")):
        try:
            question = await client.fetch_question_detail(str(question_id), state.get("auth_token"))
            similar_questions = await client.search_questions(str(question.get("title") or question_id), token=state.get("auth_token"))
            answer_count = int(question.get("answerCount") or 0)
            content = str(question.get("content") or "")
            facts.append(
                f"问题《{question.get('title') or '未命名问题'}》已接入只读引用，回答数：{answer_count}。"
                + (f"内容摘要：{content[:80]}{'…' if len(content) > 80 else ''}" if content else "")
            )
            citations.extend(
                [
                    {
                        "type": "question",
                        "questionId": question.get("questionId") or question_id,
                        "title": question.get("title"),
                        "link": f"/main?tab=qa-detail&questionId={question.get('questionId') or question_id}",
                    }
                ]
            )
            for item in (question.get("answers") or [])[:2]:
                citations.append(
                    {
                        "type": "answer",
                        "answerId": item.get("answerId"),
                        "authorName": item.get("authorName"),
                        "content": item.get("content"),
                    }
                )
            for item in similar_questions[:3]:
                citations.append(
                    {
                        "type": "question",
                        "questionId": item.get("questionId"),
                        "title": item.get("title"),
                        "likeCount": item.get("likeCount"),
                        "answerCount": item.get("answerCount"),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            facts.append(f"问题引用回退到本地模式: {exc.__class__.__name__}")

    if not facts:
        facts.append("未命中远端上下文，使用本地稳定规则回复")

    return {**state, "facts": facts, "citations": citations}


def _draft_answer(state: AgentState) -> AgentState:
    request = state.get("request", {})
    message = str(request.get("message") or "")
    facts = state.get("facts", [])
    context = _get_context(request)
    page = context.get("page", {})
    resource = _get_resource(context)
    resource_kind = str(resource.get("kind") or "").lower()
    resource_title = _resource_label(resource)
    resource_preview = _preview_text(resource.get("contentPreview") or resource.get("content") or "", 260)

    if resource_preview and any(keyword in message for keyword in ("总结", "摘要", "summary", "反馈", "点评")):
        if resource_kind == "note-editor":
            answer = (
                f"基于正在编辑的笔记《{resource_title}》，我看到的内容片段是：{resource_preview}\n\n"
                f"建议：1. 先补一个能概括全文的标题 2. 把现有内容拆成更清晰的小节 3. 把结论或待办单独拎出来。"
            )
        elif resource_kind == "qa-detail":
            answer = (
                f"基于当前问答《{resource_title}》，问题内容片段是：{resource_preview}\n\n"
                f"建议：1. 明确提问目标 2. 补足必要背景 3. 回答时优先给可执行方案。"
            )
        else:
            answer = (
                f"基于当前内容《{resource_title}》，核心片段是：{resource_preview}\n\n"
                f"建议：1. 提炼核心观点 2. 补充关键论据 3. 增加一个下一步动作。"
            )
    elif any(keyword in message for keyword in ("标题", "起标题", "title")):
        answer = "标题候选：1. 结构化整理 2. 站内引用摘要 3. 可执行知识卡片"
    elif any(keyword in message for keyword in ("关键词", "keywords")):
        answer = f"关键词：{'、'.join(_extract_keywords(message))}"
    elif any(keyword in message for keyword in ("相似", "重复", "问题")):
        answer = "我会先做相似问题检索，当前返回的是稳定占位列表，后续可替换成站内搜索结果。"
    elif any(keyword in message for keyword in ("总结", "摘要", "summary")):
        detail_fact = next(
            (
                fact
                for fact in facts
                if fact
                and not fact.startswith("已连接")
                and not fact.startswith("笔记预览")
                and not fact.startswith("检索到")
                and not fact.startswith("当前内容片段")
                and not fact.startswith("未命中远端上下文")
            ),
            None,
        )
        answer = detail_fact or f"页面摘要：{page.get('tab') or 'unknown'} / {page.get('searchKeyword') or 'no-keyword'}。"
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

    async def summarize_note(self, request: NoteSummaryRequest, auth_token: str | None = None) -> dict[str, Any]:
        context = _get_context(request.model_dump())
        resource = _get_resource(context)
        note = await self._login_api_client.fetch_note_preview(request.note_id, auth_token)
        title = str(note.get("title") or "未命名笔记")
        keyword = request.keyword or title
        related_notes = await self._login_api_client.search_notes(keyword, user_id=self._context_user_id(request.context), token=auth_token)
        summary_source = self._pick_summary_source(note, related_notes)
        resource_preview = _preview_text(resource.get("contentPreview") or resource.get("content") or "", 220)
        if resource_preview:
            summary_source = f"基于宿主提供的正文片段：{resource_preview}"
        summary = f"笔记《{title}》：{summary_source}" if summary_source else f"当前笔记《{title}》已接入只读代理，后续可继续接入正文摘要。"

        citations = [
            {
                "type": "note",
                "noteId": note.get("id") or request.note_id,
                "title": title,
                "url": note.get("url"),
                "fileType": note.get("fileType"),
            }
        ]
        for item in related_notes[:3]:
            citations.append(
                {
                    "type": "related-note",
                    "noteId": item.get("noteId"),
                    "title": item.get("title"),
                    "summary": item.get("contentSummary"),
                }
            )

        return NoteSummaryResponse(
            note=note,
            summary=summary,
            related_notes=related_notes[:3],
            citations=citations,
            ai_generated=True,
        ).model_dump()

    async def reference_question(self, request: QuestionReferenceRequest, auth_token: str | None = None) -> dict[str, Any]:
        context = _get_context(request.model_dump())
        resource = _get_resource(context)
        question = await self._login_api_client.fetch_question_detail(request.question_id, auth_token)
        question_title = str(question.get("title") or "未命名问题")
        similar_questions = await self._login_api_client.search_questions(question_title, token=auth_token)
        answer_count = int(question.get("answerCount") or 0)
        summary = self._build_question_summary(question, answer_count)
        resource_preview = _preview_text(resource.get("contentPreview") or resource.get("content") or "", 220)
        if resource_preview:
            summary = f"基于宿主提供的问答片段：{resource_preview}"

        references = []
        for answer in (question.get("answers") or [])[:2]:
            references.append(
                {
                    "type": "answer",
                    "answerId": answer.get("answerId"),
                    "authorName": answer.get("authorName"),
                    "content": answer.get("content"),
                }
            )
        for item in similar_questions[:3]:
            references.append(
                {
                    "type": "question",
                    "questionId": item.get("questionId"),
                    "title": item.get("title"),
                    "likeCount": item.get("likeCount"),
                    "answerCount": item.get("answerCount"),
                }
            )

        citations = [
            {
                "type": "question",
                "questionId": question.get("questionId") or request.question_id,
                "title": question_title,
                "link": f"/main?tab=qa-detail&questionId={question.get('questionId') or request.question_id}",
            }
        ]

        return QuestionReferenceResponse(
            question=question,
            references=references,
            citations=citations,
            summary=summary,
            ai_generated=True,
        ).model_dump()

    async def similar_questions(self, request: SimilarQuestionRequest, auth_token: str | None = None) -> dict[str, Any]:
        keywords = _extract_keywords(request.question)
        similar = await self._login_api_client.search_questions(request.question, token=auth_token)
        items = []
        for index, item in enumerate(similar[: request.limit or 3], start=1):
            items.append(
                {
                    "questionId": item.get("questionId") or str(index),
                    "title": item.get("title") or f"与「{keywords[min(index - 1, len(keywords) - 1)]}」相关的问题",
                    "link": f"/main?tab=qa-detail&questionId={item.get('questionId') or index}",
                }
            )

        if not items:
            for index, keyword in enumerate(keywords[: request.limit or 3], start=1):
                items.append(
                    {
                        "questionId": 1000 + index,
                        "title": f"与「{keyword}」相关的相似问题",
                        "link": f"/main?tab=qa-detail&questionId={1000 + index}",
                    }
                )

        return {"items": items[: request.limit or 3], "ai_generated": True}

    async def note_reference(self, note_id: int, auth_token: str | None = None) -> dict[str, Any]:
        note = await self._login_api_client.fetch_note_preview(note_id, auth_token)
        related_notes = await self._login_api_client.search_notes(str(note.get("title") or note_id), token=auth_token)
        return {
            "note": note,
            "related_notes": related_notes[:5],
            "citations": [
                {
                    "type": "note",
                    "noteId": note.get("id") or note_id,
                    "title": note.get("title"),
                    "url": note.get("url"),
                    "fileType": note.get("fileType"),
                }
            ],
            "ai_generated": True,
        }

    def _context_user_id(self, context: Any) -> int | None:
        if not isinstance(context, dict):
            return None
        user = context.get("user") or {}
        user_id = user.get("id")
        try:
            return int(user_id) if user_id is not None else None
        except (TypeError, ValueError):
            return None

    def _pick_summary_source(self, note: dict[str, Any], related_notes: list[dict[str, Any]]) -> str | None:
        if isinstance(note.get("contentSummary"), str) and note["contentSummary"].strip():
            return note["contentSummary"].strip()
        for item in related_notes:
            content_summary = item.get("contentSummary")
            if isinstance(content_summary, str) and content_summary.strip():
                return content_summary.strip()
        return None

    def _build_question_summary(self, question: dict[str, Any], answer_count: int) -> str:
        title = str(question.get("title") or "未命名问题")
        content = str(question.get("content") or "")
        if content.strip():
            return f"问题《{title}》：内容摘要 {content[:80]}{'…' if len(content) > 80 else ''}。回答数：{answer_count}。"
        return f"问题《{title}》已接入只读引用，当前有 {answer_count} 个回答。"
