from pathlib import Path

from modamayor.loader import Chunk, chunk_chat, chunk_markdown, chunk_pricelist, load_chunks

DOCS = Path(__file__).resolve().parent.parent / "docs"

MD = """# Condiciones de venta - Casa X

## Atencion

Lunes a viernes de 9 a 18.

## Compra minima

La compra minima es de $250.000.
"""

PRICELIST = """CASA X
LISTA DE PRECIOS - OCTUBRE 2026

ARTICULO     PRECIO   MIN
REM LISA     4800     curva x12
BUZO FRISA   17800    x6

Curva remeras: 3 S - 3 M - 3 L - 3 XL
Talles jean hombre: 38 al 48
"""

CHAT = """[28/10/2026 09:12] Beltran: ojo con lo siguiente
[28/10/2026 09:13] Beltran: el descuento ya no es 10, es 8%
[29/10/2026 10:00] Marcela: ok
"""


def test_markdown_splits_by_section_and_keeps_title():
    chunks = chunk_markdown(MD, source="cond.md")
    assert len(chunks) == 2
    assert all("Condiciones de venta" in c.text for c in chunks)
    assert "Compra minima" in chunks[1].text
    assert "$250.000" in chunks[1].text
    assert "$250.000" not in chunks[0].text
    assert all(c.source == "cond.md" and c.date is None for c in chunks)


def test_pricelist_blocks_carry_header_and_month_from_filename():
    chunks = chunk_pricelist(PRICELIST, source="lista_precios_oct2026.txt")
    assert len(chunks) == 2
    assert all("OCTUBRE 2026" in c.text for c in chunks)
    assert "BUZO FRISA   17800" in chunks[0].text
    assert "3 S - 3 M" in chunks[1].text
    assert {c.date for c in chunks} == {"2026-10"}


def test_pricelist_month_parsed_for_other_months():
    chunks = chunk_pricelist("Lista\nprecios\n\nREM 3900 x12\n", source="lista_precios_jun2026.txt")
    assert {c.date for c in chunks} == {"2026-06"}


def test_chat_one_chunk_per_message_with_iso_date():
    chunks = chunk_chat(CHAT, source="chat.txt")
    assert len(chunks) == 3
    assert chunks[0].date == "2026-10-28"
    assert chunks[2].date == "2026-10-29"
    assert "8%" in chunks[1].text
    assert "Beltran" in chunks[1].text


def test_chat_continuation_lines_join_previous_message():
    chunks = chunk_chat("[28/10/2026 09:12] A: hola\nsigue aca\n[28/10/2026 09:13] B: ok\n", source="c.txt")
    assert len(chunks) == 2
    assert "sigue aca" in chunks[0].text


def test_load_chunks_has_unique_ids_and_all_sources():
    chunks = load_chunks(DOCS)
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))
    assert {c.source for c in chunks} == {
        "condiciones_de_venta.md",
        "lista_precios_jun2026.txt",
        "lista_precios_oct2026.txt",
        "chat_dueno_whatsapp.txt",
    }
    assert all(isinstance(c, Chunk) and c.text.strip() for c in chunks)
