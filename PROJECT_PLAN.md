# Citadel: System Architecture & Master Plan

## Project Identity
Citadel is a high-throughput security proxy and middleware layer designed to protect downstream LLM APIs and backend systems. It intercepts, sanitizes, cryptographically signs, and structurally validates all inbound prompts and outbound tool calls.

## Core Architectural Flow

- Designed a high-throughput middleware security proxy using Python and FastAPI to intercept payloads and protect downstream LLM APIs from prompt injections.

- Enforced a zero-trust cryptographic signing layer utilizing HMAC-SHA256 standard libraries to authenticate inbound payloads. The architecture deliberately drops unverified signatures and avoids complex external dependencies to minimize bloat and ensure the entire round-trip overhead remains under 200ms.

- Built a strict Context-Free Grammar (CFG) token state machine to parse raw LLM outputs character-by-character and guarantee valid JSON structures. The custom parser evaluates complex grammar rules, precisely managing state transitions like LR(0) items, to rigorously reject malformed data. It triggers immediate fallback handlers upon syntax violation without attempting to guess or fix the output.

## Tech Stack
* **Framework:** Python, FastAPI
* **Security:** Python `hmac`, `hashlib` (HMAC-SHA256)
* **Parser Engine:** Custom Token State Machine / Lark
* **Deployment:** Docker

## AI Assistant Directives

- Designed a high-throughput middleware security proxy using Python and FastAPI to intercept payloads and protect downstream LLM APIs from prompt injections.

- Enforced a zero-trust cryptographic signing layer utilizing HMAC-SHA256 standard libraries to authenticate inbound payloads. The architecture deliberately drops unverified signatures and avoids complex external dependencies to minimize bloat and ensure the entire round-trip overhead remains under 200ms.

- Built a strict Context-Free Grammar (CFG) token state machine to parse raw LLM outputs character-by-character and guarantee valid JSON structures. The custom parser evaluates complex grammar rules, precisely managing state transitions like LR(0) items, to rigorously reject malformed data. It triggers immediate fallback handlers upon syntax violation without attempting to guess or fix the output.