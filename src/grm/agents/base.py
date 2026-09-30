"""Fixed model binding per role.

One LangChain chat model per role, resolved from the environment at
construction. No runtime model selection, no model name in flow logic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import SecretStr

from grm.config import Settings, get_settings
from grm.observability.logging import get_logger

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

#: Roles the user never speaks to directly.
INTERNAL_ROLES = frozenset({"qa"})


class ConfigurationError(RuntimeError):
    """Raised when a role has no usable model binding. Fails loudly."""


@lru_cache
def load_constitution(role: str) -> str:
    """Read a role's constitution from disk, once per process."""
    filename = {
        "chat": "chat_agent.md",
        "reasoning": "reasoning_agent.md",
        "qa": "qa_agent.md",
    }[role]
    path = PROMPT_DIR / filename
    if not path.exists():  # pragma: no cover - packaging error
        raise ConfigurationError(f"missing constitution: {path}")
    return path.read_text(encoding="utf-8").strip()


@dataclass
class AgentAdapter:
    """A role bound to exactly one model, with its constitution loaded."""

    role: str
    model_id: str
    constitution: str = field(default="")

    def __post_init__(self) -> None:
        if not self.constitution:
            self.constitution = load_constitution(self.role)

    @property
    def internal(self) -> bool:
        return self.role in INTERNAL_ROLES

    def bind(self) -> Any:
        """Construct the chat model. Imported lazily to keep import cost low."""
        from langchain_openai import ChatOpenAI

        if not self.model_id:
            raise ConfigurationError(
                f"role {self.role!r} has no model id bound; check the environment"
            )
        settings = get_settings()
        if not settings.api_key:
            raise ConfigurationError("API_KEY is not set; the agents cannot call a model")
        # SecretStr is the type LangChain expects; ours arrives as a plain str.
        secret = SecretStr(settings.api_key)
        return ChatOpenAI(
            model=self.model_id,
            api_key=secret,
            base_url=settings.base_url or None,
            temperature=0.2 if self.role == "qa" else 0.4,
        )

    def messages(
        self,
        user_text: str,
        context: str = "",
        history: list[dict[str, str]] | None = None,
    ) -> list[BaseMessage]:
        """Assemble the message list for one call.

        History is included so pronouns and follow-ups resolve. Without it a
        question like "what should I do about it" has no referent.
        """
        system = self.constitution
        if context:
            system = f"{system}\n\n---\n\n## Authenticated session data\n\n{context}"
        messages: list[BaseMessage] = [SystemMessage(content=system)]

        for entry in (history or [])[-8:]:
            speaker = entry.get("role")
            text = entry.get("text", "")
            if not text or speaker == "user":
                continue
            label = (
                "Beneficiary"
                if speaker == "user"
                else ("Assistant" if speaker in {"chat", "assistant"} else "Analysis")
            )
            messages.append(AIMessage(content=f"{label}: {text}"))

        messages.append(HumanMessage(content=user_text))
        return messages

    async def invoke(
        self,
        user_text: str,
        context: str = "",
        history: list[dict[str, str]] | None = None,
    ) -> AIMessage:
        """One model call, timed and logged on both sides of the wire.

        Every inference in the system passes through here, so this is the single
        place where provider latency becomes visible. A slow line here is the
        provider. A gap with no line here means we never made the call.
        """
        log = get_logger()
        prompt_chars = len(context) + len(user_text)
        log.info(
            "calling model",
            stage=f"model:{self.role}",
            model=self.model_id,
            prompt_chars=prompt_chars,
        )
        started = time.perf_counter()
        model = self.bind()
        try:
            response: AIMessage = await model.ainvoke(self.messages(user_text, context, history))
        except Exception as exc:
            log.error(
                "model call raised",
                stage=f"model:{self.role}",
                model=self.model_id,
                duration_s=round(time.perf_counter() - started, 2),
                error=type(exc).__name__,
            )
            raise
        duration = time.perf_counter() - started
        text = response.content if isinstance(response.content, str) else str(response.content)
        log.info(
            "model replied",
            stage=f"model:{self.role}",
            model=self.model_id,
            duration_s=round(duration, 2),
            reply_chars=len(text),
        )
        return response


@lru_cache
def get_adapters() -> dict[str, AgentAdapter]:
    settings: Settings = get_settings()
    return {
        "chat": AgentAdapter(role="chat", model_id=settings.chat_model),
        "reasoning": AgentAdapter(role="reasoning", model_id=settings.reasoning_model),
        "qa": AgentAdapter(role="qa", model_id=settings.qa_model),
    }
