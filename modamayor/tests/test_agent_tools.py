import pytest

from modamayor.agent.tools_catalog import (
    CotizarArgs,
    build_buscar_info,
    build_cotizar,
    build_derivar_a_humano,
    HANDOFF_SIGNAL,
    HANDOFF_COOLDOWN_SECONDS,
)
from modamayor.curation import format_quote, quote
from modamayor.loader import Chunk

TODAY = "2026-11-18"

FACTS = {
    "articles": [
        {
            "id": "buzo_frisa_canguro",
            "name": "Buzo de friza canguro",
            "aliases": ["BUZO FRISA CANG"],
            "price": 17800,
            "min_units": 6,
            "details": "Talles S al XXL.",
            "valid_from": "2026-10-14",
            "source": "lista.txt",
        },
        {
            "id": "remera_lisa",
            "name": "Remera lisa",
            "aliases": ["REM LISA ALG"],
            "price": 4800,
            "min_units": 12,
            "details": "Curva de 12.",
            "valid_from": "2026-10-14",
            "source": "lista.txt",
        },
        {
            "id": "campera_futura",
            "name": "Campera futura",
            "aliases": [],
            "price": 30000,
            "min_units": 1,
            "details": "",
            "valid_from": "2027-01-01",
            "source": "lista.txt",
        },
    ],
    "rules": {
        "min_purchase": [{"value": 200000, "from": "2026-06-01", "source": "c.md"}],
        "transfer_discount_pct": [{"value": 10, "from": "2026-06-01", "source": "c.md"}],
        "free_shipping_from": [{"value": 400000, "from": "2026-06-01", "source": "c.md"}],
    },
}


class FakeRetriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.calls = []

    def retrieve(self, question, k=4):
        self.calls.append((question, k))
        return self.chunks[:k]


def test_buscar_info_returns_chunk_text():
    retriever = FakeRetriever(
        [Chunk(id="a", text="Horario: lunes a viernes de 9 a 18.", source="faq.md"),
         Chunk(id="b", text="Aceptamos efectivo y transferencia.", source="faq.md")]
    )
    tool = build_buscar_info(retriever, k=2)
    out = tool.run({"consulta": "horario"})
    assert "Horario: lunes a viernes de 9 a 18." in out
    assert "Aceptamos efectivo y transferencia." in out
    assert retriever.calls == [("horario", 2)]


def test_buscar_info_without_results_says_so():
    tool = build_buscar_info(FakeRetriever([]), k=4)
    out = tool.run({"consulta": "algo"})
    assert out.strip() != ""
    assert "sin resultados" in out.lower()


def test_buscar_info_rejects_empty_query():
    tool = build_buscar_info(FakeRetriever([]), k=4)
    out = tool.run({"consulta": ""})
    assert out.startswith("Error en los argumentos de buscar_info")


def test_cotizar_total_comes_from_quote():
    tool = build_cotizar(FACTS, TODAY)
    out = tool.run(
        {"items": [{"article_id": "buzo_frisa_canguro", "cantidad": 12}],
         "payment": "transferencia", "zone": "caba"}
    )
    expected = format_quote(quote(FACTS, [("buzo_frisa_canguro", 12)], "transferencia", "caba", TODAY))
    assert out == expected
    assert "192.240" in out or "192240" in out


def test_cotizar_resolves_name_and_alias():
    tool = build_cotizar(FACTS, TODAY)
    by_id = tool.run({"items": [{"article_id": "remera_lisa", "cantidad": 24}]})
    by_alias = tool.run({"items": [{"article_id": "rem lisa alg", "cantidad": 24}]})
    by_name = tool.run({"items": [{"article_id": "Remera lisa", "cantidad": 24}]})
    assert by_id == by_alias == by_name


def test_cotizar_rejects_more_than_30_items():
    tool = build_cotizar(FACTS, TODAY)
    items = [{"article_id": "remera_lisa", "cantidad": 12}] * 31
    out = tool.run({"items": items})
    assert out.startswith("Error en los argumentos de cotizar")


def test_cotizar_accepts_exactly_30_items():
    tool = build_cotizar(FACTS, TODAY)
    items = [{"article_id": "remera_lisa", "cantidad": 12}] * 30
    out = tool.run({"items": items})
    assert not out.startswith("Error")


