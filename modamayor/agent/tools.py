from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    fn: Callable[[Any], str]

    def spec(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_model.model_json_schema(),
        }

    def run(self, arguments: dict[str, Any]) -> str:
        try:
            parsed = self.input_model.model_validate(arguments)
        except ValidationError as exc:
            return format_validation_error(self.name, exc)
        return self.fn(parsed)


def format_validation_error(name: str, exc: ValidationError) -> str:
    problems = "; ".join(
        f"{'.'.join(str(p) for p in e['loc']) or 'entrada'}: {e['msg']}" for e in exc.errors()
    )
    return f"Error en los argumentos de {name}: {problems}. Corregí la llamada y reintentá."
