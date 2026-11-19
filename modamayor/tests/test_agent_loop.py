from pydantic import BaseModel, Field

from modamayor.agent.tools import Tool


class CotizarInput(BaseModel):
    modelo: str
    cantidad: int = Field(gt=0)


def cotizar(args: CotizarInput) -> str:
    return f"{args.modelo} x{args.cantidad}"


def make_tool() -> Tool:
    return Tool(name="cotizar", description="Cotiza un modelo", input_model=CotizarInput, fn=cotizar)


def test_validation_negative_quantity_returns_error_and_skips_execution():
    calls: list[CotizarInput] = []

    def spy(args: CotizarInput) -> str:
        calls.append(args)
        return "ok"

    tool = Tool(name="cotizar", description="d", input_model=CotizarInput, fn=spy)
    result = tool.run({"modelo": "remera", "cantidad": -2})
    assert "cantidad" in result
    assert result.startswith("Error")
    assert calls == []


def test_validation_missing_field_returns_error():
    result = make_tool().run({"cantidad": 3})
    assert result.startswith("Error")
    assert "modelo" in result


def test_valid_arguments_execute():
    assert make_tool().run({"modelo": "remera", "cantidad": 3}) == "remera x3"


def test_spec_is_built_from_the_model_schema():
    spec = make_tool().spec()
    assert spec["name"] == "cotizar"
    assert spec["description"] == "Cotiza un modelo"
    assert set(spec["parameters"]["properties"]) == {"modelo", "cantidad"}
    assert "phone" not in spec["parameters"]["properties"]


from modamayor.agent.loop import LIMIT_NOTICE, run_turn
from modamayor.agent.provider import AssistantMessage, ToolCall


class ScriptedProvider:
    def __init__(self, replies: list[AssistantMessage]) -> None:
        self.replies = list(replies)
        self.seen: list[tuple[list[dict], list[dict]]] = []

    def chat(self, messages, tools):
        self.seen.append(([dict(m) for m in messages], tools))
        return self.replies.pop(0)


def call(i: int, name: str = "cotizar", **arguments) -> ToolCall:
    return ToolCall(id=f"call_{i}", name=name, arguments=arguments)


def test_turn_without_tool_calls_returns_text():
    provider = ScriptedProvider([AssistantMessage(text="hola")])
    result = run_turn([{"role": "user", "content": "hi"}], [make_tool()], provider)
    assert result.text == "hola"
    assert result.tool_calls_made == 0
    assert not result.capped


def test_tool_result_goes_back_to_the_model():
    provider = ScriptedProvider(
        [
            AssistantMessage(text="", tool_calls=[call(0, modelo="remera", cantidad=2)]),
            AssistantMessage(text="son 2 remeras"),
        ]
    )
    result = run_turn([{"role": "user", "content": "cotizame"}], [make_tool()], provider)
    assert result.text == "son 2 remeras"
    tool_msg = provider.seen[1][0][-1]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_0"
    assert tool_msg["name"] == "cotizar"
    assert tool_msg["content"] == "remera x2"


def test_unknown_tool_returns_error_and_counts_against_limit():
    provider = ScriptedProvider(
        [
            AssistantMessage(text="", tool_calls=[call(0, name="borrar_todo")]),
            AssistantMessage(text="no puedo"),
        ]
    )
    result = run_turn([{"role": "user", "content": "x"}], [make_tool()], provider)
    assert result.tool_calls_made == 1
    tool_msg = provider.seen[1][0][-1]
    assert tool_msg["content"].startswith("Error")
    assert "borrar_todo" in tool_msg["content"]


def test_limit_caps_calls_and_closes_the_turn():
    looping = [
        AssistantMessage(text="", tool_calls=[call(0, modelo="a", cantidad=1)]) for _ in range(3)
    ]
    provider = ScriptedProvider(looping + [AssistantMessage(text="cierre")])
    executed: list[str] = []

    def spy(args: CotizarInput) -> str:
        executed.append(args.modelo)
        return "ok"

    tool = Tool(name="cotizar", description="d", input_model=CotizarInput, fn=spy)
    result = run_turn([{"role": "user", "content": "x"}], [tool], provider, max_calls=3)
    assert len(executed) == 3
    assert result.tool_calls_made == 3
    assert result.capped
    assert result.text == "cierre"
    final_messages = provider.seen[-1][0]
    assert final_messages[-1] == {"role": "user", "content": LIMIT_NOTICE}


def test_limit_inside_a_single_reply_answers_every_call_id():
    provider = ScriptedProvider(
        [
            AssistantMessage(text="", tool_calls=[call(0, modelo="a", cantidad=1), call(1, modelo="b", cantidad=1)]),
            AssistantMessage(text="cierre"),
        ]
    )
    result = run_turn([{"role": "user", "content": "x"}], [make_tool()], provider, max_calls=1)
    assert result.capped
    tool_msgs = [m for m in provider.seen[-1][0] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["call_0", "call_1"]


def test_limit_close_ignores_tool_calls_in_the_final_reply():
    provider = ScriptedProvider(
        [
            AssistantMessage(text="", tool_calls=[call(0, modelo="a", cantidad=1)]),
            AssistantMessage(text="", tool_calls=[call(1, modelo="a", cantidad=1)]),
        ]
    )
    result = run_turn([{"role": "user", "content": "x"}], [make_tool()], provider, max_calls=1)
    assert result.capped
    assert result.text


def test_input_messages_are_not_mutated():
    messages = [{"role": "user", "content": "x"}]
    run_turn(messages, [make_tool()], ScriptedProvider([AssistantMessage(text="ok")]))
    assert messages == [{"role": "user", "content": "x"}]
