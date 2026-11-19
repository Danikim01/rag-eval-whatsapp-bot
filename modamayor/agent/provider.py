import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from modamayor.llm import (
    ANTHROPIC_MAX_TOKENS,
    ANTHROPIC_VERSION,
    OLLAMA_GENERATOR,
    OLLAMA_URL,
    _post,
    _require,
)


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class AssistantMessage:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


class ToolProvider(Protocol):
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> AssistantMessage: ...


class OllamaToolProvider:
    def __init__(self, env: Mapping[str, str], client: httpx.Client | None = None) -> None:
        self._model = env.get("LLM_MODEL") or OLLAMA_GENERATOR
        self._url = env.get("OLLAMA_URL") or OLLAMA_URL
        self._client = client or httpx.Client()

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> AssistantMessage:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [_ollama_message(m) for m in messages],
            "stream": False,
            "think": False,
            "options": {"temperature": 0},
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters"],
                    },
                }
                for t in tools
            ]
        data = _post(self._client, f"{self._url}/api/chat", {}, payload, 300)
        message = data["message"]
        calls = [
            ToolCall(id=f"call_{i}", name=c["function"]["name"], arguments=c["function"].get("arguments") or {})
            for i, c in enumerate(message.get("tool_calls") or [])
        ]
        return AssistantMessage(text=(message.get("content") or "").strip(), tool_calls=calls)


def _ollama_message(message: dict[str, Any]) -> dict[str, Any]:
    role = message["role"]
    if role == "tool":
        return {"role": "tool", "tool_name": message["name"], "content": message["content"]}
    calls = message.get("tool_calls")
    if role == "assistant" and calls:
        return {
            "role": "assistant",
            "content": message.get("content", ""),
            "tool_calls": [{"function": {"name": c.name, "arguments": c.arguments}} for c in calls],
        }
    return {"role": role, "content": message["content"]}


class AnthropicToolProvider:
    def __init__(self, env: Mapping[str, str], client: httpx.Client | None = None) -> None:
        self._model = _require(env, "LLM_MODEL")
        self._headers = {"x-api-key": _require(env, "ANTHROPIC_API_KEY"), "anthropic-version": ANTHROPIC_VERSION}
        self._client = client or httpx.Client()

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> AssistantMessage:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
            "temperature": 0,
            "messages": _anthropic_messages(messages),
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [
                {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools
            ]
        data = _post(self._client, "https://api.anthropic.com/v1/messages", self._headers, payload, 120)
        blocks = data["content"]
        text = "".join(b["text"] for b in blocks if b.get("type") == "text").strip()
        calls = [
            ToolCall(id=b["id"], name=b["name"], arguments=b.get("input") or {})
            for b in blocks
            if b.get("type") == "tool_use"
        ]
        return AssistantMessage(text=text, tool_calls=calls)


def _anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m["role"]
        if role == "system":
            continue
        if role == "tool":
            block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
            last = out[-1] if out else None
            if last and last["role"] == "user" and isinstance(last["content"], list):
                last["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
            continue
        calls = m.get("tool_calls")
        if role == "assistant" and calls:
            content: list[dict[str, Any]] = []
            if m.get("content"):
                content.append({"type": "text", "text": m["content"]})
            content.extend({"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments} for c in calls)
            out.append({"role": "assistant", "content": content})
            continue
        out.append({"role": role, "content": m["content"]})
    return out


TOOL_PROVIDERS = {"ollama": OllamaToolProvider, "anthropic": AnthropicToolProvider}


def build_tool_provider(env: Mapping[str, str] | None = None, client: httpx.Client | None = None) -> ToolProvider:
    env = os.environ if env is None else env
    name = env.get("LLM_PROVIDER") or "ollama"
    factory = TOOL_PROVIDERS.get(name)
    if factory is None:
        raise RuntimeError(f"Unknown LLM_PROVIDER: {name} (expected one of {', '.join(TOOL_PROVIDERS)})")
    return factory(env, client)
