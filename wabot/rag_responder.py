import os
from datetime import date

import chromadb

from modamayor.agent.provider import build_tool_provider
from modamayor.bot import reply
from modamayor.curation import build_chunks, load_facts
from modamayor.llm import build_embedder, build_generator
from modamayor.rag import Retriever
from modamayor.run_eval import FACTS_PATH


def build_responder(owner_number: str):
    today = os.environ.get("WABOT_TODAY") or date.today().isoformat()
    facts = load_facts(FACTS_PATH)
    generate = build_generator()
    provider = build_tool_provider() if os.environ.get("WABOT_AGENT") == "1" else None
    retriever = Retriever(chromadb.EphemeralClient(), build_embedder(), "modamayor", build_chunks(facts, today))

    def respond(text: str, history: list[tuple[str, str]]) -> str:
        return reply(text, history, owner_number, retriever, generate, today=today, facts=facts, provider=provider)

    return respond
