import pytest

from modamayor.curation import build_chunks, current_value, quote

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
            "source": "lista_precios_oct2026.txt",
        },
        {
            "id": "remera_lisa",
            "name": "Remera lisa de algodón cuello redondo",
            "aliases": ["REM LISA ALG"],
            "price": 4800,
            "min_units": 12,
            "details": "Se vende por curva de 12: 3 S, 3 M, 3 L, 3 XL.",
            "valid_from": "2026-10-14",
            "source": "lista_precios_oct2026.txt",
        },
        {
            "id": "jean_clasico_hombre",
            "name": "Jean clásico de hombre, corte recto",
            "aliases": ["JN CLAS H"],
            "price": 19500,
            "min_units": 6,
            "details": "Talles 38 al 48.",
            "valid_from": "2026-10-14",
            "source": "lista_precios_oct2026.txt",
        },
    ],
    "rules": {
        "min_purchase": [
            {"value": 250000, "from": "2026-06-01", "source": "condiciones_de_venta.md"},
            {"value": 200000, "from": "2026-11-01", "source": "chat_dueno_whatsapp.txt"},
        ],
        "transfer_discount_pct": [
            {"value": 10, "from": "2026-06-01", "source": "condiciones_de_venta.md"},
            {"value": 8, "from": "2026-11-01", "source": "chat_dueno_whatsapp.txt"},
        ],
        "free_shipping_from": [
            {"value": 400000, "from": "2026-06-01", "source": "condiciones_de_venta.md"},
        ],
    },
    "stock": [
        {
            "id": "jean_clasico_negro_46",
            "text": "El jean clásico de hombre negro talle 46 está agotado, reingresa aproximadamente el 20/11.",
            "from": "2026-10-28",
            "source": "chat_dueno_whatsapp.txt",
        }
    ],
    "policies": [
        {
            "id": "atencion",
            "text": "Atendemos de lunes a viernes de 9 a 18 hs y sábados de 9 a 13 hs.",
            "from": "2026-06-01",
            "source": "condiciones_de_venta.md",
        }
    ],
}


def test_current_value_picks_latest_not_after_today():
    timeline = FACTS["rules"]["min_purchase"]
    assert current_value(timeline, "2026-10-30")["value"] == 250000
    assert current_value(timeline, "2026-11-01")["value"] == 200000
    assert current_value(timeline, "2026-11-09")["value"] == 200000


def test_current_value_none_before_first_entry():
    assert current_value(FACTS["rules"]["min_purchase"], "2026-01-01") is None


def test_article_chunk_has_expanded_name_alias_price_and_min():
    chunks = {c.id: c for c in build_chunks(FACTS, "2026-11-09")}
    chunk = chunks["article:buzo_frisa_canguro"]
    assert "Buzo de friza canguro" in chunk.text
    assert "BUZO FRISA CANG" in chunk.text
    assert "$17.800" in chunk.text
    assert "6 unidades" in chunk.text
    assert "Talles S al XXL" in chunk.text
    assert chunk.source == "lista_precios_oct2026.txt"
    assert chunk.date == "2026-10-14"


def test_rules_chunks_use_values_in_force_today():
    after = " ".join(c.text for c in build_chunks(FACTS, "2026-11-09"))
    before = " ".join(c.text for c in build_chunks(FACTS, "2026-10-30"))
    assert "$200.000" in after and "$250.000" not in after
    assert "8%" in after and "10%" not in after
    assert "$250.000" in before and "$200.000" not in before


def test_rules_chunk_carries_source_of_winning_value():
    chunks = {c.id: c for c in build_chunks(FACTS, "2026-11-09")}
    assert chunks["rule:min_purchase"].source == "chat_dueno_whatsapp.txt"
    assert chunks["rule:min_purchase"].date == "2026-11-01"


def test_stock_and_policy_chunks_present():
    chunks = {c.id: c for c in build_chunks(FACTS, "2026-11-09")}
    assert "agotado" in chunks["stock:jean_clasico_negro_46"].text
    assert chunks["policy:atencion"].source == "condiciones_de_venta.md"


def test_future_dated_items_are_excluded():
    chunk_ids = {c.id for c in build_chunks(FACTS, "2026-10-01")}
    assert "article:buzo_frisa_canguro" not in chunk_ids
    assert "stock:jean_clasico_negro_46" not in chunk_ids


def test_quote_transfer_discount():
    result = quote(FACTS, [("buzo_frisa_canguro", 40)], payment="transferencia", zone="caba", today="2026-11-09")
    assert result["subtotal"] == 712000
    assert result["discount"] == 56960
    assert result["total"] == 655040
    assert result["meets_min"] is True
    assert result["free_shipping"] is True


