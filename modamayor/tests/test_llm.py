import json

import httpx
import pytest

from modamayor.llm import build_embedder, build_generator


def client_returning(payload, seen):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


def body(request):
    return json.loads(request.content)


def test_ollama_generator_posts_chat_and_returns_stripped_content():
    seen = []
    c = client_returning({"message": {"content": "  hola  "}}, seen)
    generate = build_generator({"LLM_PROVIDER": "ollama"}, client=c)
    assert generate("pregunta") == "hola"
    assert str(seen[0].url).endswith("/api/chat")
    assert body(seen[0])["messages"] == [{"role": "user", "content": "pregunta"}]
    assert body(seen[0])["options"]["temperature"] == 0


def test_default_provider_is_ollama():
    seen = []
    c = client_returning({"message": {"content": "x"}}, seen)
    assert build_generator({}, client=c)("p") == "x"
    assert str(seen[0].url).startswith("http://localhost:11434")


def test_openai_generator_sends_bearer_and_parses_choice():
    seen = []
    c = client_returning({"choices": [{"message": {"content": "ok "}}]}, seen)
    env = {"LLM_PROVIDER": "openai", "LLM_MODEL": "m1", "OPENAI_API_KEY": "k"}
    assert build_generator(env, client=c)("p") == "ok"
    assert str(seen[0].url) == "https://api.openai.com/v1/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer k"
    assert body(seen[0])["model"] == "m1"
    assert body(seen[0])["temperature"] == 0


def test_anthropic_generator_sends_key_version_and_parses_text():
    seen = []
    c = client_returning({"content": [{"type": "text", "text": " listo "}]}, seen)
    env = {"LLM_PROVIDER": "anthropic", "LLM_MODEL": "m2", "ANTHROPIC_API_KEY": "k"}
    assert build_generator(env, client=c)("p") == "listo"
    assert str(seen[0].url) == "https://api.anthropic.com/v1/messages"
    assert seen[0].headers["x-api-key"] == "k"
    assert seen[0].headers["anthropic-version"] == "2023-06-01"
    assert body(seen[0])["max_tokens"] > 0
    assert body(seen[0])["messages"] == [{"role": "user", "content": "p"}]


@pytest.mark.parametrize("provider,key", [("openai", "OPENAI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")])
def test_cloud_provider_requires_model_and_key(provider, key):
    with pytest.raises(RuntimeError, match="LLM_MODEL"):
        build_generator({"LLM_PROVIDER": provider, key: "k"})
    with pytest.raises(RuntimeError, match=key):
        build_generator({"LLM_PROVIDER": provider, "LLM_MODEL": "m"})


def test_unknown_provider_is_rejected():
    with pytest.raises(RuntimeError, match="LLM_PROVIDER"):
        build_generator({"LLM_PROVIDER": "nope"})


def test_http_error_propagates():
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, json={})))
    with pytest.raises(httpx.HTTPStatusError):
        build_generator({}, client=c)("p")


def test_ollama_embedder_returns_embeddings():
    seen = []
    c = client_returning({"embeddings": [[1.0, 2.0]]}, seen)
    assert build_embedder({}, client=c)(["a"]) == [[1.0, 2.0]]
    assert str(seen[0].url).endswith("/api/embed")
    assert body(seen[0])["input"] == ["a"]


def test_openai_embedder_orders_by_index():
    seen = []
    payload = {"data": [{"index": 1, "embedding": [2.0]}, {"index": 0, "embedding": [1.0]}]}
    c = client_returning(payload, seen)
    env = {"EMBED_PROVIDER": "openai", "EMBED_MODEL": "e1", "OPENAI_API_KEY": "k"}
    assert build_embedder(env, client=c)(["a", "b"]) == [[1.0], [2.0]]
    assert str(seen[0].url) == "https://api.openai.com/v1/embeddings"


def test_anthropic_has_no_embedder():
    with pytest.raises(RuntimeError, match="EMBED_PROVIDER"):
        build_embedder({"EMBED_PROVIDER": "anthropic"})
