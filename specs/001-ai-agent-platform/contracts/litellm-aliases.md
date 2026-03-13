# LiteLLM Model Alias Contract

**Date**: 2026-03-14 | **Plan**: [plan.md](../plan.md)

This document defines the model alias contract between agent code and the LiteLLM proxy.
Agent code MUST use only the aliases listed here — never provider model strings.
The mapping from alias → provider/model is configured exclusively in `infra/litellm/config.yaml.template`.

---

## Canonical Aliases

| Alias | Purpose | Default provider/model | Fallback |
|-------|---------|------------------------|---------|
| `default` | General-purpose chat — reasoning, instruction following, long context | `anthropic/claude-sonnet-4-5` | `fast` |
| `fast` | Low-latency chat — classification, routing, short responses | `openai/gpt-4o-mini` | _(none)_ |
| `embedding` | Text embedding — semantic memory storage and retrieval | `openai/text-embedding-3-small` via local endpoint | _(none)_ |

### Rules

1. **Agent code uses aliases only.** Any import or usage of `anthropic`, `openai`, `cohere`, or any other provider SDK in agent code is a constitution violation (§VI).
2. **Aliases are stable.** The alias names in this document do not change. Provider mappings behind them change only via config update.
3. **New aliases follow this process**: proposal → constitutional review → update this document + `config.yaml.template` + `.env.example`.
4. **Embedding dimensions** for the `embedding` alias is **1536**. Any code storing or querying vectors MUST match this dimension. Changing the embedding alias to a model with different dimensions requires a Qdrant collection migration.

---

## SDK Usage Pattern

```python
# agent/graphs/tool_agent.py  — correct
from openai import AsyncOpenAI

llm = AsyncOpenAI(
    base_url=settings.LITELLM_BASE_URL + "/v1",
    api_key=settings.LITELLM_API_KEY,
)
response = await llm.chat.completions.create(
    model="default",      # ← alias, not provider string
    messages=messages,
)

# WRONG — direct provider SDK, banned
import anthropic  # ← constitution violation §VI
```

---

## Environment Variables (agent-api container)

| Variable | Description | Example |
|----------|-------------|---------|
| `LITELLM_BASE_URL` | Base URL of the LiteLLM proxy (internal Docker network) | `http://litellm:4000` |
| `LITELLM_API_KEY` | Auth key for the proxy (matches `LITELLM_MASTER_KEY` or a virtual key) | `sk-agent-platform-internal` |

---

## Fallback Behaviour

When the primary provider for an alias is unavailable:
1. LiteLLM retries the primary up to `num_retries` times (default: 2).
2. On exhaustion, LiteLLM routes to the configured fallback alias (see table above).
3. The fallback routing event is recorded as a warning in the Langfuse trace via the OTEL callback.
4. If no fallback is configured and the primary is exhausted, LiteLLM returns a 503 that propagates to the caller as a platform error.

---

## Budget Limits (per alias, per 30-day window)

| Alias | Default budget | Duration |
|-------|---------------|---------|
| `default` | $300 | 30 days |
| `fast` | $500 | 30 days |
| `embedding` | $100 | 30 days |

Per-client virtual key budgets are additionaly enforced at the proxy layer (see `infra/litellm/config.yaml.template`).

---

## Adding a New Alias

1. Propose the alias name and mapping in a PR that updates this file and `infra/litellm/config.yaml.template`.
2. Verify the new alias is reachable by running `make test-litellm-alias ALIAS=<name>` against a running LiteLLM instance.
3. Update `.env.example` with any new required env vars for the provider.
4. Bump the `model_alias` `CHECK` constraint in the `agent_definitions` migration to include the new alias.
