from modamayor.scoring import HANDOFF_MARKER, normalize, score

DIRECT = {
    "id": "x1",
    "key_facts": ["4800", "12"],
    "handoff": False,
}

TRAP = {
    "id": "x2",
    "key_facts": ["17800"],
    "must_not_say": ["14500"],
    "handoff": False,
}

NO_ANSWER = {
    "id": "x3",
    "key_facts": [],
    "handoff": True,
}


def test_normalize_strips_accents_case_and_thousand_separators():
    assert normalize("Falla de FÁBRICA") == "falla de fabrica"
    assert normalize("Sale $4.800 c/u") == "sale $4800 c/u"
    assert normalize("$655.040,50") == "$655040,50"


def test_all_key_facts_present_passes():
    result = score(DIRECT, "La remera lisa sale $4.800 y la curva es de 12 unidades.")
    assert result.passed
    assert result.missing == []


def test_missing_key_fact_fails_and_is_reported():
    result = score(DIRECT, "La remera lisa sale $4.800.")
    assert not result.passed
    assert result.missing == ["12"]


def test_forbidden_value_fails_even_if_correct_one_present():
    result = score(TRAP, "Antes costaba $14.500 y ahora $17.800.")
    assert not result.passed
    assert result.forbidden_hits == ["14500"]


def test_correct_answer_without_forbidden_value_passes():
    assert score(TRAP, "El buzo frisa sale $17.800, minimo 6.").passed


def test_handoff_required_and_present_passes():
    answer = f"No tengo ese dato, {HANDOFF_MARKER}."
    assert score(NO_ANSWER, answer).passed


def test_handoff_required_but_answered_fails():
    result = score(NO_ANSWER, "Si, hacemos estampado personalizado.")
    assert not result.passed
    assert result.handoff_ok is False


def test_unneeded_handoff_fails():
    result = score(DIRECT, f"{HANDOFF_MARKER}")
    assert not result.passed
    assert result.handoff_ok is False


def test_handoff_marker_ignores_accents_and_case():
    assert score(NO_ANSWER, "TE PASO CON UNA PERSONA").passed