def test_quote_cash_free_shipping_caba():
    result = quote(FACTS, [("jean_clasico_hombre", 25)], payment="efectivo", zone="caba", today="2026-11-09")
    assert result["subtotal"] == 487500
    assert result["discount"] == 0
    assert result["total"] == 487500
    assert result["free_shipping"] is True


def test_quote_below_minimum_purchase():
    result = quote(FACTS, [("remera_lisa", 12)], payment="efectivo", zone="caba", today="2026-11-09")
    assert result["subtotal"] == 57600
    assert result["meets_min"] is False
    assert result["free_shipping"] is False


def test_quote_flags_quantity_below_article_minimum():
    result = quote(FACTS, [("buzo_frisa_canguro", 3)], payment="efectivo", zone="caba", today="2026-11-09")
    assert result["below_article_min"] == ["buzo_frisa_canguro"]


def test_quote_interior_never_free_shipping():
    result = quote(FACTS, [("jean_clasico_hombre", 25)], payment="efectivo", zone="interior", today="2026-11-09")
    assert result["free_shipping"] is False


def test_quote_unknown_article_raises():
    with pytest.raises(KeyError):
        quote(FACTS, [("pantufla", 1)], payment="efectivo", zone="caba", today="2026-11-09")


def test_parse_order_extracts_known_lines_and_defaults():
    from modamayor.curation import parse_order

    raw = 'ok {"lines": [{"article_id": "buzo_frisa_canguro", "quantity": 40}], "payment": "transferencia", "zone": "caba"}'
    order = parse_order(raw, FACTS)
    assert order == {"lines": [("buzo_frisa_canguro", 40)], "payment": "transferencia", "zone": "caba"}


def test_parse_order_drops_unknown_articles_and_bad_quantities():
    from modamayor.curation import parse_order

    raw = '{"lines": [{"article_id": "pantufla", "quantity": 2}, {"article_id": "remera_lisa", "quantity": 0}], "payment": "efectivo", "zone": "caba"}'
    assert parse_order(raw, FACTS) is None


def test_parse_order_none_on_garbage():
    from modamayor.curation import parse_order

    assert parse_order("no se", FACTS) is None
    assert parse_order("{rota", FACTS) is None


def test_parse_order_unknown_payment_and_zone_become_none():
    from modamayor.curation import parse_order

    raw = '{"lines": [{"article_id": "remera_lisa", "quantity": 12}], "payment": "bitcoin", "zone": "marte"}'
    order = parse_order(raw, FACTS)
    assert order["payment"] is None and order["zone"] is None


def test_quote_with_unknown_payment_and_zone_applies_no_discount_or_shipping():
    result = quote(FACTS, [("jean_clasico_hombre", 25)], payment=None, zone=None, today="2026-11-09")
    assert result["discount"] == 0
    assert result["free_shipping"] is False


def test_format_quote_has_exact_numbers():
    from modamayor.curation import format_quote

    result = quote(FACTS, [("buzo_frisa_canguro", 40)], payment="transferencia", zone="caba", today="2026-11-09")
    text = format_quote(result)
    assert "$712.000" in text and "$56.960" in text and "$655.040" in text
    assert "alcanza la compra mínima" in text
    assert "envío gratis" in text


def test_format_quote_reports_below_minimum():
    from modamayor.curation import format_quote

    result = quote(FACTS, [("remera_lisa", 12)], payment="efectivo", zone="caba", today="2026-11-09")
    text = format_quote(result)
    assert "$57.600" in text
    assert "NO alcanza la compra mínima" in text
    assert "$200.000" in text


def test_parse_order_resolves_alias_and_name_to_article_id():
    from modamayor.curation import parse_order

    raw = '{"lines": [{"article_id": "BUZO FRISA CANG", "quantity": 40}, {"article_id": "buzo de friza canguro", "quantity": 2}], "payment": "efectivo", "zone": "caba"}'
    order = parse_order(raw, FACTS)
    assert order["lines"] == [("buzo_frisa_canguro", 40), ("buzo_frisa_canguro", 2)]


def test_format_quote_mentions_discount_percentage():
    from modamayor.curation import format_quote

    result = quote(FACTS, [("buzo_frisa_canguro", 40)], payment="transferencia", zone=None, today="2026-11-09")
    assert "8%" in format_quote(result)


def test_format_quote_omits_shipping_verdict_when_zone_unknown():
    from modamayor.curation import format_quote

    result = quote(FACTS, [("buzo_frisa_canguro", 40)], payment="transferencia", zone=None, today="2026-11-09")
    text = format_quote(result)
    assert "NO corresponde" not in text and "No corresponde" not in text
    assert "$400.000" in text
