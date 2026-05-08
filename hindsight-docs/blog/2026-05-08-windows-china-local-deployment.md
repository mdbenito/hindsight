---
title: "Windows + China Network: A Practical Local Deployment Guide"
description: "How to run Hindsight locally on Windows in restricted networks, including embedding configuration pitfalls, DeepSeek limitations, and Hugging Face mirror setup."
authors: [hindsight]
date: 2026-05-08
tags: [windows, deployment, china, deepseek, embeddings, troubleshooting]
---

If you are deploying Hindsight locally on Windows in a China-based network, there are a few setup traps that can waste hours if you hit them in the wrong order.

This post is a practical setup path based on community feedback and repeat issues we see in support:

- embedding env var naming differences from LLM vars
- DeepSeek embeddings assumptions
- Hugging Face model download failures in restricted networks

<!-- truncate -->

## TL;DR

1. Use DeepSeek for LLM if you want, but not for embeddings.
2. Use local embeddings (`BAAI/bge-small-en-v1.5`) for reliability and privacy.
3. Set `HF_ENDPOINT=https://hf-mirror.com` before startup.
4. Use provider-specific embedding env vars (`HINDSIGHT_API_EMBEDDINGS_{PROVIDER}_{PARAMETER}`).

## Pitfall 1: Embedding Env Vars Use Provider-Specific Names

LLM env vars are provider-agnostic:

- `HINDSIGHT_API_LLM_API_KEY`
- `HINDSIGHT_API_LLM_MODEL`
- `HINDSIGHT_API_LLM_BASE_URL`

Embedding env vars are provider-specific:

- `HINDSIGHT_API_EMBEDDINGS_OPENAI_API_KEY`
- `HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL`
- `HINDSIGHT_API_EMBEDDINGS_OPENAI_BASE_URL`

Common mistake:

- `HINDSIGHT_API_EMBEDDINGS_MODEL` (wrong)
- `HINDSIGHT_API_EMBEDDINGS_OPENAI_MODEL` (correct)

When these keys are misnamed, startup can fall back to default embedding settings and then fail with confusing auth or endpoint errors.

## Pitfall 2: DeepSeek Is LLM-Only for This Stack

DeepSeek works as an LLM provider, but it does not provide a compatible embeddings endpoint for Hindsight embedding calls.

If you are using DeepSeek for `HINDSIGHT_API_LLM_PROVIDER`, pair it with a different embedding provider:

- local (recommended for this setup)
- OpenAI-compatible embeddings
- Cohere
- Google/Gemini embeddings

## Pitfall 3: Hugging Face Download Hangs in China Networks

Local embedding and reranker models are downloaded through Hugging Face tooling. In restricted networks this often stalls or times out unless you set a mirror.

Set this before starting Hindsight:

```bat
set HF_ENDPOINT=https://hf-mirror.com
```

This is a `huggingface_hub` setting, not a Hindsight-specific variable.

## Working Windows `.bat` Example

```bat
@echo off
chcp 65001 >nul
title Hindsight Local Memory Service

set HF_ENDPOINT=https://hf-mirror.com

set HINDSIGHT_API_LLM_PROVIDER=deepseek
set HINDSIGHT_API_LLM_API_KEY=sk-your-deepseek-key
set HINDSIGHT_API_LLM_MODEL=deepseek-v4-flash
set HINDSIGHT_API_LLM_BASE_URL=https://api.deepseek.com

set HINDSIGHT_API_EMBEDDINGS_PROVIDER=local
set HINDSIGHT_API_EMBEDDINGS_LOCAL_MODEL=BAAI/bge-small-en-v1.5

set HINDSIGHT_API_RERANKER_PROVIDER=flashrank

hindsight-api --port 8888
```

Then open:

- API docs: `http://127.0.0.1:8888/docs`
- Metrics: `http://127.0.0.1:8888/metrics`

## Validation

Quick reflect check:

```bash
curl -X POST http://127.0.0.1:8888/v1/default/banks/test/reflect \
  -H "Content-Type: application/json" \
  -d '{"query":"Hello, testing memory system","budget":"low"}'
```

## Where This Lives in the Docs

We also added this guidance to the core docs so it is easier to find during setup:

- [Configuration](/developer/configuration#embeddings)
- [Installation (Windows)](/developer/installation#windows)

If you are okay with managed infrastructure and unrestricted network access, [Hindsight Cloud](https://ui.hindsight.vectorize.io/signup) is the fastest path to production.
