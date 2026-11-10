from modamayor.triage import (
    CLARIFY_MARKER,
    build_triage_prompt,
    owner_link,
    parse_action,
    resolve_action,
    triage,
)


def test_parse_action_reads_plain_label():
    assert parse_action("answer") == "answer"
    assert parse_action("  CLARIFY\n") == "clarify"
    assert parse_action("handoff.") == "handoff"


def test_parse_action_finds_label_inside_text():
    assert parse_action("La acción es: handoff porque pide hablar con alguien") == "handoff"


def test_parse_action_garbage_defaults_to_answer():
    assert parse_action("???") == "answer"
    assert parse_action("") == "answer"


def test_prompt_has_identity_labels_question_and_history():
    history = [("user", "hola"), ("assistant", "Hola, soy el asistente")]
    prompt = build_triage_prompt("cuanto sale?", history)
    assert "mayorista de ropa" in prompt
    for label in ("answer", "clarify", "handoff"):
        assert label in prompt
    assert "cuanto sale?" in prompt
    assert "hola" in prompt and "Hola, soy el asistente" in prompt


def test_prompt_without_history_says_chat_is_empty():
    assert "primer mensaje" in build_triage_prompt("hola", [])


def test_resolve_keeps_first_clarify():
    assert resolve_action("clarify", []) == "clarify"
    assert resolve_action("clarify", [("user", "x"), ("assistant", "algo sin marcador")]) == "clarify"


def test_resolve_turns_second_clarify_into_handoff():
    history = [("user", "naranja?"), ("assistant", f"{CLARIFY_MARKER}, podes reformular?"), ("user", "dale")]
    assert resolve_action("clarify", history) == "handoff"


def test_resolve_does_not_touch_answer_or_handoff():
    history = [("assistant", CLARIFY_MARKER)]
    assert resolve_action("answer", history) == "answer"
    assert resolve_action("handoff", history) == "handoff"


def test_triage_uses_generator_and_resolves():
    assert triage("de que color es una naranja?", [], generate=lambda p: "clarify") == "clarify"
    history = [("assistant", CLARIFY_MARKER)]
    assert triage("insisto", history, generate=lambda p: "clarify") == "handoff"


def test_owner_link_is_urlencoded_and_carries_question_and_reason():
    link = owner_link("5491112345678", "Hacen bordado?", "pedido personalizado")
    assert link.startswith("https://wa.me/5491112345678?text=")
    assert " " not in link
    assert "Hacen%20bordado%3F" in link or "Hacen+bordado%3F" in link
    assert "pedido" in link
