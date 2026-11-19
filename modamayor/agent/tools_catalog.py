import time
from typing import Callable, Literal

from pydantic import BaseModel, Field

from modamayor.agent.tools import Tool
from modamayor.curation import format_quote, quote
from modamayor.rag import Retriever

MAX_ITEMS = 30
MAX_UNITS = 500
HANDOFF_SIGNAL = "HANDOFF_SOLICITADO"
HANDOFF_COOLDOWN_SECONDS = 3600
HANDOFF_REPEAT_NOTICE = (
    "La derivacion ya fue solicitada hace menos de una hora para esta conversacion. "
    "No la repitas: avisale al cliente que una persona del equipo ya tiene su consulta."
)


class BuscarInfoArgs(BaseModel):
    consulta: str = Field(min_length=1, max_length=500, description="Pregunta o tema a buscar en la base de conocimiento")


class Item(BaseModel):
    article_id: str = Field(min_length=1, description="Id, nombre o alias del articulo")
    cantidad: int = Field(ge=1, le=MAX_UNITS, description="Unidades pedidas")


class DerivarArgs(BaseModel):
    motivo: str = Field(min_length=1, max_length=300, description="Motivo breve de la derivacion")


class CotizarArgs(BaseModel):
    items: list[Item] = Field(min_length=1, max_length=MAX_ITEMS, description="Articulos y cantidades a cotizar")
    payment: Literal["efectivo", "transferencia"] | None = Field(default=None, description="Forma de pago")
    zone: Literal["caba", "gba", "interior"] | None = Field(default=None, description="Zona de entrega")


def build_buscar_info(retriever: Retriever, k: int) -> Tool:
    def buscar_info(args: BuscarInfoArgs) -> str:
        """Busca informacion del negocio (horarios, politicas, articulos, precios). Arg consulta: texto a buscar."""
        chunks = retriever.retrieve(args.consulta, k=k)
        if not chunks:
            return "Sin resultados para esa consulta."
        return "\n\n".join(c.text for c in chunks)

    return Tool("buscar_info", buscar_info.__doc__ or "", BuscarInfoArgs, buscar_info)


def build_cotizar(facts: dict, today: str) -> Tool:
    def cotizar(args: CotizarArgs) -> str:
        """Cotiza un pedido con precios vigentes; el total lo calcula el sistema. Args: items (article_id, cantidad), payment, zone."""
        lookup: dict[str, str] = {}
        for article in facts.get("articles", []):
            if article["valid_from"] > today:
                continue
            for key in [article["id"], article["name"], *article.get("aliases", [])]:
                lookup[key.strip().lower()] = article["id"]
        lines: list[tuple[str, int]] = []
        for item in args.items:
            resolved = lookup.get(item.article_id.strip().lower())
            if resolved is None:
                return f"Error: articulo '{item.article_id}' no encontrado o no vigente. Usa buscar_info para ver el id correcto."
            lines.append((resolved, item.cantidad))
        return format_quote(quote(facts, lines, args.payment, args.zone, today))

    return Tool("cotizar", cotizar.__doc__ or "", CotizarArgs, cotizar)


def build_derivar_a_humano(
    conversation_id: str,
    clock: Callable[[], float] = time.time,
    store: dict[str, float] | None = None,
) -> Tool:
    last_handoff: dict[str, float] = store if store is not None else {}

    def derivar_a_humano(args: DerivarArgs) -> str:
        """Deriva la conversacion a una persona del equipo (reclamos, pedidos personalizados, confirmar pedidos). Arg motivo: razon breve."""
        now = clock()
        previous = last_handoff.get(conversation_id)
        if previous is not None and now - previous < HANDOFF_COOLDOWN_SECONDS:
            return HANDOFF_REPEAT_NOTICE
        last_handoff[conversation_id] = now
        return HANDOFF_SIGNAL

    return Tool("derivar_a_humano", derivar_a_humano.__doc__ or "", DerivarArgs, derivar_a_humano)
