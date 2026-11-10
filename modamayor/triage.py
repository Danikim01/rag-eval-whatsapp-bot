import re
from typing import Callable
from urllib.parse import quote as urlquote

from modamayor.scoring import HANDOFF_MARKER

CLARIFY_MARKER = "no te entendí bien"
ACTIONS = ("answer", "clarify", "handoff")

History = list[tuple[str, str]]

IDENTITY = (
    "Sos el asistente de WhatsApp de Casa Beltrán Mayorista, un negocio mayorista de ropa. "
    "Podés responder: precios y artículos de la lista, cantidades mínimas, compra mínima, formas de pago y descuentos, "
    "envíos, horarios, plazos, stock informado y política de cambios y devoluciones. "
    "La remera estampada es un artículo de la lista de precios. "
    "No podés resolver: pedidos personalizados (estampar o bordar el logo del cliente), reclamos, confirmar pedidos con dinero de por medio, "
    "facturación especial ni nada que no esté en la información del negocio."
)


def _format_history(history: History) -> str:
    if not history:
        return "Es el primer mensaje del cliente, el chat está vacío."
    lines = [f"{'Cliente' if role == 'user' else 'Asistente'}: {text}" for role, text in history]
    return "Conversación previa:\n" + "\n".join(lines)


def build_triage_prompt(question: str, history: History) -> str:
    return (
        f"{IDENTITY}\n\n"
        "Clasificá el último mensaje del cliente con UNA sola palabra:\n"
        "- answer: es un saludo, o una consulta del rubro que se puede responder con la información del negocio.\n"
        "- clarify: el tema no tiene que ver con ropa ni con el negocio (ej: de qué color es una naranja, cuánto cuesta una naranja, "
        "deportes), aunque use palabras como precio o cuánto cuesta; o es demasiado ambiguo para responder "
        "(ej: cuánto sale, sin decir qué artículo).\n"
        "- handoff: el cliente pide hablar con una persona, o es una consulta del rubro que el asistente no puede resolver "
        "(pedido personalizado, reclamo, confirmar un pedido con dinero).\n"
        "Juzgá el tema por lo que el cliente nombra: si nombra algo que no es ropa ni un servicio del negocio, es clarify, "
        "incluso si el asistente ya había pedido aclarar antes. "
        "Si pregunta precio o cantidad sin nombrar ningún artículo y el mensaje previo no lo aclara, también es clarify.\n"
        "Respondé solo answer, clarify o handoff.\n\n"
        f"{_format_history(history)}\n\n"
        f"Último mensaje del cliente: {question}"
    )


def parse_action(raw: str) -> str:
    match = re.search(r"\b(answer|clarify|handoff)\b", raw.lower())
    return match.group(1) if match else "answer"


def resolve_action(action: str, history: History) -> str:
    if action != "clarify":
        return action
    last_assistant = next((text for role, text in reversed(history) if role == "assistant"), None)
    if last_assistant and CLARIFY_MARKER in last_assistant:
        return "handoff"
    return action


def triage(question: str, history: History, generate: Callable[[str], str]) -> str:
    return resolve_action(parse_action(generate(build_triage_prompt(question, history))), history)


def owner_link(owner_number: str, question: str, reason: str) -> str:
    text = f"Hola, vengo del asistente. Mi consulta: {question} (motivo: {reason})"
    return f"https://wa.me/{owner_number}?text={urlquote(text)}"


def clarify_message() -> str:
    return (
        f"Perdón, {CLARIFY_MARKER}. Puedo ayudarte con precios, mínimos de compra, formas de pago, envíos y horarios. "
        "¿Me contás qué necesitás?"
    )


def handoff_message(owner_number: str, question: str, reason: str) -> str:
    return (
        f"Para esto {HANDOFF_MARKER}. Escribile directo acá y ya le llega tu consulta: "
        f"{owner_link(owner_number, question, reason)}"
    )


def text_only_message(owner_number: str) -> str:
    return (
        "Por ahora solo puedo leer mensajes de texto. Escribime tu consulta, "
        f"o si preferís hablar con una persona, escribile directo acá: https://wa.me/{owner_number}"
    )
