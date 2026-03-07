import logging
from typing import Any, Iterable, List, Optional, Sequence

import google.generativeai as genai

from app.core.config import settings
from app.core.llm_provider import LLMProvider


class GeminiProvider(LLMProvider):
    """
    Gemini-backed provider used by the query service.

    Supports legacy `generate(prompt=...)` and query-service style
    `generate(query=..., retrieved=..., history=...)`.
    """

    def __init__(self) -> None:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(getattr(settings, "LLM_MODEL", "gemini-2.5-flash"))
        self.is_fallback = False

    def _extract_text(self, response: Any) -> str:
        text = (getattr(response, "text", "") or "").strip()
        if text:
            return text

        # Some SDK responses expose content only through candidates/parts.
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if not parts:
                continue
            joined = "".join(getattr(part, "text", "") for part in parts).strip()
            if joined:
                return joined

        return ""

    def _normalize_history(self, history: Optional[Sequence[Any]]) -> str:
        if not history:
            return ""

        lines: List[str] = []
        for msg in history:
            role = "user"
            content = ""

            if isinstance(msg, dict):
                role = str(msg.get("role", role))
                content = str(msg.get("content", ""))
            else:
                role = str(getattr(msg, "role", role))
                content = str(getattr(msg, "content", ""))

            content = content.strip()
            if content:
                lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def _normalize_sources(self, retrieved: Optional[Iterable[Any]]) -> List[str]:
        if not retrieved:
            return []

        context_lines: List[str] = []
        for idx, point in enumerate(retrieved, start=1):
            payload = getattr(point, "payload", None) or {}
            text = str(payload.get("text") or payload.get("document") or "").strip()
            if not text:
                continue
            score = getattr(point, "score", None)
            score_str = f" score={float(score):.3f}" if score is not None else ""
            context_lines.append(f"[{idx}{score_str}] {text}")

        return context_lines

    def _build_prompt(
        self,
        query: str,
        retrieved: Optional[Iterable[Any]] = None,
        history: Optional[Sequence[Any]] = None,
    ) -> str:
        system_prompt = (
            f"You are an AI assistant for {settings.ORG_NAME}. "
            f"Organization description: {settings.ORG_DESCRIPTION}. "
            "Answer clearly and concisely. "
            "If context is missing, say what is unknown instead of inventing facts."
        )

        history_block = self._normalize_history(history)
        sources = self._normalize_sources(retrieved)
        context_block = "\n".join(sources) if sources else "(no retrieved context)"

        sections = [
            system_prompt,
            "Retrieved context:\n" + context_block,
        ]

        if history_block:
            sections.append("Conversation history:\n" + history_block)

        sections.append("User question:\n" + query.strip())
        return "\n\n".join(sections)

    def _fallback_answer(self, query: str, retrieved: Optional[Iterable[Any]] = None) -> str:
        snippets = self._normalize_sources(retrieved)[:3]
        if snippets:
            return (
                "I could not reach Gemini right now. "
                "Please retry. In the meantime, here is related context:\n"
                + "\n".join(snippets)
            )

        return (
            "I could not reach Gemini right now, and I have no retrieved context to answer safely. "
            "Please retry in a moment."
        )

    def generate(
        self,
        prompt: Optional[str] = None,
        *,
        query: Optional[str] = None,
        retrieved: Optional[Iterable[Any]] = None,
        history: Optional[Sequence[Any]] = None,
    ) -> str:
        user_query = (query or prompt or "").strip()
        if not user_query:
            raise ValueError("A non-empty prompt/query is required.")

        self.is_fallback = False
        full_prompt = self._build_prompt(query=user_query, retrieved=retrieved, history=history)

        try:
            response = self.model.generate_content(full_prompt)
            text = self._extract_text(response)
            if not text:
                raise RuntimeError("Gemini returned an empty response.")
            return text
        except Exception as exc:
            logging.exception("Gemini generation failed: %s", exc)
            self.is_fallback = True
            return self._fallback_answer(query=user_query, retrieved=retrieved)
