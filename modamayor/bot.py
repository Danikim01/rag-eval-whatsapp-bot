from typing import Callable

from modamayor.rag import Retriever, answer
from modamayor.triage import History, clarify_message, handoff_message, triage

HANDOFF_REASON = "consulta que el asistente no puede resolver"
HISTORY_TURNS = 6


def reply(
    question: str,
    history: History,
    owner_number: str,
    retriever: Retriever,
    generate: Callable[[str], str],
    today: str | None = None,
    facts: dict | None = None,
    k: int = 4,
) -> str:
    action = triage(question, history, generate)
    if action == "clarify":
        return clarify_message()
    if action == "handoff":
        return handoff_message(owner_number, question, HANDOFF_REASON)
    return answer(question, retriever, k=k, today=today, generate=generate, facts=facts, history=history)
