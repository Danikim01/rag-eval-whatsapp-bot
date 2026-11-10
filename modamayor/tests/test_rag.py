import chromadb

from modamayor.loader import Chunk
from modamayor.rag import Retriever, build_prompt

VOCAB = ["buzo", "remera", "minimo", "transferencia"]


def fake_embed(texts):
    return [[float(t.lower().count(w)) + 0.01 for w in VOCAB] for t in texts]


CHUNKS = [
    Chunk("a#0", "buzo frisa 17800", "lista_oct.txt", "2026-10"),
    Chunk("a#1", "remera lisa 4800", "lista_oct.txt", "2026-10"),
    Chunk("b#0", "minimo de compra 250000 transferencia", "cond.md", None),
]


def make_retriever():
    client = chromadb.EphemeralClient()
    return Retriever(client, fake_embed, name="test_col", chunks=CHUNKS)


def test_retrieve_returns_most_similar_first():
    hits = make_retriever().retrieve("precio del buzo", k=2)
    assert hits[0].id == "a#0"
    assert len(hits) == 2


def test_retrieved_chunks_keep_source_and_date():
    hit = make_retriever().retrieve("remera", k=1)[0]
    assert hit.source == "lista_oct.txt"
    assert hit.date == "2026-10"
    assert hit.text == "remera lisa 4800"


def test_undated_chunk_roundtrips_as_none():
    hit = make_retriever().retrieve("minimo transferencia", k=1)[0]
    assert hit.id == "b#0"
    assert hit.date is None


def test_rebuilding_same_name_does_not_duplicate():
    client = chromadb.EphemeralClient()
    Retriever(client, fake_embed, name="dup", chunks=CHUNKS)
    again = Retriever(client, fake_embed, name="dup", chunks=CHUNKS)
    assert len(again.retrieve("buzo", k=10)) == len(CHUNKS)


def test_prompt_contains_context_question_and_handoff_rule():
    prompt = build_prompt("cuanto sale el buzo?", CHUNKS[:1], today="2026-11-09")
    assert "buzo frisa 17800" in prompt
    assert "cuanto sale el buzo?" in prompt
    assert "te paso con una persona" in prompt
    assert "2026-11-09" in prompt
    assert "lista_oct.txt" in prompt


def test_prompt_includes_verified_calculation_when_given():
    prompt = build_prompt("q?", CHUNKS[:1], verified="Total a pagar: $655.040.")
    assert "Total a pagar: $655.040." in prompt
    assert "no lo recalcules" in prompt


def test_prompt_without_verified_has_no_calculation_section():
    assert "Cálculo verificado" not in build_prompt("q?", CHUNKS[:1])


def test_prompt_tells_model_not_to_hand_off_when_answer_is_complete():
    assert "no derives" in build_prompt("q?", CHUNKS[:1])


FACTS = {
    "articles": [
        {"id": "buzo_frisa_canguro", "name": "Buzo", "aliases": ["BUZO"], "price": 17800, "min_units": 6,
         "details": "", "valid_from": "2026-10-14", "source": "l.txt"},
    ],
    "rules": {
        "min_purchase": [{"value": 200000, "from": "2026-11-01", "source": "c.txt"}],
        "transfer_discount_pct": [{"value": 8, "from": "2026-11-01", "source": "c.txt"}],
        "free_shipping_from": [{"value": 400000, "from": "2026-06-01", "source": "c.md"}],
    },
}


def test_answer_injects_computed_quote_into_prompt():
    from modamayor.rag import answer

    seen = []

    def fake_generate(prompt):
        seen.append(prompt)
        if "article_id" in prompt and "JSON" in prompt:
            return '{"lines": [{"article_id": "buzo_frisa_canguro", "quantity": 40}], "payment": "transferencia", "zone": "caba"}'
        return "respuesta"

    out = answer("40 buzos por transferencia en CABA?", make_retriever(), k=2, today="2026-11-09",
                 generate=fake_generate, facts=FACTS)
    assert out == "respuesta"
    assert "$655.040" in seen[-1]


def test_answer_without_parsable_order_skips_calculation():
    from modamayor.rag import answer

    seen = []

    def fake_generate(prompt):
        seen.append(prompt)
        return "no es un pedido"

    answer("a que hora abren?", make_retriever(), k=2, today="2026-11-09", generate=fake_generate, facts=FACTS)
    assert "Cálculo verificado" not in seen[-1]


def test_answer_without_facts_makes_single_generation_call():
    from modamayor.rag import answer

    calls = []
    answer("buzo", make_retriever(), k=2, generate=lambda p: calls.append(p) or "ok")
    assert len(calls) == 1
