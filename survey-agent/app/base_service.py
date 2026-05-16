"""Contract every service agent must follow. Service agents never call the LLM."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ServiceResult:
    """Standardized return type for every service agent."""

    def __init__(
        self,
        success: bool,
        data: dict[str, Any] | None = None,
        pre_written_reply: str | None = None,
        error_message: str | None = None,
        needs_redo: bool = False,
        needs_human: bool = False,
        clarification_question: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.success = success
        self.data = data or {}
        self.pre_written_reply = pre_written_reply
        self.error_message = error_message
        self.needs_redo = needs_redo
        self.needs_human = needs_human
        self.clarification_question = clarification_question
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "pre_written_reply": self.pre_written_reply,
            "error_message": self.error_message,
            "needs_redo": self.needs_redo,
            "needs_human": self.needs_human,
            "clarification_question": self.clarification_question,
            "metadata": self.metadata,
        }

    @classmethod
    def ok(cls, data: dict) -> "ServiceResult":
        return cls(success=True, data=data)

    @classmethod
    def reply(cls, text: str) -> "ServiceResult":
        return cls(success=True, pre_written_reply=text)

    @classmethod
    def error(cls, message: str, needs_redo: bool = False) -> "ServiceResult":
        return cls(success=False, error_message=message, needs_redo=needs_redo)

    @classmethod
    def ask_human(cls, question: str) -> "ServiceResult":
        return cls(success=True, clarification_question=question, pre_written_reply=question)

    @classmethod
    def escalate(cls, message: str) -> "ServiceResult":
        return cls(success=True, pre_written_reply=message, needs_human=True)


class BaseServiceAgent(ABC):
    @property
    @abstractmethod
    def service_name(self) -> str: ...

    @property
    @abstractmethod
    def handled_intents(self) -> list[str]: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def example_questions(self) -> list[str]: ...

    @abstractmethod
    def execute(
        self,
        action: str,
        params: dict[str, Any],
        user_id: str,
        raw_message: str,
        history: list[dict],
    ) -> ServiceResult: ...

    def can_handle(self, intent: str) -> bool:
        return intent in self.handled_intents

    def get_info(self) -> dict:
        return {
            "service_name": self.service_name,
            "handled_intents": self.handled_intents,
            "description": self.description,
            "example_questions": self.example_questions,
        }
