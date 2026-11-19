from typing import Callable

from modamayor.agent.loop import run_turn
from modamayor.agent.prompt import build_system_prompt
from modamayor.agent.provider import ToolProvider
from modamayor.agent.tools import Tool
from modamayor.agent.tools_catalog import (
    HANDOFF_SIGNAL,
    build_buscar_info,
    build_cotizar,
    build_derivar_a_humano,
)
from modamayor.rag import Retriever, answer
from modamayor.triage import History, clarify_message, handoff_message, triage

HANDOFF_REASON = "consulta que el asistente no puede resolver"
HISTORY_TURNS = 6

_DEFAULT_HANDOFF_STORE: dict[str, float] = {}


def _history_messages(history: History) -> list[dict[str, str]]:
    return [
        {"role": "user" if role == "user" else "assistant", "content": content}
        for role, content in history[-HISTORY_TURNS:]
    ]


def _agent_reply(
    question: str,
    history: History,
    owner_number: str,
    retriever: Retriever,
    provider: ToolProvider,
    today: str | None,
    facts: dict | None,
    k: int,
    conversation_id: str,
    handoff_store: dict[str, float],
) -> str:
    tools: list[Tool] = [
        build_buscar_info(retriever, k),
        build_derivar_a_humano(conversation_id, store=handoff_store),
    ]
    if facts is not None:
        tools.append(build_cotizar(facts, today or ""))
    messages = [
        {"role": "system", "content": build_system_prompt(today)},
        *_history_messages(history),
        {"role": "user", "content": question},
    ]
    result = run_turn(messages, tools, provider)
    handed_off = any(m.get("role") == "tool" and m.get("content") == HANDOFF_SIGNAL for m in result.messages)
    if handed_off:
        return handoff_message(owner_number, question, HANDOFF_REASON)
    return result.text


def reply(
    question: str,
    history: History,
    owner_number: str,
    retriever: Retriever,
    generate: Callable[[str], str],
    today: str | None = None,
    facts: dict | None = None,
    k: int = 4,
    provider: ToolProvider | None = None,
    conversation_id: str = "default",
    handoff_store: dict[str, float] | None = None,
) -> str:
    action = triage(question, history, generate)
    if action == "clarify":
        return clarify_message()
    if action == "handoff":
        return handoff_message(owner_number, question, HANDOFF_REASON)
    if provider is None:
        return answer(question, retriever, k=k, today=today, generate=generate, facts=facts, history=history)
    store = _DEFAULT_HANDOFF_STORE if handoff_store is None else handoff_store
    return _agent_reply(
        question, history, owner_number, retriever, provider, today, facts, k, conversation_id, store
    )
