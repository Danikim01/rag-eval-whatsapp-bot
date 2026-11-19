---
date: 2026-11-18
project: Agencia-Automatizaciones
type: probe
tags: [avellaneda, agente, qwen3, tool-calling]
---

# Probe de tool calling con qwen3

Modelo: `qwen3:8b`.
Prompts: 20, con una tool de juguete y temperatura 0.
Comando: `python -m modamayor.agent.probe`.

## Resultado: 100%

| Tipo | Cantidad |
|---|---|
| ok | 20 |

## Decisión

Seguir con tool calling nativo. Se mide de nuevo con las 40 pruebas de la fase 5.

## Fallas

Ninguna.
