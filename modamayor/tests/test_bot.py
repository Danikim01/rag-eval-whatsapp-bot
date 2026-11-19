from modamayor.bot import reply
from modamayor.rag import build_prompt
from modamayor.triage import CLARIFY_MARKER

OWNER = "5491112345678"


class FakeRetriever:
    def retrieve(self, question, k=4):
        return []


def make_generate(label, answer_text="respuesta rag"):
    def generate(prompt):
        if "Clasificá el último mensaje" in prompt:
            return label
        return answer_text

    return generate


def test_answer_goes_through_rag():
    out = reply("cuanto sale el buzo?", [], OWNER, FakeRetriever(), make_generate("answer"))
    assert out == "respuesta rag"


def test_clarify_returns_clarify_message_without_rag():
    out = reply("color de naranja?", [], OWNER, FakeRetriever(), make_generate("clarify"))
    assert CLARIFY_MARKER in out


def test_handoff_returns_owner_link_with_question():
    out = reply("hacen bordado?", [], OWNER, FakeRetriever(), make_generate("handoff"))
    assert f"https://wa.me/{OWNER}?text=" in out
    assert "bordado" in out


def test_second_clarify_becomes_handoff():
    history = [("user", "naranja?"), ("assistant", f"Perdón, {CLARIFY_MARKER}.")]
    out = reply("insisto", history, OWNER, FakeRetriever(), make_generate("clarify"))
    assert "wa.me" in out


def test_rag_prompt_includes_history_and_greeting_rule():
    prompt = build_prompt("y el envio?", [], history=[("user", "hola"), ("assistant", "buenas")])
    assert "Cliente: hola" in prompt and "Asistente: buenas" in prompt
    assert "saluda" in prompt.lower()


from modamayor.agent.prompt import build_system_prompt
from modamayor.agent.provider import AssistantMessage, ToolCall
from urllib.parse import quote

from modamayor.agent.tools_catalog import HANDOFF_REPEAT_NOTICE
from modamayor.scoring import HANDOFF_MARKER

FACTS = {
    "articles": [
        {"id": "buzo", "name": "Buzo canguro", "aliases": [], "valid_from": "2020-01-01", "price": 10000, "min_units": 6}
    ],
    "rules": {
        "min_purchase": [{"value": 50000, "from": "2020-01-01", "source": "c.md"}],
        "transfer_discount_pct": [{"value": 10, "from": "2020-01-01", "source": "c.md"}],
        "free_shipping_from": [{"value": 400000, "from": "2020-01-01", "source": "c.md"}],
    },
}


class ScriptedProvider:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def chat(self, messages, tools):
        self.calls.append((list(messages), [t["name"] if "name" in t else t for t in tools]))
        return self.script.pop(0)


def call(name, **arguments):
    return AssistantMessage(text="", tool_calls=[ToolCall(id=f"c-{name}", name=name, arguments=arguments)])


def test_answer_branch_runs_tool_loop():
    provider = ScriptedProvider([call("buscar_info", consulta="horarios"), AssistantMessage(text="Abrimos de 9 a 18")])
    out = reply(
        "a que hora abren?", [], OWNER, FakeRetriever(), make_generate("answer"),
        provider=provider, conversation_id="c1", handoff_store={},
    )
    assert out == "Abrimos de 9 a 18"
    assert len(provider.calls) == 2


def test_clarify_and_handoff_never_enter_the_loop():
    for label in ("clarify", "handoff"):
        provider = ScriptedProvider([])
        out = reply("x", [], OWNER, FakeRetriever(), make_generate(label), provider=provider, conversation_id="c1")
        assert provider.calls == []
        assert out


def test_handoff_signal_returns_owner_link():
    provider = ScriptedProvider([call("derivar_a_humano", motivo="quiere confirmar pedido"), AssistantMessage(text="ok")])
    out = reply(
        "confirmame el pedido", [], OWNER, FakeRetriever(), make_generate("answer"),
        provider=provider, conversation_id="c2", handoff_store={},
    )
    assert f"https://wa.me/{OWNER}?text=" in out
    assert quote("confirmame el pedido") in out


def test_repeat_handoff_does_not_resend_link():
    store = {}
    first = ScriptedProvider([call("derivar_a_humano", motivo="m"), AssistantMessage(text="ok")])
    reply("confirmar", [], OWNER, FakeRetriever(), make_generate("answer"), provider=first, conversation_id="c3", handoff_store=store)
    second = ScriptedProvider([call("derivar_a_humano", motivo="m"), AssistantMessage(text="Ya tiene tu consulta una persona del equipo")])
    out = reply("confirmar ya", [], OWNER, FakeRetriever(), make_generate("answer"), provider=second, conversation_id="c3", handoff_store=store)
    assert "wa.me" not in out
    assert out == "Ya tiene tu consulta una persona del equipo"
    assert any(HANDOFF_REPEAT_NOTICE in m.get("content", "") for m in second.calls[1][0])


def test_history_and_question_reach_provider():
    provider = ScriptedProvider([AssistantMessage(text="hola")])
    reply(
        "y el envio?", [("user", "hola"), ("assistant", "buenas")], OWNER, FakeRetriever(), make_generate("answer"),
        provider=provider, conversation_id="c4", handoff_store={},
    )
    messages = provider.calls[0][0]
    assert messages[0]["role"] == "system"
    assert [m["role"] for m in messages[1:]] == ["user", "assistant", "user"]
    assert messages[-1]["content"] == "y el envio?"


def test_cotizar_available_only_with_facts():
    with_facts = ScriptedProvider([AssistantMessage(text="a")])
    reply("hola", [], OWNER, FakeRetriever(), make_generate("answer"), facts=FACTS, today="2026-11-18",
          provider=with_facts, conversation_id="c5", handoff_store={})
    without = ScriptedProvider([AssistantMessage(text="a")])
    reply("hola", [], OWNER, FakeRetriever(), make_generate("answer"),
          provider=without, conversation_id="c6", handoff_store={})
    assert "cotizar" in with_facts.calls[0][1]
    assert "cotizar" not in without.calls[0][1]


def test_order_flows_to_cotizar_with_system_total():
    provider = ScriptedProvider([
        call("cotizar", items=[{"article_id": "buzo", "cantidad": 12}]),
        AssistantMessage(text="Te queda asi"),
    ])
    reply("quiero 12 buzos", [], OWNER, FakeRetriever(), make_generate("answer"), facts=FACTS, today="2026-11-18",
          provider=provider, conversation_id="c7", handoff_store={})
    tool_msgs = [m for m in provider.calls[1][0] if m["role"] == "tool"]
    assert tool_msgs and "120" in tool_msgs[0]["content"]


def test_system_prompt_forbids_confirming_orders():
    prompt = build_system_prompt("2026-11-18")
    assert "2026-11-18" in prompt
    assert HANDOFF_MARKER in prompt
    assert "confirm" in prompt.lower()
    assert "derivar_a_humano" in prompt and "cotizar" in prompt


def test_system_prompt_requires_direct_cotizar_call():
    prompt = build_system_prompt(None)
    assert "artículo y una cantidad" in prompt
    assert "sin pedir confirmación" in prompt
