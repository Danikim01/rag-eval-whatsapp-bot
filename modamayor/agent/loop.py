from dataclasses import dataclass, field
from typing import Any

from modamayor.agent.provider import ToolProvider
from modamayor.agent.tools import Tool

MAX_CALLS = 6
LIMIT_NOTICE = (
    "Llegaste al límite de llamadas a herramientas de este turno. "
    "Respondé ahora con lo que tenés, sin llamar más herramientas."
)
SKIPPED_RESULT = "Error: se alcanzó el límite de llamadas del turno, esta llamada no se ejecutó."
FALLBACK_TEXT = "No pude completar la consulta. Te derivo con una persona del equipo."


@dataclass(frozen=True)
class TurnResult:
    text: str
    tool_calls_made: int
    capped: bool
    messages: list[dict[str, Any]] = field(default_factory=list)


def _execute(tools_by_name: dict[str, Tool], name: str, arguments: dict[str, Any]) -> str:
    tool = tools_by_name.get(name)
    if tool is None:
        available = ", ".join(sorted(tools_by_name)) or "ninguna"
        return f"Error: la herramienta {name} no existe. Herramientas disponibles: {available}."
    try:
        return tool.run(arguments)
    except Exception as exc:
        return f"Error al ejecutar {name}: {exc}"


def run_turn(
    messages: list[dict[str, Any]],
    tools: list[Tool],
    provider: ToolProvider,
    max_calls: int = MAX_CALLS,
) -> TurnResult:
    history = [dict(m) for m in messages]
    tools_by_name = {t.name: t for t in tools}
    specs = [t.spec() for t in tools]
    made = 0

    while True:
        reply = provider.chat(history, specs)
        if not reply.tool_calls:
            return TurnResult(reply.text, made, False, history)

        history.append({"role": "assistant", "content": reply.text, "tool_calls": reply.tool_calls})
        for tc in reply.tool_calls:
            if made >= max_calls:
                content = SKIPPED_RESULT
            else:
                content = _execute(tools_by_name, tc.name, tc.arguments)
                made += 1
            history.append(
                {"role": "tool", "tool_call_id": tc.id, "name": tc.name, "content": content}
            )

        if made >= max_calls:
            history.append({"role": "user", "content": LIMIT_NOTICE})
            closing = provider.chat(history, [])
            return TurnResult(closing.text or FALLBACK_TEXT, made, True, history)
