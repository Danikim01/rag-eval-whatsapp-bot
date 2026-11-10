import os
from collections.abc import Callable, Mapping

import httpx

OLLAMA_URL = "http://localhost:11434"
OLLAMA_GENERATOR = "qwen3:8b"
OLLAMA_EMBEDDER = "bge-m3"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_MAX_TOKENS = 1024

Generator = Callable[[str], str]
Embedder = Callable[[list[str]], list[list[float]]]


def _require(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if not value:
        raise RuntimeError(f"Missing env var: {name}")
    return value


def _post(client: httpx.Client, url: str, headers: dict, payload: dict, timeout: float) -> dict:
    response = client.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _ollama_generator(env, client) -> Generator:
    model = env.get("LLM_MODEL") or OLLAMA_GENERATOR
    url = env.get("OLLAMA_URL") or OLLAMA_URL

    def generate(prompt: str) -> str:
        data = _post(
            client,
            f"{url}/api/chat",
            {},
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "think": False,
                "options": {"temperature": 0},
            },
            300,
        )
        return data["message"]["content"].strip()

    return generate


def _openai_generator(env, client) -> Generator:
    model = _require(env, "LLM_MODEL")
    headers = {"Authorization": f"Bearer {_require(env, 'OPENAI_API_KEY')}"}

    def generate(prompt: str) -> str:
        data = _post(
            client,
            "https://api.openai.com/v1/chat/completions",
            headers,
            {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0},
            120,
        )
        return data["choices"][0]["message"]["content"].strip()

    return generate


def _anthropic_generator(env, client) -> Generator:
    model = _require(env, "LLM_MODEL")
    headers = {"x-api-key": _require(env, "ANTHROPIC_API_KEY"), "anthropic-version": ANTHROPIC_VERSION}

    def generate(prompt: str) -> str:
        data = _post(
            client,
            "https://api.anthropic.com/v1/messages",
            headers,
            {
                "model": model,
                "max_tokens": ANTHROPIC_MAX_TOKENS,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            },
            120,
        )
        return "".join(b["text"] for b in data["content"] if b.get("type") == "text").strip()

    return generate


GENERATORS = {"ollama": _ollama_generator, "openai": _openai_generator, "anthropic": _anthropic_generator}


def build_generator(env: Mapping[str, str] | None = None, client: httpx.Client | None = None) -> Generator:
    env = os.environ if env is None else env
    provider = env.get("LLM_PROVIDER") or "ollama"
    factory = GENERATORS.get(provider)
    if factory is None:
        raise RuntimeError(f"Unknown LLM_PROVIDER: {provider} (expected one of {', '.join(GENERATORS)})")
    return factory(env, client or httpx.Client())


def _ollama_embedder(env, client) -> Embedder:
    model = env.get("EMBED_MODEL") or OLLAMA_EMBEDDER
    url = env.get("OLLAMA_URL") or OLLAMA_URL

    def embed(texts: list[str]) -> list[list[float]]:
        return _post(client, f"{url}/api/embed", {}, {"model": model, "input": texts}, 120)["embeddings"]

    return embed


def _openai_embedder(env, client) -> Embedder:
    model = _require(env, "EMBED_MODEL")
    headers = {"Authorization": f"Bearer {_require(env, 'OPENAI_API_KEY')}"}

    def embed(texts: list[str]) -> list[list[float]]:
        data = _post(client, "https://api.openai.com/v1/embeddings", headers, {"model": model, "input": texts}, 120)
        return [row["embedding"] for row in sorted(data["data"], key=lambda r: r["index"])]

    return embed


EMBEDDERS = {"ollama": _ollama_embedder, "openai": _openai_embedder}


def build_embedder(env: Mapping[str, str] | None = None, client: httpx.Client | None = None) -> Embedder:
    env = os.environ if env is None else env
    provider = env.get("EMBED_PROVIDER") or "ollama"
    factory = EMBEDDERS.get(provider)
    if factory is None:
        raise RuntimeError(f"Unknown EMBED_PROVIDER: {provider} (expected one of {', '.join(EMBEDDERS)})")
    return factory(env, client or httpx.Client())
