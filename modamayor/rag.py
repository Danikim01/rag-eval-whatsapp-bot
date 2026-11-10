from typing import Callable

from modamayor.curation import format_quote, parse_order, quote
from modamayor.llm import Embedder, build_generator
from modamayor.loader import Chunk
from modamayor.scoring import HANDOFF_MARKER


class Retriever:
    def __init__(self, client, embed: Embedder, name: str, chunks: list[Chunk]):
        self._embed = embed
        self._by_id = {c.id: c for c in chunks}
        try:
            client.delete_collection(name)
        except Exception:
            pass
        self._collection = client.create_collection(name, metadata={"hnsw:space": "cosine"})
        self._collection.add(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            embeddings=embed([c.text for c in chunks]),
            metadatas=[{"source": c.source, "date": c.date or ""} for c in chunks],
        )

    def retrieve(self, question: str, k: int = 4) -> list[Chunk]:
        result = self._collection.query(
            query_embeddings=self._embed([question]),
            n_results=min(k, len(self._by_id)),
        )
        return [self._by_id[i] for i in result["ids"][0]]


def build_prompt(
    question: str,
    chunks: list[Chunk],
    today: str | None = None,
    verified: str | None = None,
    history: list[tuple[str, str]] | None = None,
) -> str:
    context = "\n\n".join(
        f"[fuente: {c.source}{f', fecha: {c.date}' if c.date else ''}]\n{c.text}" for c in chunks
    )
    date_line = f"Fecha de hoy: {today}\n" if today else ""
    verified_block = (
        f"Cálculo verificado (hecho por el sistema, usalo tal cual, no lo recalcules y mencioná en la respuesta los montos que correspondan): {verified}\n\n"
        if verified
        else ""
    )
    history_block = (
        "Conversación previa:\n"
        + "\n".join(f"{'Cliente' if r == 'user' else 'Asistente'}: {t}" for r, t in history)
        + "\n\n"
        if history
        else ""
    )
    return (
        "Sos el asistente de WhatsApp de un negocio mayorista de ropa. "
        "Respondé en español rioplatense, breve y claro, usando solo la información del contexto.\n"
        f"Si el contexto no alcanza para responder, respondé exactamente que no tenés ese dato y que "
        f"{HANDOFF_MARKER}.\n"
        f"Si el contexto alcanza para responder completo, respondé y no derives a una persona.\n"
        "Si el cliente solo saluda, saludá brevemente y contale que podés ayudar con precios, mínimos de compra, formas de pago, envíos y horarios, sin derivar.\n"
        f"{date_line}\n"
        f"Contexto:\n{context}\n\n"
        f"{verified_block}"
        f"{history_block}"
        f"Pregunta del cliente: {question}"
    )


def build_order_prompt(question: str, facts: dict) -> str:
    catalog = "\n".join(f"- {a['id']}: {a['name']} ({', '.join(a['aliases'])})" for a in facts["articles"])
    return (
        "Extraé el pedido del cliente y devolvé SOLO un JSON, sin texto extra, con esta forma: "
        '{"lines": [{"article_id": "...", "quantity": 0}], "payment": "efectivo|transferencia|null", '
        '"zone": "caba|gba|interior|null"}.\n'
        "Usá únicamente article_id del catálogo. quantity es en unidades sueltas: una curva de remeras son 12 unidades, "
        "una docena son 12, un pack son las unidades mínimas del artículo. Si el cliente no menciona cantidades concretas de artículos, "
        'devolvé {"lines": [], "payment": null, "zone": null}. '
        "Si no menciona forma de pago o zona, usá null.\n"
        f"Catálogo:\n{catalog}\n\n"
        f"Mensaje del cliente: {question}"
    )


def answer(
    question: str,
    retriever: Retriever,
    k: int = 4,
    today: str | None = None,
    generate: Callable[[str], str] | None = None,
    facts: dict | None = None,
    history: list[tuple[str, str]] | None = None,
) -> str:
    generate = generate or build_generator()
    chunks = retriever.retrieve(question, k=k)
    verified = None
    if facts is not None and today is not None:
        order = parse_order(generate(build_order_prompt(question, facts)), facts)
        if order:
            verified = format_quote(quote(facts, order["lines"], order["payment"], order["zone"], today))
    return generate(build_prompt(question, chunks, today=today, verified=verified, history=history))
