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
