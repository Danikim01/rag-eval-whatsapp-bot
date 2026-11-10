import json
import re
from pathlib import Path

from modamayor.loader import Chunk

FREE_SHIPPING_ZONES = {"caba", "gba"}


def load_facts(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def current_value(timeline: list[dict], today: str) -> dict | None:
    valid = [entry for entry in timeline if entry["from"] <= today]
    return max(valid, key=lambda entry: entry["from"]) if valid else None


def money(amount: int) -> str:
    return "$" + f"{amount:,}".replace(",", ".")


def _article_chunk(article: dict) -> Chunk:
    aliases = ", ".join(article["aliases"])
    text = (
        f"{article['name']} (en la lista: {aliases}): {money(article['price'])} por unidad, "
        f"mínimo {article['min_units']} unidades por compra. {article['details']}"
    ).strip()
    return Chunk(f"article:{article['id']}", text, article["source"], article["valid_from"])


def _rule_chunks(rules: dict, today: str) -> list[Chunk]:
    chunks = []
    entry = current_value(rules.get("min_purchase", []), today)
    if entry:
        text = (
            f"Compra mínima: {money(entry['value'])} por pedido, sumando todos los artículos. "
            "Además cada artículo se vende por su cantidad mínima (curva o pack) según la lista de precios."
        )
        chunks.append(Chunk("rule:min_purchase", text, entry["source"], entry["from"]))
    discount = current_value(rules.get("transfer_discount_pct", []), today)
    if discount:
        text = (
            "Formas de pago: aceptamos efectivo y transferencia bancaria. No aceptamos tarjetas de crédito "
            f"ni débito ni cheques. Pagando por transferencia hay {discount['value']}% de descuento sobre el total."
        )
        chunks.append(Chunk("rule:payment", text, discount["source"], discount["from"]))
    shipping = current_value(rules.get("free_shipping_from", []), today)
    if shipping:
        text = (
            f"Envíos: envío gratis a CABA y GBA en compras desde {money(shipping['value'])}. "
            "Al interior se despacha por el transporte que elija el cliente y el flete lo paga el cliente al recibir."
        )
        chunks.append(Chunk("rule:shipping", text, shipping["source"], shipping["from"]))
    return chunks


def build_chunks(facts: dict, today: str) -> list[Chunk]:
    chunks = [_article_chunk(a) for a in facts.get("articles", []) if a["valid_from"] <= today]
    chunks += _rule_chunks(facts.get("rules", {}), today)
    for kind, key in (("stock", "stock"), ("policy", "policies")):
        for item in facts.get(key, []):
            if item["from"] <= today:
                chunks.append(Chunk(f"{kind}:{item['id']}", item["text"], item["source"], item["from"]))
    return chunks


def quote(facts: dict, lines: list[tuple[str, int]], payment: str | None, zone: str | None, today: str) -> dict:
    articles = {a["id"]: a for a in facts["articles"] if a["valid_from"] <= today}
    rules = facts["rules"]
    subtotal = 0
    below_article_min = []
    for article_id, quantity in lines:
        article = articles[article_id]
        subtotal += article["price"] * quantity
        if quantity < article["min_units"]:
            below_article_min.append(article_id)
    discount_entry = current_value(rules["transfer_discount_pct"], today)
    discount_pct = discount_entry["value"] if payment == "transferencia" and discount_entry else 0
    discount = subtotal * discount_pct // 100
    minimum = current_value(rules["min_purchase"], today)["value"]
    free_from = current_value(rules["free_shipping_from"], today)["value"]
    return {
        "subtotal": subtotal,
        "discount": discount,
        "discount_pct": discount_pct,
        "zone": zone,
        "total": subtotal - discount,
        "meets_min": subtotal >= minimum,
        "min_purchase": minimum,
        "free_shipping": zone in FREE_SHIPPING_ZONES and subtotal >= free_from,
        "free_shipping_from": free_from,
        "below_article_min": below_article_min,
    }


PAYMENTS = {"efectivo", "transferencia"}
ZONES = {"caba", "gba", "interior"}


def parse_order(raw: str, facts: dict) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    known = {}
    for article in facts["articles"]:
        known[article["id"].lower()] = article["id"]
        known[article["name"].lower()] = article["id"]
        for alias in article["aliases"]:
            known[alias.lower()] = article["id"]
    lines = []
    for line in data.get("lines", []):
        quantity = line.get("quantity")
        article_id = known.get(str(line.get("article_id", "")).lower())
        if article_id and isinstance(quantity, int) and quantity > 0:
            lines.append((article_id, quantity))
    if not lines:
        return None
    payment = str(data.get("payment", "")).lower()
    zone = str(data.get("zone", "")).lower()
    return {
        "lines": lines,
        "payment": payment if payment in PAYMENTS else None,
        "zone": zone if zone in ZONES else None,
    }


def format_quote(result: dict) -> str:
    parts = [f"Subtotal: {money(result['subtotal'])}."]
    if result["discount"]:
        parts.append(f"Descuento por transferencia ({result['discount_pct']}%): {money(result['discount'])}.")
    parts.append(f"Total a pagar: {money(result['total'])}.")
    if result["meets_min"]:
        parts.append(f"Sí alcanza la compra mínima de {money(result['min_purchase'])}.")
    else:
        parts.append(f"NO alcanza la compra mínima de {money(result['min_purchase'])}.")
    if result["zone"] is None:
        parts.append(f"Envío gratis a CABA y GBA desde {money(result['free_shipping_from'])} (zona del cliente no indicada).")
    elif result["free_shipping"]:
        parts.append(f"Corresponde envío gratis (desde {money(result['free_shipping_from'])} en CABA y GBA).")
    else:
        parts.append(f"No corresponde envío gratis (CABA y GBA desde {money(result['free_shipping_from'])}).")
    return " ".join(parts)
