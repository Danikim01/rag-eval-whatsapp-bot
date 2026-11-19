import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from modamayor.agent.provider import OllamaToolProvider, ToolProvider
from modamayor.agent.tools import Tool

THRESHOLD = 95.0
DOC_PATH = Path("docs/tool-calling-qwen3.md")
SYSTEM = (
    "Sos el asistente de un local mayorista de ropa. "
    "Si el cliente pide un precio o una cotización, usá la herramienta cotizar_juguete. "
    "Si solo saluda, agradece o pregunta algo general, respondé sin herramientas."
)


class JuguetesInput(BaseModel):
    producto: Literal["remera", "jean", "buzo", "campera"]
    cantidad: int = Field(gt=0, le=500)


def cotizar_juguete(args: JuguetesInput) -> str:
    """Cotiza una cantidad de un producto del catálogo de prueba.

    Args:
        producto: remera, jean, buzo o campera.
        cantidad: unidades entre 1 y 500.
    """
    return f"{args.cantidad} {args.producto}: ${args.cantidad * 1000}"


TOOL = Tool(
    name="cotizar_juguete",
    description="Cotiza una cantidad de un producto: remera, jean, buzo o campera.",
    input_model=JuguetesInput,
    fn=cotizar_juguete,
)


@dataclass(frozen=True)
class Case:
    prompt: str
    expected: tuple[str, int] | None


CASES: list[Case] = [
    Case("Cuánto salen 12 remeras?", ("remera", 12)),
    Case("Necesito precio de 30 jeans", ("jean", 30)),
    Case("pasame cotización de 5 buzos", ("buzo", 5)),
    Case("Cuánto me sale llevar 100 camperas?", ("campera", 100)),
    Case("quiero 24 remeras, cuánto es?", ("remera", 24)),
    Case("Precio por 8 jeans por favor", ("jean", 8)),
    Case("cotizame 50 buzos", ("buzo", 50)),
    Case("Che, cuánto 3 camperas?", ("campera", 3)),
    Case("Me interesan 200 remeras, a cuánto?", ("remera", 200)),
    Case("Buenas, me pasás el precio de 15 jeans?", ("jean", 15)),
    Case("cuanto x 10 buzos", ("buzo", 10)),
    Case("Cuánto sería por 1 campera?", ("campera", 1)),
    Case("Necesito 60 remeras para el sábado, qué precio tienen?", ("remera", 60)),
    Case("dame el total de 7 jeans", ("jean", 7)),
    Case("Cuánto cuestan 18 buzos?", ("buzo", 18)),
    Case("Hola, buen día!", None),
    Case("Gracias, ya está", None),
    Case("A qué hora abren mañana?", None),
    Case("Perfecto, después te aviso", None),
    Case("Qué tal, cómo andan?", None),
]


@dataclass(frozen=True)
class Outcome:
    prompt: str
    kind: str


def looks_like_format_failure(text: str) -> bool:
    lowered = text.lower()
    return any(m in lowered for m in ("<tool_call>", '"name"', '"arguments"', "cotizar_juguete(", "```json"))


def evaluate(case: Case, provider: ToolProvider) -> Outcome:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": case.prompt},
    ]
    reply = provider.chat(messages, [TOOL.spec()])
    if case.expected is None:
        return Outcome(case.prompt, "ok" if not reply.tool_calls else "falsa_llamada")
    if not reply.tool_calls:
        return Outcome(case.prompt, "formato" if looks_like_format_failure(reply.text) else "sin_llamada")
    call = reply.tool_calls[0]
    if call.name != TOOL.name:
        return Outcome(case.prompt, "tool_incorrecta")
    try:
        parsed = JuguetesInput.model_validate(call.arguments)
    except Exception:
        return Outcome(case.prompt, "formato")
    if (parsed.producto, parsed.cantidad) != case.expected:
        return Outcome(case.prompt, "argumentos_incorrectos")
    return Outcome(case.prompt, "ok")


def run_probe(provider: ToolProvider, cases: list[Case] = CASES) -> list[Outcome]:
    return [evaluate(case, provider) for case in cases]


def summarize(outcomes: list[Outcome]) -> tuple[float, Counter[str]]:
    counts = Counter(o.kind for o in outcomes)
    return 100.0 * counts["ok"] / len(outcomes), counts


def decision_text(pct: float, counts: Counter[str]) -> str:
    failures = sum(n for kind, n in counts.items() if kind != "ok")
    format_failures = counts["formato"]
    if pct >= THRESHOLD:
        return "Seguir con tool calling nativo. Se mide de nuevo con las 40 pruebas de la fase 5."
    if failures and format_failures * 2 >= failures:
        return (
            "Menos de 95% y al menos la mitad de las fallas son de formato. "
            "Plan B: salida JSON forzada con `format` para qwen3, y tool calling nativo solo para Haiku."
        )
    return (
        "Menos de 95% pero las fallas no son de formato. "
        "Revisar descripciones de la tool y el prompt antes de cambiar de enfoque."
    )


def render_doc(model: str, outcomes: list[Outcome], pct: float, counts: Counter[str]) -> str:
    lines = [
        "---",
        f"date: {date.today().isoformat()}",
        "project: Agencia-Automatizaciones",
        "type: probe",
        "tags: [avellaneda, agente, qwen3, tool-calling]",
        "---",
        "",
        "# Probe de tool calling con qwen3",
        "",
        f"Modelo: `{model}`.",
        f"Prompts: {len(outcomes)}, con una tool de juguete y temperatura 0.",
        "Comando: `python -m modamayor.agent.probe`.",
        "",
        f"## Resultado: {pct:.0f}%",
        "",
        "| Tipo | Cantidad |",
        "|---|---|",
    ]
    for kind, n in sorted(counts.items()):
        lines.append(f"| {kind} | {n} |")
    lines += ["", "## Decisión", "", decision_text(pct, counts), "", "## Fallas", ""]
    failed = [o for o in outcomes if o.kind != "ok"]
    if failed:
        lines += [f"- {o.kind}: {o.prompt}" for o in failed]
    else:
        lines.append("Ninguna.")
    return "\n".join(lines) + "\n"


def main() -> int:
    provider = OllamaToolProvider({})
    outcomes = run_probe(provider)
    pct, counts = summarize(outcomes)
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(render_doc(provider._model, outcomes, pct, counts), encoding="utf-8")
    print(f"acierto: {pct:.0f}% {dict(counts)}")
    print(decision_text(pct, counts))
    failures = sum(n for kind, n in counts.items() if kind != "ok")
    if pct < THRESHOLD and counts["formato"] * 2 >= failures:
        print("ADVERTENCIA: stop, decidir plan B antes de seguir", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