def test_cotizar_rejects_501_units_accepts_500():
    tool = build_cotizar(FACTS, TODAY)
    bad = tool.run({"items": [{"article_id": "remera_lisa", "cantidad": 501}]})
    ok = tool.run({"items": [{"article_id": "remera_lisa", "cantidad": 500}]})
    assert bad.startswith("Error en los argumentos de cotizar")
    assert not ok.startswith("Error")


@pytest.mark.parametrize("cantidad", [0, -3])
def test_cotizar_rejects_non_positive_units(cantidad):
    tool = build_cotizar(FACTS, TODAY)
    out = tool.run({"items": [{"article_id": "remera_lisa", "cantidad": cantidad}]})
    assert out.startswith("Error en los argumentos de cotizar")


def test_cotizar_rejects_empty_items():
    tool = build_cotizar(FACTS, TODAY)
    out = tool.run({"items": []})
    assert out.startswith("Error en los argumentos de cotizar")


def test_cotizar_unknown_article_returns_error_not_exception():
    tool = build_cotizar(FACTS, TODAY)
    out = tool.run({"items": [{"article_id": "inexistente", "cantidad": 6}]})
    assert "inexistente" in out
    assert out.startswith("Error")


def test_cotizar_article_not_yet_valid_is_unknown():
    tool = build_cotizar(FACTS, TODAY)
    out = tool.run({"items": [{"article_id": "campera_futura", "cantidad": 1}]})
    assert out.startswith("Error")


def test_cotizar_rejects_invalid_payment_and_zone():
    tool = build_cotizar(FACTS, TODAY)
    bad_payment = tool.run({"items": [{"article_id": "remera_lisa", "cantidad": 12}], "payment": "bitcoin"})
    bad_zone = tool.run({"items": [{"article_id": "remera_lisa", "cantidad": 12}], "zone": "marte"})
    assert bad_payment.startswith("Error en los argumentos de cotizar")
    assert bad_zone.startswith("Error en los argumentos de cotizar")


def test_cotizar_spec_exposes_limits_in_schema():
    schema = build_cotizar(FACTS, TODAY).spec()["parameters"]
    assert schema["properties"]["items"]["maxItems"] == 30
    assert CotizarArgs.model_fields["items"] is not None


class FakeClock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _derivar(clock: FakeClock, store: dict[str, float] | None = None, conversation: str = "conv-1"):
    return build_derivar_a_humano(conversation, clock=clock, store=store if store is not None else {})


def test_derivar_first_call_returns_handoff_signal():
    tool = _derivar(FakeClock())
    assert tool.run({"motivo": "quiere estampar su logo"}) == HANDOFF_SIGNAL


def test_derivar_second_call_within_hour_does_not_repeat():
    clock = FakeClock()
    tool = _derivar(clock)
    tool.run({"motivo": "reclamo"})
    clock.now += HANDOFF_COOLDOWN_SECONDS - 1
    result = tool.run({"motivo": "reclamo otra vez"})
    assert HANDOFF_SIGNAL not in result
    assert "derivaci" in result.lower()


def test_derivar_allowed_again_after_hour():
    clock = FakeClock()
    tool = _derivar(clock)
    tool.run({"motivo": "reclamo"})
    clock.now += HANDOFF_COOLDOWN_SECONDS
    assert tool.run({"motivo": "reclamo"}) == HANDOFF_SIGNAL


def test_derivar_cooldown_is_per_conversation():
    clock = FakeClock()
    store: dict[str, float] = {}
    a = _derivar(clock, store, "conv-a")
    b = _derivar(clock, store, "conv-b")
    a.run({"motivo": "reclamo"})
    assert b.run({"motivo": "reclamo"}) == HANDOFF_SIGNAL


def test_derivar_rejects_empty_and_too_long_motivo():
    tool = _derivar(FakeClock())
    assert tool.run({"motivo": ""}).startswith("Error en los argumentos de derivar_a_humano")
    assert tool.run({"motivo": "x" * 301}).startswith("Error en los argumentos de derivar_a_humano")


def test_derivar_schema_has_no_phone_argument():
    props = _derivar(FakeClock()).spec()["parameters"]["properties"]
    assert set(props) == {"motivo"}


def test_derivar_rejected_call_does_not_consume_cooldown():
    clock = FakeClock()
    tool = _derivar(clock)
    tool.run({"motivo": ""})
    assert tool.run({"motivo": "reclamo"}) == HANDOFF_SIGNAL
